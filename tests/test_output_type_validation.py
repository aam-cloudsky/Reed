"""A node result must have the node's declared output type (issue #34)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from reed import Flow, NodeContext


@dataclass(frozen=True)
class A:
    value: int


@dataclass(frozen=True)
class C:
    value: int


@dataclass(frozen=True)
class SubC(C):
    pass


@dataclass(frozen=True)
class D:
    value: int


@dataclass
class Memory:
    n: int = 0


def test_wrong_output_type_raises_and_commits_nothing():
    fired: list[C] = []

    def wrong(a: A) -> C:
        return "oops"  # type: ignore[return-value]

    def use(c: C) -> D:
        fired.append(c)
        return D(c.value)

    flow = Flow()
    flow.add(wrong)
    flow.add(use)
    session = flow.session(observability="silent")

    session.feed(A(1))
    with pytest.raises(TypeError, match="wrong.*C.*str"):
        session.push()

    assert session.snapshot().get(str) is None
    assert session.snapshot().get(C) is None
    assert fired == []


def test_a_subclass_of_the_declared_type_is_rejected():
    def node(a: A) -> C:
        return SubC(a.value)

    flow = Flow()
    flow.add(node)
    session = flow.session(observability="silent")

    with pytest.raises(TypeError, match="SubC"):
        session.invoke(A(1))


def test_generic_output_is_checked_by_its_origin():
    def node(a: A) -> list[int]:
        return [a.value]

    flow = Flow()
    flow.add(node)
    session = flow.session(observability="silent")

    assert session.invoke(A(3)).get(list) == [3]


def test_wrong_output_type_restores_node_memory():
    def node(a: A, ctx: NodeContext[Memory, C]) -> C:
        ctx.memory.n += 1
        if a.value < 0:
            return "bad"  # type: ignore[return-value]
        return C(ctx.memory.n)

    flow = Flow()
    flow.add(node)
    session = flow.session(observability="silent")

    session.feed(A(-1))
    with pytest.raises(TypeError):
        session.push()

    assert session.invoke(A(1)).get(C) == C(1)
