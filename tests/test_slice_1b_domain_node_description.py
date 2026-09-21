"""
Focused tests for Slice 1B (docs/refactor_state.md, Completed Slices).

These tests exist because no target-architecture test can move during
this slice -- 1B is a prerequisite for 1C-1F (see
docs/refactor_priority_order.md, Milestone 1 table). Per
refactor_guide.md #11, this slice adds its own focused test(s) instead.

These tests must actually pass (not xfail): the behavior under test is
implemented in this slice.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from reed.composition.node.artifact_descriptor import ArtifactDescriptor, ArtifactRole
from reed.composition.node.domain_node_description import (
    DomainNodeDescriptionBuilder,
)
from reed.composition.node.node_context import NodeContext


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


class OtherEstimate:
    pass


@dataclass
class TrackerMemory:
    previous_confidence: float | None = None


def build(function):
    return DomainNodeDescriptionBuilder(function).build()


def test_plain_domain_node_produces_consumed_and_produced_descriptors():
    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    description = build(estimate)

    assert description.function is estimate
    assert description.consumed_artifacts == (
        ArtifactDescriptor(
            domain_type=Measurement,
            role=ArtifactRole.CONSUMED,
            name="measurement",
        ),
    )
    assert description.produced_artifact == ArtifactDescriptor(
        domain_type=Estimate,
        role=ArtifactRole.PRODUCED,
        name="return",
    )
    assert description.context is None


def test_node_with_no_consumed_parameters_has_empty_consumed_artifacts():
    def produce() -> Measurement:
        return Measurement(1)

    description = build(produce)

    assert description.consumed_artifacts == ()
    assert description.produced_artifact.domain_type is Measurement
    assert description.produced_artifact.role is ArtifactRole.PRODUCED


def test_node_context_parameter_is_excluded_from_consumed_artifacts():
    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        return Estimate(measurement.value)

    description = build(track)

    assert description.consumed_artifacts == (
        ArtifactDescriptor(
            domain_type=Measurement,
            role=ArtifactRole.CONSUMED,
            name="measurement",
        ),
    )
    assert description.context is not None
    assert description.context.parameter_name == "ctx"
    assert description.context.memory_type is TrackerMemory
    assert description.context.output_type is Estimate


def test_definition_exposes_function_and_name_with_no_flow_local_policy():
    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    definition = DomainNodeDescriptionBuilder(estimate).build_definition()

    assert definition.function is estimate
    assert definition.name == "estimate"
    # DomainNodeDefinition owns no flow-local policy, callback, or
    # execution state (docs/architectural_decision.md, Node Definition) --
    # trigger_policy/on_output ownership belongs to FlowNode (Slice 1C/1E).
    assert not hasattr(definition, "propagation_policy")
    assert not hasattr(definition, "trigger_policy")
    assert not hasattr(definition, "on_output")


def test_builder_reuses_slice_1a_validation_for_self_flow():
    def invalid(measurement: Measurement) -> Measurement:
        return measurement

    with pytest.raises(TypeError, match="self-flow"):
        build(invalid)


def test_builder_reuses_slice_1a_validation_for_context_output_mismatch():
    def invalid(
        ctx: NodeContext[TrackerMemory, OtherEstimate],
        measurement: Measurement,
    ) -> Estimate:
        return Estimate(measurement.value)

    with pytest.raises(TypeError, match="NodeContext.*return"):
        build(invalid)


def test_artifact_descriptor_does_not_expose_artifact_record_concepts():
    # ArtifactDescriptor is identity-only. It must not carry a
    # value/version/provenance field (that is ArtifactRecord, Priority 6,
    # Milestone 2 -- see non-goals.md, "ArtifactRecord Is Not A Blind
    # Parcel Rename").
    #
    # Test Integrity Rule (same treatment Slice 1A gave its own stale
    # NodeContext.__slots__ == () pin -- see
    # test_slice_1a_domain_signature_parsing.py,
    # test_node_context_shell_is_generic_and_detectable): this assertion
    # originally pinned the exact field set to {"domain_type", "role",
    # "name"}. Slice 21A (GitHub issue #21) intentionally adds a fourth,
    # defaulted field, input_role -- an identity-adjacent concept (which
    # role a consumed artifact plays in firing eligibility), not an
    # ArtifactRecord concept (value/version/provenance). The pin is
    # updated to match rather than left to fail; the assertion still
    # proves no value/version/provenance field ever gets added.
    field_names = {field for field in ArtifactDescriptor.__dataclass_fields__}
    assert field_names == {"domain_type", "role", "name", "input_role"}
