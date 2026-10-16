"""
Issue #29: self-flow through a `Sampled` self-input (unit delay).

A node may consume the type it produces only through
`Annotated[T, Sampled]`. That input reads the value committed before the
firing (z^-1, Lustre's `pre`) and never triggers the node. A triggering
self-input is still rejected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import pytest

from reed import Collective, Flow, InstanceKey, NodeContext, Sampled, TriggerPolicy
from reed.composition.flow.artifact_dependency_graph import (
    ArtifactDependencyGraph,
    SelfFlowError,
)
from reed.composition.flow.flow_node import FlowNode
from reed.composition.node.artifact_descriptor import (
    ArtifactDescriptor,
    ArtifactRole,
    InputRole,
)
from reed.composition.node.domain_node_description import (
    DomainNodeDefinition,
    DomainNodeDescription,
)


@dataclass(frozen=True)
class Tick:
    n: int


@dataclass(frozen=True)
class Count:
    value: int


@dataclass(frozen=True)
class Position:
    x: float


def _counter_flow(seen: list[int]) -> Flow:
    def counter(tick: Tick, previous: Annotated[Count, Sampled]) -> Count:
        seen.append(previous.value)
        return Count(previous.value + 1)

    flow = Flow()
    flow.add(counter)
    return flow


def test_a_sampled_self_input_is_accepted():
    _counter_flow([])


def test_a_triggering_self_input_is_rejected():
    def counter(tick: Tick, previous: Count) -> Count:
        return previous

    with pytest.raises(TypeError, match="self-flow"):
        Flow().add(counter)


def _hand_built_node(role: InputRole) -> FlowNode:
    # Built by hand, bypassing the parser, so the check under test is the
    # graph's own (same approach as test_slice_1d_artifact_dependency_graph).
    def counter(tick: Tick, previous: Count) -> Count:
        return previous

    description = DomainNodeDescription(
        function=counter,
        consumed_artifacts=(
            ArtifactDescriptor(
                domain_type=Tick, role=ArtifactRole.CONSUMED, name="tick"
            ),
            ArtifactDescriptor(
                domain_type=Count,
                role=ArtifactRole.CONSUMED,
                name="previous",
                input_role=role,
            ),
        ),
        produced_artifact=ArtifactDescriptor(
            domain_type=Count, role=ArtifactRole.PRODUCED, name="return"
        ),
        context=None,
    )
    return FlowNode(definition=DomainNodeDefinition(description=description))


def test_the_graph_accepts_only_a_sampled_self_input_independently_of_the_parser():
    with pytest.raises(SelfFlowError, match="Count"):
        ArtifactDependencyGraph().register(_hand_built_node(InputRole.TRIGGERING))

    graph = ArtifactDependencyGraph()
    graph.register(_hand_built_node(InputRole.SAMPLED))
    assert graph.producer_of(Count) is not None


def test_the_self_input_reads_the_value_committed_before_the_firing():
    seen: list[int] = []
    session = _counter_flow(seen).session(observability="silent")
    session.feed(Count(0))

    for n in range(3):
        session.feed(Tick(n))
        session.push()

    assert seen == [0, 1, 2]
    assert session.snapshot()[Count] == Count(3)


def test_the_node_does_not_fire_before_an_initial_state_exists():
    seen: list[int] = []
    session = _counter_flow(seen).session(observability="silent")

    session.feed(Tick(0))
    session.push()

    assert seen == []


def test_its_own_commit_never_triggers_the_node_again():
    seen: list[int] = []
    session = _counter_flow(seen).session(observability="silent")
    session.feed(Count(0))
    session.feed(Tick(0))
    session.push()

    session.push()
    session.push()

    assert seen == [0]


def test_feed_overwrites_the_state_and_leaves_last_output_alone():
    last_outputs: list[Count | None] = []

    def counter(
        ctx: NodeContext[None, Count],
        tick: Tick,
        previous: Annotated[Count, Sampled],
    ) -> Count:
        last_outputs.append(ctx.last_output)
        return Count(previous.value + 1)

    flow = Flow()
    flow.add(counter)
    session = flow.session(observability="silent")
    session.feed(Count(0))
    session.feed(Tick(0))
    session.push()

    session.feed(Count(100))
    session.feed(Tick(1))
    session.push()

    # The Sampled self-input reads the current value of the type (100,
    # fed); last_output is what this node produced (1).
    assert session.snapshot()[Count] == Count(101)
    assert last_outputs == [None, Count(1)]


def test_a_sampled_collective_self_input_gives_jacobi_consensus():
    # Every instance reads the positions committed before the superstep,
    # so all three see (0, 30, 60) and agree on 30. Gauss-Seidel (each
    # instance reading the ones already updated in the same push) would
    # give (30, 40, 43.3).
    def consensus(
        tick: Tick, everyone: Annotated[Collective[Position], Sampled]
    ) -> Position:
        return Position(sum(p.x for p in everyone) / len(everyone))

    flow = Flow()
    flow.add(consensus)
    session = flow.session(observability="silent")
    keys = [InstanceKey(key=k) for k in ("a", "b", "c")]
    session.feed_instances(
        dict(zip(keys, (Position(0.0), Position(30.0), Position(60.0))))
    )
    session.feed_instances({key: Tick(1) for key in keys})
    session.push()

    positions = session.snapshot().instances(Position)
    assert [positions[key] for key in keys] == [Position(30.0)] * 3


def test_a_sampled_collective_input_does_not_trigger():
    @dataclass(frozen=True)
    class Summary:
        count: int

    calls: list[int] = []

    def summary(
        tick: Tick, everyone: Annotated[Collective[Position], Sampled]
    ) -> Summary:
        calls.append(len(everyone))
        return Summary(len(everyone))

    flow = Flow()
    # ANY_INPUT_CHANGED: any triggering arrival alone would fire it.
    flow.add(summary, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    session = flow.session(observability="silent")
    session.feed(Tick(0))
    session.push()
    assert calls == [0]

    # New instances of Position arrive, but no Tick: a Sampled collective
    # is read at the next firing, it does not cause one.
    keys = [InstanceKey(key=k) for k in ("a", "b")]
    session.feed_instances(dict(zip(keys, (Position(0.0), Position(10.0)))))
    session.push()
    assert calls == [0]

    session.feed(Tick(1))
    session.push()
    assert calls == [0, 2]


def test_a_sampled_collective_input_never_enters_the_freshness_map():
    # Rule of Sampled inputs (Session._record_input): they update the last
    # known values but are never marked fresh. Not observable through
    # firing (the policy only looks at triggering types), so this checks
    # the freshness map itself.
    def summary(
        tick: Tick, everyone: Annotated[Collective[Position], Sampled]
    ) -> Count:
        return Count(len(everyone))

    flow = Flow()
    flow.add(summary)
    session = flow.session(observability="silent")
    session.feed_instances({InstanceKey(key="a"): Position(1.0)})

    fresh = session._fresh_since_last_firing  # pyright: ignore[reportPrivateUsage]
    assert all(
        Position not in types
        for by_instance in fresh.values()
        for types in by_instance.values()
    )


def test_consuming_the_same_type_twice_is_rejected():
    def nudge(
        tick: Tick,
        me: Annotated[Position, Sampled],
        everyone: Annotated[Collective[Position], Sampled],
    ) -> Count:
        return Count(0)

    with pytest.raises(TypeError, match="twice"):
        Flow().add(nudge)
