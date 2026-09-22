"""
Focused tests for Slice 2I (multi-input joins and real TriggerPolicy
evaluation -- completes the propagation engine).

See `.claude/reed-refactor/run-2I-20260912T185507Z/slice_contract.yaml`
for the full objective. These tests exercise `Session.push()`'s
cascade now consulting `TriggerPolicy` for every discovered consumer
(single- or multi-input) and building full call-argument sets for
multi-input join nodes once eligible.
"""

from __future__ import annotations

from reed import Flow, NodeContext, TriggerPolicy


class _A:
    def __init__(self, value: int) -> None:
        self.value = value


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


def test_join_node_does_not_fire_until_every_consumed_type_has_a_value():
    fired: list[str] = []

    def to_b(a: _A) -> _B:
        return _B(a.value)

    def join(b: _B, c: _C) -> _D:
        fired.append("join")
        return _D(b.value)

    flow = Flow()
    flow.add(to_b)
    flow.add(join, trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED)
    session = flow.session()

    session.feed(_A(1))
    session.push()

    assert fired == []


def test_join_node_fires_once_all_inputs_present_all_inputs_changed():
    fired: list[str] = []

    def to_b(a: _A) -> _B:
        return _B(a.value)

    def join(b: _B, c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        fired.append("join")
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(to_b)
    flow.add(join, trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED)
    session = flow.session()

    session.feed(_A(1))
    session.push()  # b arrives, join not yet covered
    session.feed(_C(10))
    session.push()  # c arrives, join now covered and fresh -> fires

    assert fired == ["join"]
    assert session.node_session(join).last_output.value == 11


def test_all_inputs_changed_join_requires_every_input_fresh_again_to_refire():
    fired: list[str] = []

    def to_b(a: _A) -> _B:
        return _B(a.value)

    def join(b: _B, c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        fired.append("join")
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(to_b)
    flow.add(join, trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED)
    session = flow.session()

    session.feed(_A(1))
    session.push()
    session.feed(_C(10))
    session.push()  # covered + both fresh -> fires (join #1)

    assert fired == ["join"]

    session.feed(_C(20))
    session.push()  # only c fresh again -> must NOT re-fire

    assert fired == ["join"]

    session.feed(_A(2))
    session.push()  # now b fresh again too -> both fresh -> fires

    assert fired == ["join", "join"]
    assert session.node_session(join).last_output.value == 2 + 20


def test_any_input_changed_join_fires_on_each_new_input_once_fully_covered():
    fired: list[str] = []

    def to_b(a: _A) -> _B:
        return _B(a.value)

    def join(b: _B, c: _C) -> _D:
        fired.append("join")
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(to_b)
    flow.add(join, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    session = flow.session()

    session.feed(_A(1))
    session.push()  # b arrives; c missing -> not covered, no fire
    assert fired == []

    session.feed(_C(10))
    session.push()  # c arrives; now covered -> fires
    assert fired == ["join"]

    session.feed(_C(20))
    session.push()  # c changes again -> fires again immediately
    assert fired == ["join", "join"]

    session.feed(_A(2))
    session.push()  # b changes -> fires again immediately
    assert fired == ["join", "join", "join"]


def test_any_input_changed_join_uses_latest_known_value_for_untouched_inputs():
    def to_b(a: _A) -> _B:
        return _B(a.value)

    def join(b: _B, c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(to_b)
    flow.add(join, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    session = flow.session()

    session.feed(_A(1))
    session.push()
    session.feed(_C(10))
    session.push()  # covered -> fires with b=1, c=10

    assert session.node_session(join).last_output.value == 11

    session.feed(_C(100))
    session.push()  # only c changes; b's last-known value (1) reused

    assert session.node_session(join).last_output.value == 101


def test_manual_policy_node_is_discovered_but_never_auto_fired_single_input():
    fired: list[str] = []

    def to_b(a: _A, ctx: NodeContext[_Memory, _B]) -> _B:
        fired.append("to_b")
        return _B(a.value)

    flow = Flow()
    flow.add(to_b, trigger_policy=TriggerPolicy.MANUAL)
    session = flow.session()

    session.feed(_A(1))
    session.push()
    session.feed(_A(2))
    session.push()
    session.feed(_A(3))
    session.push()

    assert fired == []
    assert session.node_session(to_b).last_output is None


def test_manual_policy_node_is_discovered_but_never_auto_fired_multi_input():
    fired: list[str] = []

    def to_b(a: _A) -> _B:
        return _B(a.value)

    def join(b: _B, c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        fired.append("join")
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(to_b)
    flow.add(join, trigger_policy=TriggerPolicy.MANUAL)
    session = flow.session()

    session.feed(_A(1))
    session.push()
    session.feed(_C(10))
    session.push()
    session.feed(_A(2))
    session.push()
    session.feed(_C(20))
    session.push()

    assert fired == []
    assert session.node_session(join).last_output is None


def test_join_node_firing_dispatches_on_output_and_updates_node_session():
    on_output_seen: list[int] = []

    def to_b(a: _A) -> _B:
        return _B(a.value)

    def join(b: _B, c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        ctx.memory  # accessing memory must not raise
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(to_b)
    flow.add(
        join,
        trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED,
        on_output=lambda value: on_output_seen.append(value.value),
    )
    session = flow.session()

    session.feed(_A(3))
    session.push()
    session.feed(_C(4))
    session.push()

    node_session = session.node_session(join)
    assert node_session.last_output.value == 7
    assert node_session.firing_lock is not None
    assert on_output_seen == [7]


def test_slice_2h_single_input_default_all_inputs_changed_behavior_unchanged():
    # Regression: single-input FlowNodes using either explicit policy
    # (or the ALL_INPUTS_CHANGED dataclass default) still fire
    # immediately on their one consumed type's arrival, matching Slice
    # 2H's existing unconditional single-input firing.
    calls: list[str] = []

    def to_b(a: _A, ctx: NodeContext[_Memory, _B]) -> _B:
        calls.append("to_b")
        return _B(a.value + 1)

    def to_c(b: _B, ctx: NodeContext[_Memory, _C]) -> _C:
        calls.append("to_c")
        return _C(b.value + 1)

    flow = Flow()
    flow.add(to_b)  # default trigger_policy (ALL_INPUTS_CHANGED)
    flow.add(to_c, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    session = flow.session()

    session.feed(_A(1))
    session.push()

    assert calls == ["to_b", "to_c"]
    assert session.node_session(to_b).last_output.value == 2
    assert session.node_session(to_c).last_output.value == 3

    session.feed(_A(10))
    session.push()

    assert calls == ["to_b", "to_c", "to_b", "to_c"]
    assert session.node_session(to_b).last_output.value == 11
    assert session.node_session(to_c).last_output.value == 12
