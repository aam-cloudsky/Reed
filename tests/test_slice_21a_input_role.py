"""
Focused tests for Slice 21A (GitHub issue #21, "Distinguish triggering
inputs from sampled inputs in node firing rules"):
`InputRole` enum and `ArtifactDescriptor.input_role` field.

See `.claude/reed-refactor/run-21A-20260919T144759Z/slice_contract.yaml`
for the full objective. This slice is purely additive: no detection
wiring (Slice 21B) and no `Session` eligibility change (Slice 21C) happen
here. These tests must actually pass (not xfail): the behavior under
test is implemented in this slice.
"""

from __future__ import annotations

import pytest

from reed.composition.node.artifact_descriptor import (
    ArtifactDescriptor,
    ArtifactRole,
    InputRole,
)


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


def test_input_role_defaults_to_triggering_for_existing_construction():
    # Every pre-existing call site constructs ArtifactDescriptor with
    # only domain_type/role/name -- input_role must default to
    # InputRole.TRIGGERING, today's only behavior, so none of them
    # change meaning.
    descriptor = ArtifactDescriptor(
        domain_type=Measurement, role=ArtifactRole.CONSUMED, name="measurement"
    )

    assert descriptor.input_role is InputRole.TRIGGERING


def test_input_role_can_be_set_to_sampled_explicitly():
    descriptor = ArtifactDescriptor(
        domain_type=Measurement,
        role=ArtifactRole.CONSUMED,
        name="measurement",
        input_role=InputRole.SAMPLED,
    )

    assert descriptor.input_role is InputRole.SAMPLED


def test_artifact_descriptor_remains_a_frozen_hashable_dataclass():
    # ArtifactDescriptor is used as a dict/set member elsewhere in the
    # composition layer (e.g. as an element of a FlowNode's
    # consumed_artifacts tuple, hashed via frozenset construction in
    # ArtifactDependencyGraph). Adding input_role must not break that.
    triggering = ArtifactDescriptor(
        domain_type=Measurement, role=ArtifactRole.CONSUMED, name="measurement"
    )
    same_triggering = ArtifactDescriptor(
        domain_type=Measurement,
        role=ArtifactRole.CONSUMED,
        name="measurement",
        input_role=InputRole.TRIGGERING,
    )
    sampled = ArtifactDescriptor(
        domain_type=Measurement,
        role=ArtifactRole.CONSUMED,
        name="measurement",
        input_role=InputRole.SAMPLED,
    )

    with pytest.raises(AttributeError):
        triggering.input_role = InputRole.SAMPLED  # frozen: must not allow mutation

    assert hash(triggering) == hash(same_triggering)
    assert triggering == same_triggering
    assert triggering != sampled
    assert hash(triggering) != hash(sampled) or triggering != sampled
    assert {triggering, same_triggering, sampled} == {triggering, sampled}
