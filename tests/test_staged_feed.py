"""
feed(), feed_instances() and remove_instance() stage operations that the
next push() applies (issue #34).

The rules: the last operation on a (type, instance) key wins and there is
no queue; push() works on what was staged before it started; a value fed
while a push() is running waits for the next push() and is never lost.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import pytest

from reed import Flow, InstanceKey


@dataclass(frozen=True)
class A:
    value: str


@dataclass(frozen=True)
class B:
    value: str


def _flow_seeing(seen: list[str]) -> Flow:
    def node(a: A) -> B:
        seen.append(a.value)
        return B(a.value)

    flow = Flow()
    flow.add(node)
    return flow


def test_last_feed_before_push_wins_and_is_committed_once():
    seen: list[str] = []
    session = _flow_seeing(seen).session(observability="silent")

    session.feed(A("A1-1"))
    session.feed(A("A1-2"))
    session.push()

    assert seen == ["A1-2"]
    assert session.snapshot().get(B) == B("A1-2")
    assert session.repository.get_artifact_record(A).version.number == 1


def test_feed_push_feed_push_propagates_both_values():
    seen: list[str] = []
    session = _flow_seeing(seen).session(observability="silent")

    session.feed(A("A1-1"))
    session.push()
    session.feed(A("A1-2"))
    session.push()

    assert seen == ["A1-1", "A1-2"]
    assert session.snapshot().get(B) == B("A1-2")


def test_snapshot_does_not_show_a_staged_value():
    session = _flow_seeing([]).session(observability="silent")

    session.feed(A("A1-1"))

    assert session.snapshot().get(A) is None
    assert session.repository.get_artifact_record(A) is None


def test_invoke_is_feed_push_snapshot():
    seen: list[str] = []
    session = _flow_seeing(seen).session(observability="silent")

    snapshot = session.invoke(A("A1-1"))

    assert seen == ["A1-1"]
    assert snapshot.get(B) == B("A1-1")


def test_feed_from_inside_a_node_waits_for_the_next_push():
    seen: list[str] = []
    holder: dict[str, object] = {}

    def node(a: A) -> B:
        seen.append(a.value)
        if a.value == "A1-1":
            holder["session"].feed(A("A1-2"))
        return B(a.value)

    flow = Flow()
    flow.add(node)
    session = flow.session(observability="silent")
    holder["session"] = session

    session.feed(A("A1-1"))
    session.push()
    assert seen == ["A1-1"]
    assert session.snapshot().get(A) == A("A1-1")

    session.push()
    assert seen == ["A1-1", "A1-2"]
    assert session.snapshot().get(B) == B("A1-2")


def test_feed_from_on_output_waits_for_the_next_push():
    seen: list[str] = []
    holder: dict[str, object] = {}

    def node(a: A) -> B:
        seen.append(a.value)
        return B(a.value)

    def on_output(b: B) -> None:
        if b.value == "A1-1":
            holder["session"].feed(A("A1-2"))

    flow = Flow()
    flow.add(node, on_output=on_output)
    session = flow.session(observability="silent")
    holder["session"] = session

    session.feed(A("A1-1"))
    session.push()
    session.push()

    assert seen == ["A1-1", "A1-2"]


def test_feed_from_another_thread_during_push_is_not_lost():
    seen: list[str] = []
    started = threading.Event()
    release = threading.Event()

    def node(a: A) -> B:
        seen.append(a.value)
        if a.value == "A1-1":
            started.set()
            assert release.wait(5)
        return B(a.value)

    flow = Flow()
    flow.add(node)
    session = flow.session(observability="silent")

    session.feed(A("A1-1"))
    pusher = threading.Thread(target=session.push)
    pusher.start()
    assert started.wait(5)
    session.feed(A("A1-2"))  # must not block on the running push()
    release.set()
    pusher.join(5)

    assert seen == ["A1-1"]
    assert session.snapshot().get(B) == B("A1-1")

    session.push()
    assert seen == ["A1-1", "A1-2"]
    assert session.snapshot().get(B) == B("A1-2")


def test_feed_instances_rejects_mixed_types_immediately():
    session = Flow().session(observability="silent")

    with pytest.raises(TypeError):
        session.feed_instances({InstanceKey(key="x"): A("a"), InstanceKey(key="y"): B("b")})


def test_feed_instances_is_staged_per_instance():
    session = Flow().session(observability="silent")
    x, y = InstanceKey(key="x"), InstanceKey(key="y")

    session.feed_instances({x: A("x1"), y: A("y1")})
    session.feed_instances({x: A("x2")})
    assert session.snapshot().instances(A) == {}

    session.push()
    assert session.snapshot().instances(A) == {x: A("x2"), y: A("y1")}


def test_remove_after_feed_of_the_same_instance_wins():
    session = Flow().session(observability="silent")
    x = InstanceKey(key="x")

    session.feed_instances({x: A("x1")})
    assert session.remove_instance(A, x) is True
    session.push()

    assert session.repository.get_artifact_record(A, instance=x) is None


def test_feed_after_remove_of_the_same_instance_wins():
    session = Flow().session(observability="silent")
    x = InstanceKey(key="x")

    session.feed_instances({x: A("x1")})
    session.push()
    assert session.remove_instance(A, x) is True
    session.feed_instances({x: A("x2")})
    session.push()

    assert session.snapshot().get(A, instance=x) == A("x2")


def test_remove_instance_reports_false_for_an_unknown_pair():
    session = Flow().session(observability="silent")

    assert session.remove_instance(A, InstanceKey(key="nobody")) is False
