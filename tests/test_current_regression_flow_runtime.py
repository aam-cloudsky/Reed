from __future__ import annotations

from dataclasses import dataclass

from reed import Parcel, flow, input, node, output


@dataclass
class TextParcel(Parcel):
    text: str


@dataclass
class SizeParcel(Parcel):
    size: int


@dataclass
class DoubledSizeParcel(Parcel):
    size: int


def test_decorator_flow_executes_input_transform_and_output_nodes(capsys):
    @flow
    class SizeFlow:
        @input
        def receive(self, text: str) -> TextParcel:
            return TextParcel(text)

        @node
        def compute(self, text: TextParcel) -> SizeParcel:
            return SizeParcel(len(text.text))

        @output
        def result(self, size: SizeParcel) -> int:
            return size.size

    size_flow = SizeFlow()

    assert size_flow("Hello Reed") == 10
    assert size_flow("abc") == 3

    capsys.readouterr()


def test_decorator_flow_propagates_through_multiple_transform_nodes(capsys):
    @flow
    class DoubleSizeFlow:
        @input
        def receive(self, text: str) -> TextParcel:
            return TextParcel(text)

        @node
        def compute(self, text: TextParcel) -> SizeParcel:
            return SizeParcel(len(text.text))

        @node
        def double(self, size: SizeParcel) -> DoubledSizeParcel:
            return DoubledSizeParcel(size.size * 2)

        @output
        def result(self, doubled: DoubledSizeParcel) -> int:
            return doubled.size

    double_size_flow = DoubleSizeFlow()

    assert double_size_flow("abcd") == 8

    capsys.readouterr()


def test_flow_instances_do_not_share_materialized_nodes(capsys):
    @flow
    class SizeFlow:
        @input
        def receive(self, text: str) -> TextParcel:
            return TextParcel(text)

        @node
        def compute(self, text: TextParcel) -> SizeParcel:
            return SizeParcel(len(text.text))

        @output
        def result(self, size: SizeParcel) -> int:
            return size.size

    first = SizeFlow()
    second = SizeFlow()

    assert first("a") == 1
    assert second("abcd") == 4
    assert first("abcdef") == 6

    assert first is not second
    assert first.logistics is not second.logistics

    capsys.readouterr()

