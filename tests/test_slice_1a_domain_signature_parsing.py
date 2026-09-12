"""
Focused tests for Slice 1A (docs/refactor_state.md, Current Slice).

These tests exercise the new, additive domain-signature parsing and the
minimal `NodeContext` shell directly. They exist because no test in
`tests/test_target_architecture_contract.py` can move during this slice --
every target test in that file goes through `flow.add(...)`, which does
not exist until Slice 1F (see docs/refactor_priority_order.md, "Why no
target test moves before 1F"). Per refactor_guide.md #11, this slice adds
its own focused test(s) instead.

These tests must actually pass (not xfail): the behavior under test is
implemented in this slice.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from reed.composition.node.domain_signature import (
    DomainNodeSignatureParser,
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


def parse(function):
    return DomainNodeSignatureParser(function).parse()


def test_parses_plain_domain_typed_signature():
    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    result = parse(estimate)

    assert result.function is estimate
    assert result.consumed_parameters == (("measurement", Measurement),)
    assert result.produced_type is Estimate
    assert result.context_parameter_name is None
    assert result.context_memory_type is None
    assert result.context_output_type is None


def test_node_context_is_detected_and_excluded_from_consumed_parameters():
    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        return Estimate(measurement.value)

    result = parse(track)

    assert result.consumed_parameters == (("measurement", Measurement),)
    assert result.context_parameter_name == "ctx"
    assert result.context_memory_type is TrackerMemory
    assert result.context_output_type is Estimate


def test_node_context_output_type_must_match_return_type():
    def invalid(
        ctx: NodeContext[TrackerMemory, OtherEstimate],
        measurement: Measurement,
    ) -> Estimate:
        return Estimate(measurement.value)

    with pytest.raises(TypeError, match="NodeContext.*return"):
        parse(invalid)


def test_self_flow_signature_is_rejected():
    def invalid(measurement: Measurement) -> Measurement:
        return measurement

    with pytest.raises(TypeError, match="self-flow"):
        parse(invalid)


def test_multiple_node_context_parameters_are_rejected():
    def invalid(
        ctx_one: NodeContext[TrackerMemory, Estimate],
        ctx_two: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        return Estimate(measurement.value)

    with pytest.raises(TypeError, match="more than one NodeContext"):
        parse(invalid)


def test_node_context_shell_is_generic_and_detectable():
    # NodeContext is a real, importable, generic type at this slice --
    # Slice 1A only requires that the type is detectable via
    # typing.get_origin(...), which the tests above already exercise
    # indirectly; this test documents/pins the shell's genericness.
    #
    # This test originally also pinned `NodeContext.__slots__ == ()` --
    # "no runtime behavior until Milestone 2". Milestone 2, Slice 2D is
    # exactly the slice that gives NodeContext real runtime behavior
    # (`ctx.memory`/`ctx.last_output`), so that assertion is now stale by
    # design and has been removed here (Test Integrity Rule) rather than
    # left to fail -- see tests/test_slice_2d_node_context.py for
    # NodeContext's dedicated runtime-behavior coverage.
    parametrized = NodeContext[TrackerMemory, Estimate]
    assert parametrized is not None


def test_missing_parameter_annotation_is_rejected():
    def invalid(measurement) -> Estimate:
        return Estimate(measurement.value)

    with pytest.raises(TypeError, match="must have a type annotation"):
        parse(invalid)


def test_missing_return_annotation_is_rejected():
    def invalid(measurement: Measurement):
        return Estimate(measurement.value)

    with pytest.raises(TypeError, match="must declare a return type"):
        parse(invalid)


def test_async_node_function_is_rejected():
    async def invalid(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    with pytest.raises(TypeError, match="cannot be async"):
        parse(invalid)


def test_variadic_parameters_are_rejected():
    def invalid(*values: Measurement) -> Estimate:
        return Estimate(len(values))

    with pytest.raises(TypeError, match=r"cannot declare \*args or \*\*kwargs"):
        parse(invalid)
