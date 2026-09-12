"""
Automated end-to-end acceptance test for Slice 2K.

This test asserts, as committed BEHAVIOR (never stdout), the exact
quality-gate scenario reproduced verbatim in
`examples/text_analysis_pipeline.py`: a single external publication must
automatically fan out and propagate through the complete graph
(RawText -> tokenize/normalize -> statistics/contains_python -> merge
(TriggerPolicy.ALL_INPUTS_CHANGED) -> build_report -> save_report) with
no manual intermediate republish or repository read required to make
the pipeline progress, and NodeContext memory/last_output must be
correctly preserved and updated across repeated publications.

Domain types and node functions are duplicated here rather than imported
from `examples/text_analysis_pipeline.py`. That module is a standalone
script (its `__main__` block itself calls `run.publish` twice and
`run.wait_for_callbacks()`); importing it would either execute that
script body as an import-time side effect or require guarding it behind
an `if __name__ == "__main__"` re-check that adds indirection for no
benefit. Duplicating the small, stable domain/node definitions keeps
this test self-contained and independent of any future narrative changes
to the example file, matching the pattern already used by
`tests/test_slice_2i_joins_and_trigger_policy.py` and
`tests/test_slice_2j_on_output_typing.py` (local classes/functions
rather than imports from examples/).

IMPORTANT -- Test Integrity / anti-regression intent: this test calls
`run.publish(...)` in its exercise of the pipeline EXACTLY as many times
as there are external inputs (once in the single-publish test, twice in
the second test) and never anything else that advances execution. It
reads `run.repository.get(...)` / `run.node_runtime(...)` ONLY in final
assertions, after the pipeline has already run to completion via
`run.wait_for_callbacks()`. If a future regression reintroduces a need
for manual republication or manual intermediate retrieval to make the
graph progress (e.g. merge or build_report failing to fire
automatically), the intermediate artifacts asserted here (Report,
Analysis, NodeContext memory) will simply never be committed and these
assertions will fail -- there is no fallback path in this test that
would paper over that regression.
"""

from __future__ import annotations

from dataclasses import dataclass

from reed import Flow, NodeContext, TriggerPolicy


@dataclass(frozen=True)
class RawText:
    text: str


@dataclass(frozen=True)
class NormalizedText:
    text: str


@dataclass(frozen=True)
class Tokens:
    words: list[str]


@dataclass(frozen=True)
class Statistics:
    word_count: int
    character_count: int


@dataclass(frozen=True)
class ContainsPython:
    value: bool


@dataclass(frozen=True)
class Analysis:
    word_count: int
    character_count: int
    contains_python: bool


@dataclass(frozen=True)
class Report:
    text: str


@dataclass
class AnalysisMemory:
    analyses_completed: int = 0


def tokenize(raw: RawText) -> Tokens:
    return Tokens(words=raw.text.split())


def normalize(raw: RawText) -> NormalizedText:
    return NormalizedText(text=raw.text.lower())


def contains_python(normalized: NormalizedText) -> ContainsPython:
    return ContainsPython(value="python" in normalized.text)


def statistics(tokens: Tokens) -> Statistics:
    return Statistics(
        word_count=len(tokens.words),
        character_count=sum(len(word) for word in tokens.words),
    )


def merge(
    ctx: NodeContext[AnalysisMemory, Analysis],
    stats: Statistics,
    contains: ContainsPython,
) -> Analysis:
    ctx.memory.analyses_completed += 1
    return Analysis(
        word_count=stats.word_count,
        character_count=stats.character_count,
        contains_python=contains.value,
    )


def build_report(analysis: Analysis) -> Report:
    return Report(
        text=(
            f"Words: {analysis.word_count}\n"
            f"Characters: {analysis.character_count}\n"
            f"Contains 'Python': {analysis.contains_python}"
        )
    )


def save_report(report: Report) -> None:
    # No-op side effect target for the pipeline's terminal node; presence
    # of the committed Report is asserted via run.repository instead of
    # any side effect performed here.
    return None


def _build_flow(on_analysis_committed):
    flow = Flow()
    flow.add(tokenize)
    flow.add(normalize)
    flow.add(statistics)
    flow.add(contains_python)
    flow.add(
        merge,
        trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED,
        on_output=on_analysis_committed,
    )
    flow.add(build_report)
    flow.add(save_report)
    return flow


def test_quality_gate_single_publish_propagates_end_to_end_without_manual_republish():
    committed_analyses: list[Analysis] = []

    flow = _build_flow(committed_analyses.append)
    run = flow.run()

    # The ONLY call in this test's exercise of the pipeline that advances
    # execution: exactly one external publication.
    run.publish(
        RawText(text="Python type annotations make reactive graphs elegant.")
    )
    run.wait_for_callbacks()

    # Observation-only reads below -- the pipeline has already completed.
    report = run.repository.get(Report).value
    analysis = run.repository.get(Analysis).value

    assert analysis.word_count == 7
    assert analysis.character_count == 47
    assert analysis.contains_python is True
    assert report.text == (
        "Words: 7\nCharacters: 47\nContains 'Python': True"
    )
    assert len(committed_analyses) == 1
    assert committed_analyses[0] == analysis
    assert run.callback_failures == []


def test_quality_gate_second_publish_updates_memory_and_preserves_last_output():
    committed_analyses: list[Analysis] = []

    flow = _build_flow(committed_analyses.append)
    run = flow.run()

    run.publish(
        RawText(text="Python type annotations make reactive graphs elegant.")
    )
    run.publish(
        RawText(text="Reed should propagate artifacts automatically.")
    )
    run.wait_for_callbacks()

    # Observation-only reads below -- both publications have already
    # completed; nothing here re-drives the pipeline.
    merge_runtime = run.node_runtime(merge)

    assert merge_runtime.memory.analyses_completed == 2
    assert merge_runtime.last_output.word_count == 5
    assert merge_runtime.last_output.character_count == 42
    assert merge_runtime.last_output.contains_python is False

    assert len(committed_analyses) == 2
    assert committed_analyses[0].word_count == 7
    assert committed_analyses[0].character_count == 47
    assert committed_analyses[0].contains_python is True
    assert committed_analyses[1] == merge_runtime.last_output

    report = run.repository.get(Report).value
    assert report.text == (
        "Words: 5\nCharacters: 42\nContains 'Python': False"
    )
    assert run.callback_failures == []


def test_quality_gate_merge_requires_both_inputs_before_firing():
    merge_calls: list[Analysis] = []

    def counting_merge(
        ctx: NodeContext[AnalysisMemory, Analysis],
        stats: Statistics,
        contains: ContainsPython,
    ) -> Analysis:
        ctx.memory.analyses_completed += 1
        analysis = Analysis(
            word_count=stats.word_count,
            character_count=stats.character_count,
            contains_python=contains.value,
        )
        merge_calls.append(analysis)
        return analysis

    flow = Flow()
    flow.add(tokenize)
    flow.add(normalize)
    flow.add(statistics)
    flow.add(contains_python)
    flow.add(counting_merge, trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED)
    flow.add(build_report)
    flow.add(save_report)
    run = flow.run()

    run.publish(RawText(text="hello world"))
    run.wait_for_callbacks()

    # merge must have fired exactly once per publish -- proving genuine
    # dependency-state gating (both Statistics and ContainsPython fresh)
    # rather than the node firing per-input or not at all.
    assert len(merge_calls) == 1
    assert run.callback_failures == []


def test_quality_gate_no_callback_failures():
    flow = _build_flow(lambda analysis: None)
    run = flow.run()

    run.publish(
        RawText(text="Python type annotations make reactive graphs elegant.")
    )
    run.publish(
        RawText(text="Reed should propagate artifacts automatically.")
    )
    run.wait_for_callbacks()

    assert run.callback_failures == []
