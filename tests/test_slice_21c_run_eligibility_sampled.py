"""
Focused tests for Slice 21C (GitHub issue #21, "Distinguish triggering
inputs from sampled inputs in node firing rules"): `Session`'s firing
eligibility evaluated over TRIGGERING-role consumed types only.

See `.claude/reed-refactor/run-21C-20260919T144759Z/slice_contract.yaml`
for the full objective. A consumed artifact declared `Annotated[T,
Sampled]` still counts toward coverage (the node cannot be called
without a value for it) but its arrival never by itself marks it fresh
or fires the node -- reed-sampled-inputs-proposal.md's acceptance
criterion 4, "a SAMPLED arrival alone never fires".

These tests feed domain values directly (`session.feed(_B(...))`,
`session.feed(_C(...))`, followed by `session.push()`) with no producer
node for them, exactly as
tests/test_slice_2i_joins_and_trigger_policy.py's own join tests already
do for `_C` -- `Session.feed`/`Session.push` only require a registered
consumer, not a producer.
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
    session = flow.session()

    session.feed(_B(1))
    session.push()  # SAMPLED arrives; not covered (c missing) -> no fire
    assert fired == []

    session.feed(_C(10))
    session.push()  # TRIGGERING arrives; covered and fresh -> fires
    assert fired == ["join"]

    session.feed(_B(99))
    session.push()  # SAMPLED-only re-arrival on an already-covered,
    # already-fired node -- freshness only tracks TRIGGERING types, so
    # this must not re-fire.
    assert fired == ["join"]
    assert session.node_session(join).last_output.value == 1 + 10


def test_sampled_only_publish_never_fires_a_covered_node_any_input_changed():
    fired: list[str] = []

    def join(b: Annotated[_B, Sampled], c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        fired.append("join")
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(join, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    session = flow.session()

    session.feed(_B(1))
    session.push()  # SAMPLED arrives first; not covered (c missing)
    assert fired == []

    session.feed(_C(10))
    session.push()  # TRIGGERING arrival completes coverage -> fires
    assert fired == ["join"]

    session.feed(_B(99))
    session.push()  # SAMPLED-only arrival on an already-covered,
    # already-fired node -- must not fire again even under
    # ANY_INPUT_CHANGED.
    assert fired == ["join"]
    assert session.node_session(join).last_output.value == 1 + 10


def test_triggering_publish_fires_using_latest_sampled_values_published_before_coverage():
    def join(b: Annotated[_B, Sampled], c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(join, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    session = flow.session()

    session.feed(_B(7))
    session.push()  # SAMPLED value published ahead of coverage
    session.feed(_C(3))
    session.push()  # TRIGGERING arrival completes coverage -> fires

    assert session.node_session(join).last_output.value == 10


def test_all_inputs_changed_refire_ignores_sampled_freshness_and_only_needs_triggering_types_fresh_again():
    fired: list[str] = []

    def join(b: Annotated[_B, Sampled], c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        fired.append("join")
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(join, trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED)
    session = flow.session()

    session.feed(_B(1))
    session.push()
    session.feed(_C(10))
    session.push()  # covered, c fresh -> fires (join #1)
    assert fired == ["join"]

    session.feed(_B(2))
    session.push()  # only SAMPLED b changes -- must not refire
    assert fired == ["join"]

    session.feed(_C(20))
    session.push()  # c fresh again -> refires using latest b (2)
    assert fired == ["join", "join"]
    assert session.node_session(join).last_output.value == 2 + 20


def test_any_input_changed_fires_on_triggering_arrival_and_samples_latest_sampled_values():
    def join(b: Annotated[_B, Sampled], c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(join, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    session = flow.session()

    session.feed(_B(1))
    session.push()
    session.feed(_C(10))
    session.push()  # fires: b=1, c=10
    assert session.node_session(join).last_output.value == 11

    session.feed(_B(100))
    session.push()  # SAMPLED-only change -- no fire
    assert session.node_session(join).last_output.value == 11

    session.feed(_C(5))
    session.push()  # TRIGGERING arrival -- fires using latest sampled b=100
    assert session.node_session(join).last_output.value == 105


def test_dirty_from_an_earlier_triggering_feed_fires_once_a_later_sampled_feed_completes_coverage():
    """
    DELIBERATE, OPENLY-RECORDED TEST REVERSAL (Slice 22H-1; Test
    Integrity Rule precedent set by Slice 22C). This test used to be
    named
    test_any_input_changed_never_fires_when_the_sampled_arrival_is_what_completes_coverage
    and asserted the OPPOSITE of what it asserts now -- that `join`
    could never fire once a SAMPLED arrival was the one to complete
    coverage. That was true under the OLD, synchronous publish() model,
    where eligibility was checked once per single arrival and only ever
    considered the type of the value THAT SPECIFIC CALL published: a
    SAMPLED arrival could therefore never itself trigger an eligibility
    check, even when it happened to complete coverage.

    Under the batched feed()/push() model (Slice 22F) that framing does
    not carry over: push() evaluates every currently-dirty node in one
    pass, regardless of which specific feed() most recently landed or
    which arrival dirtied it. Below, the FIRST push() leaves `join`
    dirty-but-not-fired because coverage isn't complete yet (invariant
    18: dirty state persists, is not silently discarded, across a push()
    that cannot yet fire it). The SECOND push() then correctly fires
    `join` -- honestly caused by the EARLIER, already-recorded TRIGGERING
    (_C) dirtying, with the SAMPLED (_B) feed only supplying the missing
    value, not itself originating the trigger. This is a correct,
    deliberate consequence of dirty-persists-across-a-not-yet-covered-
    push (confirmed independently by 22F's own reviewer), not a bug to
    route around.

    The stricter invariant this test used to (mis)state -- a SAMPLED
    arrival with NO accompanying or prior TRIGGERING dirtying must never
    by itself cause a firing -- is still true, and is covered by
    tests/test_slice_22f_session_push.py::test_push_respects_sampled_vs_triggering_eligibility_from_issue_21
    (SAMPLED feed arrives first, before any TRIGGERING feed at all); it
    is not duplicated here.
    """
    fired: list[str] = []

    def join(c: _C, b: Annotated[_B, Sampled], ctx: NodeContext[_Memory, _D]) -> _D:
        fired.append("join")
        return _D(c.value + b.value)

    flow = Flow()
    flow.add(join, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    session = flow.session()

    session.feed(_C(5))
    session.push()  # TRIGGERING arrives first; not covered (b missing) -- dirty, does not fire
    assert fired == []

    session.feed(_B(100))
    session.push()  # SAMPLED feed completes coverage -- fires now, using the still-dirty earlier TRIGGERING
    assert fired == ["join"]
    assert session.node_session(join).last_output.value == 5 + 100

    session.feed(_C(7))
    session.push()  # next TRIGGERING arrival fires again, using latest b=100
    assert fired == ["join", "join"]
    assert session.node_session(join).last_output.value == 7 + 100


def test_manual_policy_with_sampled_inputs_is_still_never_auto_fired():
    fired: list[str] = []

    def join(b: Annotated[_B, Sampled], c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        fired.append("join")
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(join, trigger_policy=TriggerPolicy.MANUAL)
    session = flow.session()

    session.feed(_B(1))
    session.push()
    session.feed(_C(10))
    session.push()
    session.feed(_B(2))
    session.push()
    session.feed(_C(20))
    session.push()

    assert fired == []
    assert session.node_session(join).last_output is None
