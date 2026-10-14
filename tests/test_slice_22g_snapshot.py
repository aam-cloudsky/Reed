"""
Focused tests for Slice 22G -- `Snapshot`, `Session.snapshot(self) ->
Snapshot`, and `Session.invoke(self, value: object) -> Snapshot`
(docs/refactor/session_snapshot_decision.md section 5 "`push()` and
`snapshot()`" and section 8 "Target public API reference";
docs/refactor/architectural_invariants.md #24, #25, #33).

These tests exercise the SliceContract's `contracts.expected_to_pass` list
directly through the public `Flow`/`Session`/`Snapshot` surface:

    - `.get(domain_type, default=None)` mirrors `dict.get` exactly: never
      raises, returns the committed domain value or `default`;
    - `__getitem__(domain_type)` mirrors `dict[...]` exactly: raises
      `KeyError` when nothing was committed for that type;
    - `Snapshot` never exposes `ArtifactRecord` anywhere in its public
      surface -- only plain domain values;
    - a `Snapshot` reflects the *full* current repository state at the
      moment it is built, not just whatever the most recent `push()`
      touched -- two separate feed()+push() rounds for two different
      domain types are both visible from one later `snapshot()` call;
    - `Session.invoke(value)` feeds, pushes, and returns a `Snapshot` in
      one call.
"""

from __future__ import annotations

import pytest

from reed import Flow
from reed.execution.artifact_record import ArtifactRecord
from reed.execution.snapshot import Snapshot


class RawReading:
    def __init__(self, value: float) -> None:
        self.value = value


class CalibratedReading:
    def __init__(self, value: float) -> None:
        self.value = value


class Widget:
    def __init__(self, value: int) -> None:
        self.value = value


class Gadget:
    def __init__(self, value: int) -> None:
        self.value = value


class Unrelated:
    pass


def test_snapshot_get_returns_value_or_default():
    flow = Flow()
    session = flow.session()

    session.feed(RawReading(3.0))
    session.push()

    snapshot = session.snapshot()

    got = snapshot.get(RawReading)
    assert isinstance(got, RawReading)
    assert got.value == 3.0

    # Never committed: default default is None.
    assert snapshot.get(Unrelated) is None

    # Never committed: explicit default is returned, unaltered.
    sentinel = object()
    assert snapshot.get(Unrelated, sentinel) is sentinel

    # .get() never raises, regardless of whether the type was committed.
    assert snapshot.get(CalibratedReading, "fallback") == "fallback"


def test_snapshot_getitem_raises_key_error_when_absent():
    flow = Flow()
    session = flow.session()

    session.feed(RawReading(1.0))
    session.push()

    snapshot = session.snapshot()

    # Present: behaves like dict[k].
    got = snapshot[RawReading]
    assert isinstance(got, RawReading)
    assert got.value == 1.0

    # Absent: raises KeyError, exactly like dict[k] would.
    with pytest.raises(KeyError):
        snapshot[Unrelated]


def test_snapshot_never_exposes_artifact_record():
    def calibrate(reading: RawReading) -> CalibratedReading:
        return CalibratedReading(reading.value * 2)

    flow = Flow()
    flow.add(calibrate)
    session = flow.session()

    session.feed(RawReading(5.0))
    session.push()

    snapshot = session.snapshot()

    # .get() unwraps to the plain domain value, never the ArtifactRecord
    # envelope around it.
    got = snapshot.get(CalibratedReading)
    assert isinstance(got, CalibratedReading)
    assert not isinstance(got, ArtifactRecord)

    # __getitem__ does the same.
    got_item = snapshot[RawReading]
    assert isinstance(got_item, RawReading)
    assert not isinstance(got_item, ArtifactRecord)

    # No public attribute or method on Snapshot returns/holds an
    # ArtifactRecord directly. Only .get, __getitem__, .instances (added
    # post-MI-J, see snapshot.py's own module docstring -- the
    # multi-instance-aware complement to .get/__getitem__, unwrapping to
    # plain domain values exactly like they do) and the from_repository
    # constructor (itself a constructor, not an accessor of an existing
    # Snapshot's state) are public. The pin is updated to match rather
    # than left to fail, the same precedent this codebase has already
    # established for this exact kind of additive-surface change (see
    # tests/test_slice_1b_domain_node_description.py's own comment for
    # the original instance of this precedent, Slice 21A's addition of
    # ArtifactDescriptor.input_role).
    public_members = [
        name for name in dir(snapshot) if not name.startswith("_")
    ]
    assert set(public_members) <= {"get", "from_repository", "instances"}

    instances_view = snapshot.instances(RawReading)
    assert not any(isinstance(value, ArtifactRecord) for value in instances_view.values())

    # Nothing reachable off the Snapshot instance itself (its __dict__,
    # the only internal state it holds) is an ArtifactRecord.
    for value in vars(snapshot).values():
        if isinstance(value, dict):
            for inner in value.values():
                assert not isinstance(inner, ArtifactRecord)
        else:
            assert not isinstance(value, ArtifactRecord)


def test_snapshot_reflects_full_current_repository_state_not_just_last_push():
    flow = Flow()
    session = flow.session()

    # Two separate feed()+push() rounds, committing two different types.
    session.feed(Widget(1))
    session.push()

    session.feed(Gadget(2))
    session.push()

    # One snapshot() call, taken after both rounds, sees both -- not just
    # whatever the second (most recent) push() touched.
    snapshot = session.snapshot()

    widget = snapshot[Widget]
    gadget = snapshot[Gadget]
    assert isinstance(widget, Widget) and widget.value == 1
    assert isinstance(gadget, Gadget) and gadget.value == 2

    assert snapshot.get(Widget).value == 1
    assert snapshot.get(Gadget).value == 2


def test_invoke_feeds_pushes_and_returns_a_snapshot():
    fired: list[float] = []

    def calibrate(reading: RawReading) -> CalibratedReading:
        fired.append(reading.value)
        return CalibratedReading(reading.value + 1)

    flow = Flow()
    flow.add(calibrate)
    session = flow.session()

    result = session.invoke(RawReading(9.0))

    # feed() + push() actually happened: the node fired exactly once.
    assert fired == [9.0]

    # invoke() returns a Snapshot, not None and not a bare domain value.
    assert isinstance(result, Snapshot)

    # The returned Snapshot reflects state after the feed+push: both the
    # fed value and the node's committed output are visible.
    assert result[RawReading].value == 9.0
    assert result[CalibratedReading].value == 10.0

    # It matches a snapshot taken separately right after.
    assert session.snapshot().get(CalibratedReading).value == 10.0
