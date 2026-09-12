"""
Focused tests for Slice 1E (docs/refactor_state.md, Completed Slices).

These tests exist because no target-architecture test can move during
this slice -- `TriggerPolicy` has no consumer reachable publicly until
`Flow.add(...)` exists (Slice 1F; see docs/refactor_priority_order.md,
Milestone 1 table). Per refactor_guide.md #11, this slice adds its own
focused test(s) instead.

These tests must actually pass (not xfail): the behavior under test is
implemented in this slice.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from reed.composition.flow.flow_node import FlowNode
from reed.composition.flow.trigger_policy import (
    TriggerPolicy,
    from_propagation_policy,
)
from reed.composition.node.domain_node_description import (
    DomainNodeDescriptionBuilder,
)
from reed.composition.node.propagation_policy import PropagationPolicy


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


def test_trigger_policy_is_a_distinct_enum_from_propagation_policy():
    assert TriggerPolicy is not PropagationPolicy
    assert not set(TriggerPolicy).intersection(set(PropagationPolicy))


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (PropagationPolicy.ANY_DEPENDENCY_CHANGED, TriggerPolicy.ANY_INPUT_CHANGED),
        (PropagationPolicy.ALL_DEPENDENCIES_CHANGED, TriggerPolicy.ALL_INPUTS_CHANGED),
        (PropagationPolicy.MANUAL, TriggerPolicy.MANUAL),
    ],
)
def test_from_propagation_policy_maps_every_old_value(old, new):
    assert from_propagation_policy(old) is new


def test_from_propagation_policy_covers_every_old_enum_member():
    for member in PropagationPolicy:
        # Must not raise KeyError for any current PropagationPolicy value.
        mapped = from_propagation_policy(member)
        assert isinstance(mapped, TriggerPolicy)


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


def test_old_propagation_policy_and_node_definition_are_untouched():
    # docs/non-goals.md, "Compatibility Removal": the old Parcel/decorator
    # path must remain fully intact. Confirm the old enum still exists,
    # still has its original values, and NodeDefinition still defaults to
    # it -- unrelated to TriggerPolicy.
    import dataclasses

    from reed.composition.node.node_definition import NodeDefinition

    assert {member.name for member in PropagationPolicy} == {
        "ANY_DEPENDENCY_CHANGED",
        "ALL_DEPENDENCIES_CHANGED",
        "MANUAL",
    }
    field = next(
        f
        for f in dataclasses.fields(NodeDefinition)
        if f.name == "propagation_policy"
    )
    assert field.default is PropagationPolicy.ALL_DEPENDENCIES_CHANGED
