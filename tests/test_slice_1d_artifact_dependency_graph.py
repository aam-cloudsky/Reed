"""
Focused tests for Slice 1D (docs/refactor_state.md, Completed Slices).

These tests exist because no target-architecture test can move during
this slice -- see docs/refactor_priority_order.md, Milestone 1 table
("None yet" for 1D). Per refactor_guide.md #11, this slice adds its own
focused test(s) instead.

These tests must actually pass (not xfail): the behavior under test is
implemented in this slice.
"""

from __future__ import annotations

import pytest

from reed.composition.flow.artifact_dependency_graph import (
    ArtifactDependencyGraph,
    DuplicateArtifactProducerError,
    SelfFlowError,
)
from reed.composition.flow.flow_node import FlowNode
from reed.composition.node.domain_node_description import (
    DomainNodeDescriptionBuilder,
)


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


class OtherEstimate:
    def __init__(self, value: int) -> None:
        self.value = value


def flow_node_for(function) -> FlowNode:
    definition = DomainNodeDescriptionBuilder(function).build_definition()
    return FlowNode(definition=definition)


def test_register_tracks_producer_and_consumers():
    def produce() -> Measurement:
        return Measurement(1)

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    producer = flow_node_for(produce)
    consumer = flow_node_for(estimate)

    graph = ArtifactDependencyGraph()
    graph.register(producer)
    graph.register(consumer)

    assert graph.producer_of(Measurement) is producer
    assert graph.producer_of(Estimate) is consumer
    assert graph.consumers_of(Measurement) == frozenset({consumer})
    assert graph.consumers_of(Estimate) == frozenset()


def test_upstream_and_downstream_flow_nodes():
    def produce() -> Measurement:
        return Measurement(1)

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    producer = flow_node_for(produce)
    consumer = flow_node_for(estimate)

    graph = ArtifactDependencyGraph()
    graph.register(producer)
    graph.register(consumer)

    assert graph.upstream_flow_nodes(consumer) == frozenset({producer})
    assert graph.downstream_flow_nodes(producer) == frozenset({consumer})
    assert graph.upstream_flow_nodes(producer) == frozenset()
    assert graph.downstream_flow_nodes(consumer) == frozenset()


def test_duplicate_producer_for_same_artifact_type_is_rejected():
    def first(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    def second(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value + 1)

    graph = ArtifactDependencyGraph()
    graph.register(flow_node_for(first))

    with pytest.raises(DuplicateArtifactProducerError, match="Estimate"):
        graph.register(flow_node_for(second))


def test_reregistering_the_same_flow_node_is_not_a_duplicate():
    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow_node = flow_node_for(estimate)

    graph = ArtifactDependencyGraph()
    graph.register(flow_node)
    graph.register(flow_node)  # must not raise

    assert graph.producer_of(Estimate) is flow_node


def test_self_flow_is_rejected_at_registration_time():
    # Slice 1A's DomainNodeSignatureParser already rejects this at
    # signature-parsing time; this test proves the registry enforces the
    # same invariant independently for a hand-built FlowNode that bypassed
    # the parser (architectural_invariants.md #11).
    def passthrough(measurement: Measurement) -> Measurement:
        return measurement

    definition = DomainNodeDescriptionBuilder.__new__(DomainNodeDescriptionBuilder)
    # Bypass the parser entirely: construct the description by hand so the
    # self-flow check under test is the graph's own, not a re-run of 1A's.
    from reed.composition.node.artifact_descriptor import (
        ArtifactDescriptor,
        ArtifactRole,
    )
    from reed.composition.node.domain_node_description import (
        DomainNodeDefinition,
        DomainNodeDescription,
    )

    hand_built_description = DomainNodeDescription(
        function=passthrough,
        consumed_artifacts=(
            ArtifactDescriptor(
                domain_type=Measurement, role=ArtifactRole.CONSUMED, name="measurement"
            ),
        ),
        produced_artifact=ArtifactDescriptor(
            domain_type=Measurement, role=ArtifactRole.PRODUCED, name="return"
        ),
        context=None,
    )
    hand_built_definition = DomainNodeDefinition(description=hand_built_description)
    flow_node = FlowNode(definition=hand_built_definition)

    graph = ArtifactDependencyGraph()

    with pytest.raises(SelfFlowError, match="Measurement"):
        graph.register(flow_node)


def test_unregister_removes_producer_and_consumer_entries():
    def produce() -> Measurement:
        return Measurement(1)

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    producer = flow_node_for(produce)
    consumer = flow_node_for(estimate)

    graph = ArtifactDependencyGraph()
    graph.register(producer)
    graph.register(consumer)

    graph.unregister(consumer)

    assert graph.producer_of(Measurement) is producer
    assert graph.consumers_of(Measurement) == frozenset()

    graph.unregister(producer)

    assert graph.producer_of(Measurement) is None


def test_distinct_output_artifact_types_allow_parallel_safe_branching():
    # Mirrors the target contract's
    # test_parallel_safe_branching_uses_distinct_output_artifact_types,
    # but at the registry level rather than through Flow.add (Slice 1F).
    def mask(image: Measurement) -> Estimate:
        return Estimate(image.value)

    def enhance(image: Measurement) -> OtherEstimate:
        return OtherEstimate(image.value)

    graph = ArtifactDependencyGraph()
    graph.register(flow_node_for(mask))
    graph.register(flow_node_for(enhance))  # must not raise

    assert graph.producer_of(Estimate) is not None
    assert graph.producer_of(OtherEstimate) is not None

