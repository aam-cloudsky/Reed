"""
Superstep execution (GitHub issue #31).

Rules under test:

1. A (FlowNode, instance) pair fires at most once per `push()`. A later
   arrival is recorded and takes effect in the next `push()`.
2. A FlowNode fires only after every producer of its inputs that may still
   fire in the current `push()` has fired or has been discarded.
3. When every remaining candidate waits on another one (a feedback loop),
   the candidate reached first by the change front is released; the return
   path acts as an implicit unit delay (Lustre's `pre`; Halbwachs et al.,
   Proc. IEEE 79(9), 1991, doi:10.1109/5.97300).
4. Worker outputs are committed at the barrier that closes the superstep,
   all or nothing (Bulk Synchronous Parallel; Valiant, CACM 33(8), 1990,
   doi:10.1145/79173.79181).
5. Iteration order is registration order, never `id()`-dependent.
"""

from __future__ import annotations

import csv

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

import pytest

from reed import Collective, Flow, InstanceKey, NodeContext, Sampled, TriggerPolicy
from reed.observability.storage import CSVProvenanceStore

ANY = TriggerPolicy.ANY_INPUT_CHANGED
ALL = TriggerPolicy.ALL_INPUTS_CHANGED

A = InstanceKey(key="A")
B = InstanceKey(key="B")
C = InstanceKey(key="C")


# ---------------------------------------------------------------------------
# Diamond: S0 -> Left, S0 -> Right, (Left, Right) -> Join
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Source:
    version: int


@dataclass(frozen=True)
class Left:
    version: int


@dataclass(frozen=True)
class Right:
    version: int


@dataclass(frozen=True)
class Join:
    left: int
    right: int


def _diamond(policy: TriggerPolicy, joins: list[tuple[int, int]]) -> Flow:
    def left(source: Source) -> Left:
        return Left(source.version)

    def right(source: Source) -> Right:
        return Right(source.version)

    def join(left: Left, right: Right) -> Join:
        joins.append((left.version, right.version))
        return Join(left.version, right.version)

    flow = Flow()
    flow.add(left, trigger_policy=policy)
    flow.add(right, trigger_policy=policy)
    flow.add(join, trigger_policy=policy)
    return flow


@pytest.mark.parametrize("policy", [ANY, ALL])
def test_diamond_join_fires_once_per_push_with_consistent_inputs(
    policy: TriggerPolicy,
) -> None:
    joins: list[tuple[int, int]] = []
    session = _diamond(policy, joins).session(observability="silent")

    for version in (1, 2, 3):
        session.feed(Source(version))
        session.push()
        assert session.snapshot()[Join] == Join(version, version)

    assert joins == [(1, 1), (2, 2), (3, 3)]


# ---------------------------------------------------------------------------
# Layered graph: depth d, width 2; every node depends on the whole previous
# layer. Required firings per push: 2d + 1.
# ---------------------------------------------------------------------------


def _layered_flow(
    depth: int, policy: TriggerPolicy, fired: list[str]
) -> tuple[Flow, type]:
    def make_type(name: str) -> type:
        return type(name, (int,), {})

    def make_node(name: str, inputs: list[type], output: type) -> Callable[..., object]:
        def one(a: object) -> object:
            fired.append(name)
            return output(int(a) + 1)  # type: ignore[call-overload]

        def two(a: object, b: object) -> object:
            fired.append(name)
            return output(int(a) + int(b))  # type: ignore[call-overload]

        function = one if len(inputs) == 1 else two
        params = ["a", "b"][: len(inputs)]
        function.__annotations__ = dict(zip(params, inputs, strict=True))
        function.__annotations__["return"] = output
        function.__name__ = function.__qualname__ = name
        return function

    source = make_type("LayerSource")
    flow = Flow()
    previous: list[type] = [source]
    for level in range(depth):
        layer = [make_type(f"L{level}_{w}") for w in range(2)]
        for out in layer:
            flow.add(
                make_node(f"n_{out.__name__}", previous, out), trigger_policy=policy
            )
        previous = layer
    sink = make_type("LayerSink")
    flow.add(make_node("n_sink", previous, sink), trigger_policy=policy)
    return flow, source


@pytest.mark.parametrize("policy", [ANY, ALL])
def test_layered_graph_fires_each_node_exactly_once_per_push(
    policy: TriggerPolicy,
) -> None:
    fired: list[str] = []
    flow, source = _layered_flow(6, policy, fired)
    session = flow.session(observability="silent")

    for value in (1, 2, 3):
        fired.clear()
        session.feed(source(value))
        session.push()
        assert len(fired) == 13
        assert len(set(fired)) == 13


# ---------------------------------------------------------------------------
# Feedback loop: n1(a1, a2) -> A3, n2(a3) -> A2
# ---------------------------------------------------------------------------


class A1(int):
    pass


class A2(int):
    pass


class A3(int):
    pass


def _loop(policy: TriggerPolicy, calls: list[tuple[str, int, int]]) -> Flow:
    def n1(a1: A1, a2: A2) -> A3:
        calls.append(("n1", int(a1), int(a2)))
        return A3(a1 + a2)

    def n2(a3: A3) -> A2:
        calls.append(("n2", int(a3), 0))
        return A2(a3 * 10)

    flow = Flow()
    flow.add(n1, trigger_policy=policy)
    flow.add(n2, trigger_policy=policy)
    return flow


@pytest.mark.parametrize("policy", [ANY, ALL])
def test_feedback_loop_terminates_and_next_push_reads_fed_back_value(
    policy: TriggerPolicy,
) -> None:
    calls: list[tuple[str, int, int]] = []
    session = _loop(policy, calls).session(observability="silent")

    session.feed(A2(0))
    session.feed(A1(1))
    session.push()
    assert calls == [("n1", 1, 0), ("n2", 1, 0)]
    assert session.snapshot()[A2] == 10

    calls.clear()
    session.feed(A1(5))
    session.push()
    # n1 reads the A2 produced by n2 in the previous push: the return path
    # is a unit delay.
    assert calls == [("n1", 5, 10), ("n2", 15, 0)]


def test_feedback_loop_is_accepted_at_registration() -> None:
    calls: list[tuple[str, int, int]] = []
    flow = _loop(ANY, calls)
    assert len(flow.flow_nodes) == 2


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class Fan(int):
    pass


def _fan_out_order() -> tuple[str, ...]:
    order: list[str] = []

    def make(name: str) -> Callable[[Fan], object]:
        output = type(f"Out_{name}", (int,), {})

        def node(fan: Fan) -> object:
            order.append(name)
            return output(fan)

        node.__annotations__ = {"fan": Fan, "return": output}
        node.__name__ = node.__qualname__ = name
        return node

    flow = Flow()
    for name in ("first", "second", "third", "fourth", "fifth"):
        flow.add(make(name), trigger_policy=ANY)
    session = flow.session(observability="silent")
    session.feed(Fan(1))
    session.push()
    return tuple(order)


def test_consumers_fire_in_registration_order() -> None:
    orders = {_fan_out_order() for _ in range(30)}
    assert orders == {("first", "second", "third", "fourth", "fifth")}


class S0(int):
    pass


class S1(int):
    pass


def _mixed_policy_run() -> tuple[
    tuple[str, ...], tuple[tuple[tuple[str, int], ...], ...]
]:
    """ALL_INPUTS_CHANGED nodes below ANY_INPUT_CHANGED nodes: before #31 the
    state after push() depended on id()-hash iteration order."""
    fired: list[str] = []
    types = {
        name: type(name, (int,), {})
        for name in ("N0", "N1", "N2", "N3", "N4", "N5", "N6")
    }
    t: dict[str, type] = {"S0": S0, "S1": S1, **types}
    spec = [
        ("N0", ["S1"], ALL),
        ("N1", ["N0", "S0", "S1"], ALL),
        ("N2", ["N1", "S0", "S1"], ANY),
        ("N3", ["S1"], ANY),
        ("N4", ["N1", "N2", "S0"], ALL),
        ("N5", ["S0", "S1"], ANY),
        ("N6", ["N2"], ANY),
    ]

    def make(name: str, inputs: list[str]) -> Callable[..., object]:
        params = [f"p{i}" for i in range(len(inputs))]
        output = t[name]
        weight = sum(ord(c) for c in name)

        def body(*args: int) -> object:
            fired.append(name)
            acc = weight
            for i, value in enumerate(args):
                acc = (acc * 31 + (i + 1) * int(value)) % 1_000_003
            return output(acc)

        namespace: dict[str, object] = {"body": body}
        exec(  # noqa: S102 -- builds a signature with N named parameters
            f"def {name.lower()}({', '.join(params)}):\n    return body({', '.join(params)})\n",
            namespace,
        )
        function = namespace[name.lower()]
        assert callable(function)
        function.__annotations__ = {
            p: t[i] for p, i in zip(params, inputs, strict=True)
        }
        function.__annotations__["return"] = output
        return function

    flow = Flow()
    for name, inputs, policy in spec:
        flow.add(make(name, inputs), trigger_policy=policy)
    session = flow.session(observability="silent")
    rounds = [
        [S1(27)],
        [S0(35), S1(28)],
        [S1(3), S0(5), S1(45)],
        [S0(39), S1(21), S0(46)],
    ]
    states: list[tuple[tuple[str, int], ...]] = []
    for feeds in rounds:
        for value in feeds:
            session.feed(value)
        session.push()
        snapshot = session.snapshot()
        state: list[tuple[str, int]] = []
        for name, cls in t.items():
            committed = snapshot.get(cls)
            if isinstance(committed, int):
                state.append((name, committed))
        states.append(tuple(sorted(state)))
    return tuple(fired), tuple(states)


def test_mixed_trigger_policies_produce_one_deterministic_result() -> None:
    runs = {_mixed_policy_run() for _ in range(40)}
    assert len({firings for firings, _ in runs}) == 1
    assert len({states for _, states in runs}) == 1


# ---------------------------------------------------------------------------
# Barrier, all-or-nothing, fan-in
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Task:
    size: int


@dataclass(frozen=True)
class Partial:
    value: int


@dataclass(frozen=True)
class Go:
    round: int


@dataclass(frozen=True)
class Total:
    value: int
    parts: int


def test_workers_do_not_see_sibling_outputs_before_the_barrier() -> None:
    seen_partials: list[int] = []
    holder: dict[str, object] = {}

    def worker(task: Task) -> Partial:
        session = holder["session"]
        records = session.repository.get_all_artifact_records(Partial)  # type: ignore[attr-defined]
        seen_partials.append(len(records))
        return Partial(task.size * 2)

    flow = Flow()
    flow.add(worker, trigger_policy=ANY)
    session = flow.session(observability="silent")
    holder["session"] = session

    session.feed_instances({A: Task(1), B: Task(2), C: Task(3)})
    session.push()

    assert seen_partials == [0, 0, 0]
    assert len(session.repository.get_all_artifact_records(Partial)) == 3


def test_failing_worker_commits_nothing_from_its_superstep(tmp_path: object) -> None:
    outputs: list[int] = []
    last_outputs_seen: list[object] = []
    failing = {"active": True}

    def worker(ctx: NodeContext[dict[str, int], Partial], task: Task) -> Partial:
        last_outputs_seen.append(ctx.last_output)
        if failing["active"] and task.size == 2:
            raise RuntimeError("worker B failed")
        return Partial(task.size * 2)

    def collect(partial: Partial) -> Total:
        outputs.append(partial.value)
        return Total(partial.value, 1)

    flow = Flow()
    flow.add(worker, trigger_policy=ANY)
    flow.add(collect, trigger_policy=ANY)
    session = flow.session(observability="silent", storage_root=str(tmp_path))

    session.feed_instances({A: Task(1), B: Task(2), C: Task(3)})
    with pytest.raises(RuntimeError, match="worker B failed"):
        session.push()

    assert session.repository.get_all_artifact_records(Partial) == {}
    assert outputs == []
    store = session.provenance_store
    assert isinstance(store, CSVProvenanceStore)
    with store.path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert not any("Partial" in row["artifact_id"] for row in rows)

    # The failed superstep left the freshness untouched: once the fault is
    # gone, the same push() completes, and no worker saw a last_output from
    # the discarded attempt.
    failing["active"] = False
    last_outputs_seen.clear()
    session.push()
    assert last_outputs_seen == [None, None, None]
    assert len(session.repository.get_all_artifact_records(Partial)) == 3


def test_collective_fan_in_runs_after_every_worker_of_the_same_push() -> None:
    received: list[tuple[int, ...]] = []

    def worker(task: Task) -> Partial:
        return Partial(task.size * 10)

    def aggregate(go: Go, partials: Collective[Partial]) -> Total:
        received.append(tuple(sorted(p.value for p in partials)))
        return Total(sum(p.value for p in partials), len(partials))

    flow = Flow()
    flow.add(aggregate, trigger_policy=ANY)  # registered first on purpose
    flow.add(worker, trigger_policy=ANY)
    session = flow.session(observability="silent")

    session.feed(Go(1))
    session.feed_instances({A: Task(1), B: Task(2), C: Task(3)})
    session.push()
    assert received == [(10, 20, 30)]
    assert session.snapshot()[Total] == Total(60, 3)

    session.feed(Go(2))
    session.feed_instances({A: Task(4), B: Task(5), C: Task(6)})
    session.push()
    assert received[-1] == (40, 50, 60)


def test_sampled_input_waits_for_its_producer_in_the_same_push() -> None:
    reads: list[tuple[int, int]] = []

    def doubled(source: Source) -> Left:
        return Left(source.version * 2)

    def reader(source: Source, latest: Annotated[Left, Sampled]) -> Right:
        reads.append((source.version, latest.version))
        return Right(latest.version)

    flow = Flow()
    flow.add(reader, trigger_policy=ANY)
    flow.add(doubled, trigger_policy=ANY)
    session = flow.session(observability="silent")
    session.feed(Left(0))
    for version in (1, 2):
        session.feed(Source(version))
        session.push()
    assert reads == [(1, 2), (2, 4)]


def test_workers_record_their_own_instance_in_provenance(tmp_path: object) -> None:
    def worker(task: Task) -> Partial:
        return Partial(task.size)

    flow = Flow()
    flow.add(worker, trigger_policy=ANY)
    session = flow.session(observability="silent", storage_root=str(tmp_path))
    session.feed_instances({A: Task(1), B: Task(2), C: Task(3)})
    session.push()

    store = session.provenance_store
    assert isinstance(store, CSVProvenanceStore)
    with store.path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    generated = [
        row["instance_id"]
        for row in rows
        if row["event_type"] == "generated" and "Partial" in row["artifact_id"]
    ]
    used = [
        row["instance_id"]
        for row in rows
        if row["event_type"] == "used" and "Task" in row["artifact_id"]
    ]
    assert generated == ["'A'", "'B'", "'C'"]
    assert used == ["'A'", "'B'", "'C'"]


def test_fan_in_inside_a_loop_breaks_the_loop_at_the_sampled_edge() -> None:
    # Workers sample the previous Total; the aggregate collects the workers'
    # outputs. The Sampled edge is the loop's delay, so each push the
    # aggregate sees the fresh outputs of every worker.
    received: list[tuple[int, ...]] = []

    def aggregate(go: Go, partials: Collective[Partial]) -> Total:
        received.append(tuple(sorted(p.value for p in partials)))
        return Total(sum(p.value for p in partials), len(partials))

    def worker(task: Task, previous: Annotated[Total, Sampled]) -> Partial:
        return Partial(task.size + previous.value)

    flow = Flow()
    flow.add(aggregate, trigger_policy=ANY)
    flow.add(worker, trigger_policy=ANY)
    session = flow.session(observability="silent")
    session.feed(Total(0, 0))

    session.feed(Go(1))
    session.feed_instances({A: Task(1), B: Task(2)})
    session.push()
    assert received == [(1, 2)]

    session.feed(Go(2))
    session.feed_instances({A: Task(10), B: Task(20)})
    session.push()
    assert received[-1] == (13, 23)


def test_node_waiting_on_a_loop_reads_the_loops_new_value() -> None:
    log: list[tuple[str, int, int]] = []

    @dataclass(frozen=True)
    class In1:
        v: int

    @dataclass(frozen=True)
    class In2:
        v: int

    @dataclass(frozen=True)
    class SOut:
        v: int

    @dataclass(frozen=True)
    class POut:
        v: int

    @dataclass(frozen=True)
    class QOut:
        v: int

    @dataclass(frozen=True)
    class ROut:
        v: int

    def r(f: In2, a: POut) -> ROut:
        log.append(("r", f.v, a.v))
        return ROut(a.v)

    def s(x: In1) -> SOut:
        return SOut(x.v)

    def p(a: SOut, q: QOut) -> POut:
        return POut(a.v)

    def q(a: POut) -> QOut:
        return QOut(a.v)

    flow = Flow()
    for function in (r, s, p, q):
        flow.add(function, trigger_policy=ANY)
    session = flow.session(observability="silent")
    session.feed(QOut(0))
    session.feed(In1(1))
    session.feed(In2(1))
    session.push()
    log.clear()
    session.feed(In1(2))
    session.feed(In2(2))
    session.push()
    assert log == [("r", 2, 2)]


def test_successful_siblings_of_a_failed_worker_have_finished_trace_events() -> None:
    def worker(task: Task) -> Partial:
        if task.size == 2:
            raise RuntimeError("boom")
        return Partial(task.size)

    flow = Flow()
    flow.add(worker, trigger_policy=ANY)
    session = flow.session(observability="silent")
    session.feed_instances({A: Task(1), B: Task(2)})
    with pytest.raises(RuntimeError):
        session.push()

    worker_events = [
        event.event_type
        for event in session.trace.events
        if event.node_id.endswith(".worker")
    ]
    assert worker_events == ["node_started", "node_finished", "node_started"]


def test_push_from_inside_push_is_rejected() -> None:
    joins: list[tuple[int, int]] = []
    flow = Flow()

    def left(source: Source) -> Left:
        return Left(source.version)

    def right(source: Source) -> Right:
        return Right(source.version)

    def join(left: Left, right: Right) -> Join:
        joins.append((left.version, right.version))
        return Join(left.version, right.version)

    session_holder: dict[str, object] = {}

    def nested_push(value: Left) -> None:
        session = session_holder["session"]
        session.push()  # type: ignore[attr-defined]

    flow.add(left, trigger_policy=ANY, on_output=nested_push)
    flow.add(right, trigger_policy=ANY)
    flow.add(join, trigger_policy=ANY)
    session = flow.session(observability="silent")
    session_holder["session"] = session

    session.feed(Source(1))
    session.push()
    assert joins == [(1, 1)]
    assert len(session.callback_failures) == 1
    assert "in progress" in str(session.callback_failures[0])


def test_fan_in_with_only_a_collective_input_fires_once_after_the_workers() -> None:
    received: list[tuple[int, ...]] = []

    def worker(task: Task) -> Partial:
        return Partial(task.size * 10)

    def aggregate(partials: Collective[Partial]) -> Total:
        received.append(tuple(sorted(p.value for p in partials)))
        return Total(sum(p.value for p in partials), len(partials))

    flow = Flow()
    flow.add(worker)
    flow.add(aggregate)
    session = flow.session(observability="silent")

    session.feed_instances({A: Task(1), B: Task(2), C: Task(3)})
    session.push()
    assert received == [(10, 20, 30)]

    session.push()
    assert received == [(10, 20, 30)], "nothing new: the fan-in does not fire again"
