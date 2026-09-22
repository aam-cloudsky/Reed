"""
Focused tests for Slice 22B (`ArtifactOrigin` enum +
`ArtifactProvenance.origin` field).

See `docs/refactor/session_snapshot_decision.md` section 6 ("Unified
versioning and `ArtifactOrigin`") for the accepted design this slice
implements, and `docs/refactor/architectural_invariants.md` #29
(`ArtifactOrigin` has exactly two values, every commit path sets it
explicitly, no default).

Covers exactly what this slice adds:

    1. `ArtifactOrigin` has exactly two members, `NODE` and `EXTERNAL`
       (invariant 29) -- no third `PENDING`/`UNSET` value.
    2. `ArtifactProvenance.advance(...)`'s `origin` parameter is
       required and keyword-only, with no default -- omitting it raises
       `TypeError`.
    3. `NodeSession.wrap(...)` -- the one current call site -- sets
       `origin=ArtifactOrigin.NODE` on the resulting `ArtifactRecord`'s
       provenance.

This slice is purely additive to the data shape (no other field is
removed or renamed, and `ArtifactRecord.advance(value, ...)` -- the
value-mutation method -- is explicitly out of scope; that is Slice 22C's
job), so no existing behavior is exercised here beyond the new field/
parameter itself.
"""

from __future__ import annotations

import pytest

from reed.execution.artifact_record import (
    ArtifactOrigin,
    ArtifactProvenance,
    ArtifactVersion,
)


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


def test_artifact_origin_has_exactly_two_members():
    assert {member.name for member in ArtifactOrigin} == {"NODE", "EXTERNAL"}
    assert len(ArtifactOrigin) == 2


def test_artifact_origin_members_are_distinct():
    assert ArtifactOrigin.NODE is not ArtifactOrigin.EXTERNAL
    assert ArtifactOrigin.NODE.value != ArtifactOrigin.EXTERNAL.value


def test_advance_requires_origin_keyword_argument():
    provenance = ArtifactProvenance()

    with pytest.raises(TypeError):
        provenance.advance()  # type: ignore[call-arg]


def test_advance_rejects_origin_as_a_positional_argument():
    provenance = ArtifactProvenance()

    with pytest.raises(TypeError):
        provenance.advance(ArtifactOrigin.NODE)  # type: ignore[misc]


def test_advance_with_origin_keyword_sets_origin_and_advances_version():
    provenance = ArtifactProvenance()

    provenance.advance(origin=ArtifactOrigin.EXTERNAL)

    assert provenance.origin is ArtifactOrigin.EXTERNAL
    assert provenance.version == ArtifactVersion.initial()


def test_fresh_artifact_provenance_has_no_origin_until_advanced():
    provenance = ArtifactProvenance()

    assert provenance.origin is None


def test_origin_is_overwritten_on_every_advance_call():
    provenance = ArtifactProvenance()

    provenance.advance(origin=ArtifactOrigin.NODE)
    assert provenance.origin is ArtifactOrigin.NODE

    provenance.advance(origin=ArtifactOrigin.EXTERNAL)
    assert provenance.origin is ArtifactOrigin.EXTERNAL


def test_copy_carries_origin_forward():
    provenance = ArtifactProvenance()
    provenance.advance(origin=ArtifactOrigin.EXTERNAL)

    copied = provenance.copy()

    assert copied.origin is ArtifactOrigin.EXTERNAL


def test_node_session_wrap_sets_origin_node():
    from reed import Flow

    def produce_measurement() -> Measurement:
        return Measurement(1)

    flow = Flow()
    flow.add(produce_measurement)
    session = flow.session()
    node_session = session.node_session(produce_measurement)

    record = node_session.wrap(Measurement(1))

    assert record.provenance.origin is ArtifactOrigin.NODE


def test_node_session_wrap_sets_origin_node_on_every_repeated_firing():
    from reed import Flow

    def produce_measurement() -> Measurement:
        return Measurement(1)

    flow = Flow()
    flow.add(produce_measurement)
    session = flow.session()
    node_session = session.node_session(produce_measurement)

    first_record = node_session.wrap(Measurement(1))
    second_record = node_session.wrap(Measurement(2))

    assert first_record.provenance.origin is ArtifactOrigin.NODE
    assert second_record.provenance.origin is ArtifactOrigin.NODE
