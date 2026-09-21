"""
Focused tests for Slice 21C (GitHub issue #21, "Distinguish triggering
inputs from sampled inputs in node firing rules"): `Run`'s firing
eligibility evaluated over TRIGGERING-role consumed types only.

See `.claude/reed-refactor/run-21C-20260919T144759Z/slice_contract.yaml`
for the full objective. A consumed artifact declared `Annotated[T,
Sampled]` still counts toward coverage (the node cannot be called
without a value for it) but its arrival never by itself marks it fresh
or fires the node -- reed-sampled-inputs-proposal.md's acceptance
criterion 4, "a SAMPLED arrival alone never fires".

These tests publish domain values directly (`run.publish(_B(...))`,
`run.publish(_C(...))`) with no producer node for them, exactly as
tests/test_slice_2i_joins_and_trigger_policy.py's own join tests already
do for `_C` -- `Run.publish` only requires a registered consumer, not a
producer.
"""

from __future__ import annotations

from typing import Annotated

from reed import Flow, NodeContext, TriggerPolicy
from reed.composition.node.sampled import Sampled


class _B:
    def __init__(self, value: int) -> None:
        self.value = value


class _C:
    def __init__(self, value: int) -> None:
        self.value = value


class _D:
    def __init__(self, value: int) -> None:
        self.value = value


class _Memory:
    pass


def test_sampled_only_publish_never_fires_a_covered_node_all_inputs_changed():
    fired: list[str] = []

    def join(b: Annotated[_B, Sampled], c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        fired.append("join")
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(join, trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED)
    run = flow.run()

    run.publish(_B(1))  # SAMPLED arrives; not covered (c missing) -> no fire
    assert fired == []

    run.publish(_C(10))  # TRIGGERING arrives; covered and fresh -> fires
    assert fired == ["join"]

    run.publish(_B(99))  # SAMPLED-only re-arrival on an already-covered,
    # already-fired node -- freshness only tracks TRIGGERING types, so
    # this must not re-fire.
    assert fired == ["join"]
    assert run.node_runtime(join).last_output.value == 1 + 10


def test_sampled_only_publish_never_fires_a_covered_node_any_input_changed():
    fired: list[str] = []

    def join(b: Annotated[_B, Sampled], c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        fired.append("join")
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(join, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    run = flow.run()

    run.publish(_B(1))  # SAMPLED arrives first; not covered (c missing)
    assert fired == []

    run.publish(_C(10))  # TRIGGERING arrival completes coverage -> fires
    assert fired == ["join"]

    run.publish(_B(99))  # SAMPLED-only arrival on an already-covered,
    # already-fired node -- must not fire again even under
    # ANY_INPUT_CHANGED.
    assert fired == ["join"]
    assert run.node_runtime(join).last_output.value == 1 + 10


def test_triggering_publish_fires_using_latest_sampled_values_published_before_coverage():
    def join(b: Annotated[_B, Sampled], c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(join, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    run = flow.run()

    run.publish(_B(7))  # SAMPLED value published ahead of coverage
    run.publish(_C(3))  # TRIGGERING arrival completes coverage -> fires

    assert run.node_runtime(join).last_output.value == 10


def test_all_inputs_changed_refire_ignores_sampled_freshness_and_only_needs_triggering_types_fresh_again():
    fired: list[str] = []

    def join(b: Annotated[_B, Sampled], c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        fired.append("join")
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(join, trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED)
    run = flow.run()

    run.publish(_B(1))
    run.publish(_C(10))  # covered, c fresh -> fires (join #1)
    assert fired == ["join"]

    run.publish(_B(2))  # only SAMPLED b changes -- must not refire
    assert fired == ["join"]

    run.publish(_C(20))  # c fresh again -> refires using latest b (2)
    assert fired == ["join", "join"]
    assert run.node_runtime(join).last_output.value == 2 + 20


def test_any_input_changed_fires_on_triggering_arrival_and_samples_latest_sampled_values():
    def join(b: Annotated[_B, Sampled], c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(join, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    run = flow.run()

    run.publish(_B(1))
    run.publish(_C(10))  # fires: b=1, c=10
    assert run.node_runtime(join).last_output.value == 11

    run.publish(_B(100))  # SAMPLED-only change -- no fire
    assert run.node_runtime(join).last_output.value == 11

    run.publish(_C(5))  # TRIGGERING arrival -- fires using latest sampled b=100
    assert run.node_runtime(join).last_output.value == 105


def test_any_input_changed_never_fires_when_the_sampled_arrival_is_what_completes_coverage():
    # The committed scenarios above all have the TRIGGERING arrival
    # complete coverage last. This is the sharper reading of acceptance
    # criterion 4 ("a SAMPLED arrival alone never fires"): even when the
    # SAMPLED arrival is the one that completes coverage for the first
    # time, it must not fire the node -- only the next TRIGGERING
    # arrival may.
    fired: list[str] = []

    def join(c: _C, b: Annotated[_B, Sampled], ctx: NodeContext[_Memory, _D]) -> _D:
        fired.append("join")
        return _D(c.value + b.value)

    flow = Flow()
    flow.add(join, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    run = flow.run()

    run.publish(_C(5))  # TRIGGERING arrives first; not covered (b missing)
    assert fired == []

    run.publish(_B(100))  # SAMPLED arrival completes coverage -- must not fire
    assert fired == []

    run.publish(_C(7))  # next TRIGGERING arrival fires, using latest b=100
    assert fired == ["join"]
    assert run.node_runtime(join).last_output.value == 7 + 100


def test_manual_policy_with_sampled_inputs_is_still_never_auto_fired():
    fired: list[str] = []

    def join(b: Annotated[_B, Sampled], c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        fired.append("join")
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(join, trigger_policy=TriggerPolicy.MANUAL)
    run = flow.run()

    run.publish(_B(1))
    run.publish(_C(10))
    run.publish(_B(2))
    run.publish(_C(20))

    assert fired == []
    assert run.node_runtime(join).last_output is None
