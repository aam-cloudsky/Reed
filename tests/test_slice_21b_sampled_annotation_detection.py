"""
Focused tests for Slice 21B (GitHub issue #21, "Distinguish triggering
inputs from sampled inputs in node firing rules"): the `Sampled` marker,
the `get_type_hints(include_extras=True)` fix, and detection of
`Annotated[T, Sampled]` wired into `ArtifactDescriptor.input_role`.

See `.claude/reed-refactor/run-21B-20260919T144759Z/slice_contract.yaml`
for the full objective. These tests must actually pass (not xfail): the
behavior under test is implemented in this slice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import pytest

from reed.composition.node.artifact_descriptor import InputRole
from reed.composition.node.domain_node_description import (
    DomainNodeDescriptionBuilder,
)
from reed.composition.node.domain_signature import DomainNodeSignatureParser
from reed.composition.node.node_context import NodeContext
from reed.composition.node.sampled import Sampled


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Baseline:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


@dataclass
class TrackerMemory:
    previous_confidence: float | None = None


def parse(function):
    return DomainNodeSignatureParser(function).parse()


def build(function):
    return DomainNodeDescriptionBuilder(function).build()


def test_annotated_sampled_parameter_sets_input_role_sampled():
    def estimate(
        measurement: Measurement, baseline: Annotated[Baseline, Sampled]
    ) -> Estimate:
        return Estimate(measurement.value + baseline.value)

    description = build(estimate)

    by_name = {artifact.name: artifact for artifact in description.consumed_artifacts}

    assert by_name["measurement"].input_role is InputRole.TRIGGERING
    assert by_name["baseline"].input_role is InputRole.SAMPLED


def test_plain_annotation_without_sampled_still_defaults_to_triggering():
    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    description = build(estimate)

    assert description.consumed_artifacts[0].input_role is InputRole.TRIGGERING


def test_self_flow_compares_the_unwrapped_type_and_accepts_only_a_sampled_self_input():
    # Self-flow correctness is the sharpest risk in this slice: domain-type
    # comparisons must happen on the unwrapped type everywhere, not just
    # in the new Sampled-detection path. Issue #29 changed the rule itself:
    # a Sampled self-input (an explicit unit delay) is now accepted, so
    # this test pins both sides of the unwrapped comparison.
    def accumulate(
        measurement: Baseline, previous: Annotated[Measurement, Sampled]
    ) -> Measurement:
        return previous

    description = build(accumulate)
    by_name = {a.name: a for a in description.consumed_artifacts}
    assert by_name["previous"].domain_type is Measurement
    assert by_name["previous"].input_role is InputRole.SAMPLED

    def invalid(
        baseline: Annotated[Baseline, Sampled], measurement: Measurement
    ) -> Measurement:
        return measurement

    with pytest.raises(TypeError, match="self-flow"):
        parse(invalid)

    with pytest.raises(TypeError, match="self-flow"):
        build(invalid)


def test_node_context_detection_is_unaffected_by_include_extras_change():
    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Annotated[Measurement, Sampled],
    ) -> Estimate:
        return Estimate(measurement.value)

    result = parse(track)

    assert result.context_parameter_name == "ctx"
    assert result.context_memory_type is TrackerMemory
    assert result.context_output_type is Estimate
    assert result.consumed_parameters == (("measurement", Measurement),)
    assert result.sampled_parameter_names == frozenset({"measurement"})


def test_node_context_output_type_check_still_uses_unwrapped_return_type():
    def invalid(
        ctx: NodeContext[TrackerMemory, Baseline],
        measurement: Annotated[Measurement, Sampled],
    ) -> Estimate:
        return Estimate(measurement.value)

    with pytest.raises(TypeError, match="NodeContext.*return"):
        parse(invalid)
