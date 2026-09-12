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
    print("[tokenize]")
    return Tokens(words=raw.text.split())


def normalize(raw: RawText) -> NormalizedText:
    print("[normalize]")
    return NormalizedText(text=raw.text.lower())


def contains_python(normalized: NormalizedText) -> ContainsPython:
    print("[contains_python]")
    return ContainsPython(value="python" in normalized.text)


def statistics(tokens: Tokens) -> Statistics:
    print("[statistics]")
    return Statistics(
        word_count=len(tokens.words),
        character_count=sum(len(word) for word in tokens.words),
    )


def merge(
    ctx: NodeContext[AnalysisMemory, Analysis],
    stats: Statistics,
    contains: ContainsPython,
) -> Analysis:
    print("[merge]")
    ctx.memory.analyses_completed += 1

    if ctx.last_output is not None:
        print("[merge] previous analysis:", ctx.last_output)

    return Analysis(
        word_count=stats.word_count,
        character_count=stats.character_count,
        contains_python=contains.value,
    )


def build_report(analysis: Analysis) -> Report:
    print("[build_report]")
    return Report(
        text=(
            f"Words: {analysis.word_count}\n"
            f"Characters: {analysis.character_count}\n"
            f"Contains 'Python': {analysis.contains_python}"
        )
    )


def save_report(report: Report) -> None:
    print("[save_report]")
    print(report.text)


def show_analysis(analysis: Analysis) -> None:
    print("[analysis committed]")
    print(analysis.word_count, analysis.character_count, analysis.contains_python)


flow = Flow()

flow.add(tokenize)
flow.add(normalize)

flow.add(statistics)
flow.add(contains_python)

flow.add(
    merge,
    trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED,
    on_output=show_analysis,
)

flow.add(build_report)
flow.add(save_report)


if __name__ == "__main__":
    run = flow.run()

    run.publish(
        RawText(text="Python type annotations make reactive graphs elegant.")
    )

    run.publish(
        RawText(text="Reed should propagate artifacts automatically.")
    )

    run.wait_for_callbacks()

    if run.callback_failures:
        print("Callback failures:", run.callback_failures)
