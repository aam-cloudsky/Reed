"""
A failed superstep leaves no node-memory transition behind (issue #34):
memory is copied before each worker runs and restored if any worker of the
superstep raises.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

import pytest

from reed import Flow, NodeContext


@dataclass(frozen=True)
class Tick:
    value: int


@dataclass(frozen=True)
class Count:
    value: int


@dataclass(frozen=True)
class Checked:
    value: int


@dataclass
class CounterMemory:
    n: int = 0


def _flow(fail: dict[str, bool]) -> Flow:
    def counter(tick: Tick, ctx: NodeContext[CounterMemory, Count]) -> Count:
        ctx.memory.n += 1
        return Count(ctx.memory.n)

    def check(tick: Tick) -> Checked:
        if fail["on"]:
            raise ValueError("boom")
        return Checked(tick.value)

    flow = Flow()
    flow.add(counter)
    flow.add(check)
    return flow


def test_memory_of_a_sibling_worker_is_restored_when_the_superstep_fails():
    fail = {"on": True}
    session = _flow(fail).session(observability="silent")

    session.feed(Tick(1))
    with pytest.raises(ValueError):
        session.push()
    assert session.snapshot().get(Count) is None

    fail["on"] = False
    session.feed(Tick(1))
    session.push()

    assert session.snapshot().get(Count) == Count(1)


def test_memory_after_a_successful_superstep_is_kept():
    session = _flow({"on": False}).session(observability="silent")

    session.invoke(Tick(1))
    session.invoke(Tick(2))

    assert session.snapshot().get(Count) == Count(2)


def test_memory_of_the_failing_worker_is_restored():
    calls = {"n": 0}

    def flaky(tick: Tick, ctx: NodeContext[CounterMemory, Count]) -> Count:
        ctx.memory.n += 1
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("first call fails")
        return Count(ctx.memory.n)

    flow = Flow()
    flow.add(flaky)
    session = flow.session(observability="silent")

    session.feed(Tick(1))
    with pytest.raises(ValueError):
        session.push()
    session.feed(Tick(1))
    session.push()

    assert session.snapshot().get(Count) == Count(1)


@dataclass
class LockedMemory:
    lock: threading.Lock = field(default_factory=threading.Lock)


def test_memory_that_cannot_be_copied_raises_a_clear_type_error():
    def node(tick: Tick, ctx: NodeContext[LockedMemory, Count]) -> Count:
        return Count(tick.value)

    flow = Flow()
    flow.add(node)
    session = flow.session(observability="silent")
    session.invoke(Tick(1))  # memory is created on the first firing

    session.feed(Tick(2))
    with pytest.raises(TypeError, match="deepcopy"):
        session.push()
