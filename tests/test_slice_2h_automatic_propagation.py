"""
Focused tests for Slice 2H (automatic propagation engine core --
linear/fan-out, single-input consumers only).

See `.claude/reed-refactor/run-2H-20260912T184226Z/slice_contract.yaml`
for the full objective. These tests exercise `Run.publish(...)`'s new
work-queue-driven cascade: a directly published domain value now
triggers every reachable single-input consumer, not just one FlowNode,
and the cascade continues transitively until no more eligible FlowNodes
remain (quiescence). A discovered multi-input FlowNode is left inert
(discovered, not fired, no error) -- that is exactly this slice's
deliberately narrow terminal condition; join-firing semantics are
Slice 2I's job.
"""

from __future__ import annotations

from reed import Flow, NodeContext


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


class _E:
    def __init__(self, value: int) -> None:
        self.value = value


class _Memory:
    pass


def test_linear_multi_hop_cascade_fires_every_downstream_node():
    # A -> B -> C -> D: one publish(A) should cascade through all three
    # hops without any further publish() calls.
    calls: list[str] = []

    def to_b(a: _A, ctx: NodeContext[_Memory, _B]) -> _B:
        calls.append("to_b")
        return _B(a.value + 1)

    def to_c(b: _B, ctx: NodeContext[_Memory, _C]) -> _C:
        calls.append("to_c")
        return _C(b.value + 1)

    def to_d(c: _C, ctx: NodeContext[_Memory, _D]) -> _D:
        calls.append("to_d")
        return _D(c.value + 1)

    flow = Flow()
    flow.add(to_b)
    flow.add(to_c)
    flow.add(to_d)
    run = flow.run()

    run.publish(_A(1))

    assert calls == ["to_b", "to_c", "to_d"]
    assert run.node_runtime(to_b).last_output.value == 2
    assert run.node_runtime(to_c).last_output.value == 3
    assert run.node_runtime(to_d).last_output.value == 4


def test_fan_out_fires_every_consumer_of_the_same_artifact_type():
    # A is consumed by both to_b and to_c -- both must fire from one
    # publish(A) call.
    fired: list[str] = []

    def to_b(a: _A, ctx: NodeContext[_Memory, _B]) -> _B:
        fired.append("to_b")
        return _B(a.value * 2)

    def to_c(a: _A, ctx: NodeContext[_Memory, _C]) -> _C:
        fired.append("to_c")
        return _C(a.value * 3)

    flow = Flow()
    flow.add(to_b)
    flow.add(to_c)
    run = flow.run()

    run.publish(_A(5))

    assert set(fired) == {"to_b", "to_c"}
    assert run.node_runtime(to_b).last_output.value == 10
    assert run.node_runtime(to_c).last_output.value == 15


def test_multi_input_flow_node_is_discovered_but_not_fired_and_raises_no_error():
    # to_d consumes both _B and _C -- two consumed artifact types, so it
    # is a join candidate. It must be discovered as a consumer of _B
    # (reachable from publish(A)) but never fired and never errored.
    fired: list[str] = []

    def to_b(a: _A) -> _B:
        fired.append("to_b")
        return _B(a.value)

    def to_c(a: _A) -> _C:
        fired.append("to_c")
        return _C(a.value)

    def to_d(b: _B, c: _C) -> _D:
        fired.append("to_d")  # pragma: no cover -- must never actually fire
        return _D(b.value + c.value)

    flow = Flow()
    flow.add(to_b)
    flow.add(to_c)
    flow.add(to_d)
    run = flow.run()

    result = run.publish(_A(7))

    assert "to_d" not in fired
    assert set(fired) == {"to_b", "to_c"}
    # No exception was raised (implicit -- publish() returned normally),
    # and the directly-fired node's own committed value is returned.
    assert isinstance(result, (_B, _C))


def test_quiescence_terminates_a_finite_cascade_with_no_leftover_queue():
    # A three-hop linear cascade with a terminal node (nothing consumes
    # its output) must simply stop -- no error, no hang.
    def to_b(a: _A, ctx: NodeContext[_Memory, _B]) -> _B:
        return _B(a.value)

    def to_c(b: _B, ctx: NodeContext[_Memory, _C]) -> _C:
        return _C(b.value)

    flow = Flow()
    flow.add(to_b)
    flow.add(to_c)
    run = flow.run()

    # Must return promptly with the correct terminal state.
    run.publish(_A(3))

    assert run.node_runtime(to_b).last_output.value == 3
    assert run.node_runtime(to_c).last_output.value == 3


def test_cascade_fired_nodes_get_correct_node_runtime_and_on_output_dispatch():
    # NodeRuntime memory/last_output/firing_lock and on_output dispatch
    # must occur correctly for every cascade-fired node, not only the
    # directly-published one.
    on_output_seen: list[int] = []

    def to_b(a: _A, ctx: NodeContext[_Memory, _B]) -> _B:
        ctx.memory  # accessing memory must not raise
        return _B(a.value + 100)

    def to_c(b: _B, ctx: NodeContext[_Memory, _C]) -> _C:
        return _C(b.value + 1)

    flow = Flow()
    flow.add(to_b)
    flow.add(
        to_c,
        on_output=lambda value: on_output_seen.append(value.value),
    )
    run = flow.run()

    run.publish(_A(1))

    node_runtime_b = run.node_runtime(to_b)
    node_runtime_c = run.node_runtime(to_c)

    assert node_runtime_b.last_output.value == 101
    assert node_runtime_c.last_output.value == 102
    assert node_runtime_b.firing_lock is not None  # state-aware (has ctx)
    assert on_output_seen == [102]


def test_second_publish_call_re_fires_downstream_nodes_with_new_data():
    # No per-version dedup: repeated publish() calls re-run the whole
    # cascade and re-fire the same downstream nodes with new data.
    fire_count = {"to_b": 0, "to_c": 0}

    def to_b(a: _A, ctx: NodeContext[_Memory, _B]) -> _B:
        fire_count["to_b"] += 1
        return _B(a.value + 1)

    def to_c(b: _B, ctx: NodeContext[_Memory, _C]) -> _C:
        fire_count["to_c"] += 1
        return _C(b.value + 1)

    flow = Flow()
    flow.add(to_b)
    flow.add(to_c)
    run = flow.run()

    run.publish(_A(1))
    run.publish(_A(10))

    assert fire_count == {"to_b": 2, "to_c": 2}
    assert run.node_runtime(to_b).last_output.value == 11
    assert run.node_runtime(to_c).last_output.value == 12


def test_publish_return_value_is_the_directly_fired_nodes_own_committed_value():
    # publish()'s return value must remain the directly-fired node's own
    # committed value, unaffected by the cascade it triggers downstream.
    def to_b(a: _A) -> _B:
        return _B(a.value + 1)

    def to_c(b: _B) -> _C:
        return _C(b.value + 1)

    flow = Flow()
    flow.add(to_b)
    flow.add(to_c)
    run = flow.run()

    result = run.publish(_A(1))

    assert isinstance(result, _B)
    assert result.value == 2
