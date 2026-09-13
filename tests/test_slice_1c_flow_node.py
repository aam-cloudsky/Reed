"""
Focused tests for Slice 1C (docs/refactor_state.md, Completed Slices).

These tests exist because no target-architecture test can move during
this slice -- nothing can reach `FlowNode` publicly until `Flow.add(...)`
exists (Slice 1F; see docs/refactor_priority_order.md, Milestone 1
table). Per refactor_guide.md #11, this slice adds its own focused
test(s) instead.

These tests must actually pass (not xfail): the behavior under test is
implemented in this slice.
"""

from __future__ import annotations

from dataclasses import dataclass

from reed.composition.flow.flow_node import FlowNode
from reed.composition.node.domain_node_description import (
    DomainNodeDescriptionBuilder,
)
from reed.composition.node.node_context import NodeContext
from reed.composition.flow.trigger_policy import TriggerPolicy


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


@dataclass
class TrackerMemory:
    previous_confidence: float | None = None


def define(function):
    return DomainNodeDescriptionBuilder(function).build_definition()


def test_flow_node_wraps_definition_and_defaults_trigger_policy():
    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    definition = define(estimate)
    flow_node = FlowNode(definition=definition)

    assert flow_node.definition is definition
    assert flow_node.definition.function is estimate
    assert flow_node.trigger_policy is TriggerPolicy.ALL_INPUTS_CHANGED
    assert flow_node.on_output is None


def test_flow_node_exposes_consumed_and_produced_artifacts():
    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow_node = FlowNode(definition=define(estimate))

    assert flow_node.consumed_artifacts == define(estimate).description.consumed_artifacts
    assert [artifact.domain_type for artifact in flow_node.consumed_artifacts] == [
        Measurement
    ]
    assert flow_node.produced_artifact.domain_type is Estimate


def test_flow_node_exposes_context_descriptor_when_present():
    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        return Estimate(measurement.value)

    flow_node = FlowNode(definition=define(track))

    assert flow_node.context is not None
    assert flow_node.context.memory_type is TrackerMemory
    assert flow_node.context.output_type is Estimate


def test_flow_node_context_is_none_when_absent():
    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow_node = FlowNode(definition=define(estimate))

    assert flow_node.context is None


def test_flow_node_stores_custom_trigger_policy_and_on_output():
    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    def on_output(value: Estimate) -> None:
        pass

    flow_node = FlowNode(
        definition=define(estimate),
        trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED,
        on_output=on_output,
    )

    assert flow_node.trigger_policy is TriggerPolicy.ANY_INPUT_CHANGED
    assert flow_node.on_output is on_output


def test_same_node_definition_may_back_distinct_flow_node_participations():
    # docs/architectural_decision.md, "Flow-Local Node Reference": the
    # same NodeDefinition may eventually participate in different Flows,
    # or more than once. No separate identity field is introduced in this
    # slice (see non-goals.md, "Multiple Registrations of the Same Node
    # Definition") -- the FlowNode instance itself is the flow-local
    # reference, so two participations of the same definition are simply
    # two distinct FlowNode objects.
    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    definition = define(estimate)

    first_participation = FlowNode(definition=definition)
    second_participation = FlowNode(
        definition=definition,
        trigger_policy=TriggerPolicy.MANUAL,
    )

    assert first_participation.definition is second_participation.definition
    assert first_participation is not second_participation
    assert first_participation.trigger_policy != second_participation.trigger_policy


def test_flow_node_has_no_dedicated_identity_field():
    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow_node = FlowNode(definition=define(estimate))

    # Milestone O2, Slice O2b added `instruments` (a tuple of declared
    # Instrument observability definitions) -- this is not the
    # flow-local "identity" field this test guards against (a distinct
    # id/handle a user would supply, e.g. `name=`); `FlowNode.node_id`
    # (Milestone O1, Slice O1c) remains a computed @property, not a
    # stored field, for the same reason. This assertion's actual
    # invariant -- no user-supplied identity field -- is unchanged.
    field_names = {field for field in FlowNode.__dataclass_fields__}
    assert field_names == {
        "definition",
        "trigger_policy",
        "on_output",
        "instruments",
    }
