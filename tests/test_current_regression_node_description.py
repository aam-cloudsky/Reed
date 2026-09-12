from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest

from reed.composition.node.node_builder import NodeDescriptionBuilder
from reed.composition.node.node_definition import NodeKind
from reed.synchronization.parcel.parcel import Parcel


@dataclass
class InputParcel(Parcel):
    value: int


@dataclass
class OtherInputParcel(Parcel):
    value: int


@dataclass
class OutputParcel(Parcel):
    value: int


@dataclass
class OtherOutputParcel(Parcel):
    value: int


def build_transform_description(function):
    return NodeDescriptionBuilder(function=function, kind=NodeKind.TRANSFORM).build()


def test_transform_description_keeps_current_parcel_contract():
    def transform(value: InputParcel, factor: int) -> OutputParcel:
        return OutputParcel(value.value * factor)

    description = build_transform_description(transform)

    assert description.function is transform
    assert description.kind is NodeKind.TRANSFORM
    assert description.consumed_parameters == (("value", InputParcel),)
    assert description.external_parameters == (("factor", int),)
    assert description.produced_types == (OutputParcel,)
    assert description.external_return_type is None


def test_transform_description_supports_fixed_tuple_of_produced_parcels():
    def split(value: InputParcel) -> tuple[OutputParcel, OtherOutputParcel]:
        return OutputParcel(value.value), OtherOutputParcel(value.value)

    description = build_transform_description(split)

    assert description.consumed_parameters == (("value", InputParcel),)
    assert description.produced_types == (OutputParcel, OtherOutputParcel)
    assert description.external_return_type is None


def test_output_description_keeps_external_return_type():
    def result(value: OutputParcel) -> int:
        return value.value

    description = NodeDescriptionBuilder(
        function=result,
        kind=NodeKind.OUTPUT,
    ).build()

    assert description.consumed_parameters == (("value", OutputParcel),)
    assert description.produced_types == ()
    assert description.external_return_type is int


def test_input_description_allows_external_parameters_and_requires_parcel_output():
    def receive(value: int) -> InputParcel:
        return InputParcel(value)

    description = NodeDescriptionBuilder(
        function=receive,
        kind=NodeKind.INPUT,
    ).build()

    assert description.consumed_parameters == ()
    assert description.external_parameters == (("value", int),)
    assert description.produced_types == (InputParcel,)


def test_missing_parameter_annotation_is_rejected():
    def transform(value) -> OutputParcel:
        return OutputParcel(value.value)

    with pytest.raises(TypeError, match="must have a type annotation"):
        build_transform_description(transform)


def test_missing_return_annotation_is_rejected():
    def transform(value: InputParcel):
        return OutputParcel(value.value)

    with pytest.raises(TypeError, match="must declare a return type"):
        build_transform_description(transform)


def test_optional_parcel_dependency_is_rejected():
    def transform(value: Optional[InputParcel]) -> OutputParcel:
        return OutputParcel(0 if value is None else value.value)

    with pytest.raises(TypeError, match=r"Optional\[Parcel\] is not supported"):
        build_transform_description(transform)


def test_variadic_parameters_are_rejected():
    def transform(*values: InputParcel) -> OutputParcel:
        return OutputParcel(len(values))

    with pytest.raises(TypeError, match=r"cannot declare \*args or \*\*kwargs"):
        build_transform_description(transform)


def test_tuple_return_must_only_contain_parcel_types():
    def transform(value: InputParcel) -> tuple[OutputParcel, int]:
        return OutputParcel(value.value), value.value

    with pytest.raises(TypeError, match="must inherit from Parcel"):
        build_transform_description(transform)


def test_transform_without_parcel_input_is_rejected():
    def transform(value: int) -> OutputParcel:
        return OutputParcel(value)

    with pytest.raises(TypeError, match="must consume at least one Parcel"):
        build_transform_description(transform)


def test_input_node_cannot_consume_parcels():
    def receive(value: InputParcel) -> OutputParcel:
        return OutputParcel(value.value)

    with pytest.raises(TypeError, match="cannot consume Parcels"):
        NodeDescriptionBuilder(function=receive, kind=NodeKind.INPUT).build()


def test_transform_node_cannot_have_external_return_type():
    def transform(value: InputParcel) -> int:
        return value.value

    with pytest.raises(TypeError, match="must produce at least one Parcel"):
        build_transform_description(transform)


def test_duplicate_consumed_parcel_type_is_rejected():
    def transform(left: InputParcel, right: InputParcel) -> OutputParcel:
        return OutputParcel(left.value + right.value)

    with pytest.raises(TypeError, match="cannot consume the same Parcel type"):
        build_transform_description(transform)


def test_duplicate_produced_parcel_type_is_rejected():
    def transform(
        left: InputParcel,
        right: OtherInputParcel,
    ) -> tuple[OutputParcel, OutputParcel]:
        return OutputParcel(left.value), OutputParcel(right.value)

    with pytest.raises(TypeError, match="cannot produce the same Parcel type"):
        build_transform_description(transform)
