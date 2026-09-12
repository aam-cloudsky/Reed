"""
Focused tests for `TriggerPolicy`.

`TriggerPolicy` decides whether a `FlowNode` becomes eligible to execute
after input artifact changes (docs/architectural_invariants.md #18-20).
The previous `PropagationPolicy` enum and its `Node`/`NodeDefinition`
execution-eligibility path have been retired along with the rest of the
legacy decorator/Parcel programming model; the migration-bridge coverage
that once lived here (`from_propagation_policy`, `PropagationPolicy`
enum-value parity) was retired with it.
"""

from __future__ import annotations

from reed.composition.flow.flow_node import FlowNode
from reed.composition.flow.trigger_policy import TriggerPolicy
from reed.composition.node.domain_node_description import (
    DomainNodeDescriptionBuilder,
)


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def define(function):
    return DomainNodeDescriptionBuilder(function).build_definition()


def test_trigger_policy_has_target_values():
    assert {member.name for member in TriggerPolicy} == {
        "ANY_INPUT_CHANGED",
        "ALL_INPUTS_CHANGED",
        "MANUAL",
    }


def test_flow_node_trigger_policy_defaults_to_target_enum():
    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow_node = FlowNode(definition=define(estimate))

    assert flow_node.trigger_policy is TriggerPolicy.ALL_INPUTS_CHANGED
    assert isinstance(flow_node.trigger_policy, TriggerPolicy)


def test_flow_node_accepts_explicit_trigger_policy():
    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow_node = FlowNode(
        definition=define(estimate),
        trigger_policy=TriggerPolicy.MANUAL,
    )

    assert flow_node.trigger_policy is TriggerPolicy.MANUAL
