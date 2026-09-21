"""
Focused tests for Slice 21D (GitHub issue #21, "Distinguish triggering
inputs from sampled inputs in node firing rules"): zero-TRIGGERING-inputs
registration validation and public exports of InputRole/Sampled.

See
.claude/reed-refactor/run-21D-20260919T144759Z/slice_contract.yaml
for the full objective. These tests must actually pass (not xfail): the
behavior under test is implemented in this slice.
"""

from __future__ import annotations

from typing import Annotated

import pytest

from reed.composition.flow.artifact_dependency_graph import (
    ArtifactDependencyGraph,
    ZeroTriggeringInputsError,
)
from reed.composition.flow.flow_node import FlowNode
from reed.composition.flow.trigger_policy import TriggerPolicy
from reed.composition.node.domain_node_description import (
    DomainNodeDescriptionBuilder,
)
from reed.composition.node.sampled import Sampled


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def flow_node_for(
    function, *, trigger_policy: TriggerPolicy = TriggerPolicy.ALL_INPUTS_CHANGED
) -> FlowNode:
    definition = DomainNodeDescriptionBuilder(function).build_definition()
    return FlowNode(definition=definition, trigger_policy=trigger_policy)


def test_zero_triggering_inputs_raises_at_registration_time():
    def estimate(measurement: Annotated[Measurement, Sampled]) -> Estimate:
        return Estimate(measurement.value)

    flow_node = flow_node_for(
        estimate, trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED
    )

    graph = ArtifactDependencyGraph()

    with pytest.raises(ZeroTriggeringInputsError, match="estimate"):
        graph.register(flow_node)


def test_zero_triggering_inputs_is_allowed_under_manual_trigger_policy():
    def estimate(measurement: Annotated[Measurement, Sampled]) -> Estimate:
        return Estimate(measurement.value)

    flow_node = flow_node_for(estimate, trigger_policy=TriggerPolicy.MANUAL)

    graph = ArtifactDependencyGraph()
    graph.register(flow_node)  # must not raise

    assert graph.producer_of(Estimate) is flow_node


def test_zero_consumed_artifacts_source_node_is_exempt():
    # A pure source/producer node (zero consumed artifacts at all) is a
    # pre-existing, always-valid case unrelated to this validation -- it
    # is never a Run.publish(...) cascade consumer of anything either
    # way, regardless of TriggerPolicy.
    def produce() -> Measurement:
        return Measurement(1)

    flow_node = flow_node_for(produce, trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED)

    graph = ArtifactDependencyGraph()
    graph.register(flow_node)  # must not raise

    assert graph.producer_of(Measurement) is flow_node


def test_public_api_exports_sampled_and_input_role():
    import reed

    assert reed.Sampled is Sampled
    assert reed.InputRole is not None
    assert reed.InputRole.TRIGGERING is not None
    assert reed.InputRole.SAMPLED is not None
