"""
Slice 22C -- `ArtifactRecord.advance(value, *, origin, producer=None)`.

Focused tests for the new in-place mutation method itself
(`docs/refactor/session_snapshot_decision.md` section 7,
`docs/refactor/architectural_invariants.md` #27/#28). The broader,
deliberately-reversed regression test lives in
`tests/test_observability_o7b_provenance_version.py`
(`test_earlier_retrieved_records_now_observe_a_later_advance_in_place`);
these tests exercise `.advance()` directly, without going through
`Flow`/`Session` at all.

This slice does NOT wire `NodeSession.wrap()` to call `.advance()` --
that unification is slice 22D. These tests construct `ArtifactRecord`s
directly, exactly as `tests/test_slice_2c_artifact_record.py` already
does for plain construction.
"""

from __future__ import annotations

import pytest

from reed.execution.artifact_record import (
    ArtifactOrigin,
    ArtifactRecord,
    ArtifactVersion,
)


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def test_advance_mutates_value_and_provenance_in_place():
    record = ArtifactRecord(value=Measurement(1))
    assert record.version == ArtifactVersion.pending()
    assert record.provenance.origin is None

    same_object = record  # an alias, not a copy -- see glossary.md "Aliasing"

    record.advance(Measurement(2), origin=ArtifactOrigin.NODE)

    # In-place mutation (glossary.md "In-place mutation"): `record` was
    # not replaced by a new object, so `same_object` -- retrieved BEFORE
    # the advance() call -- is the identical object and observes the
    # mutation too.
    assert same_object is record
    assert same_object.value is record.value
    assert record.value.value == 2
    assert record.version == ArtifactVersion.initial()
    assert record.provenance.origin is ArtifactOrigin.NODE

    record.advance(Measurement(3), origin=ArtifactOrigin.EXTERNAL)

    assert same_object.value.value == 3
    assert same_object.version.number == 2
    assert same_object.provenance.origin is ArtifactOrigin.EXTERNAL


def test_advance_sets_producer_only_when_given():
    record = ArtifactRecord(value=Measurement(1))

    record.advance(Measurement(2), origin=ArtifactOrigin.NODE)
    assert record.provenance.producer is None

    sentinel_producer = object()
    record.advance(Measurement(3), origin=ArtifactOrigin.NODE, producer=sentinel_producer)
    assert record.provenance.producer is sentinel_producer

    # Omitting `producer` on a later call does not clear a previously set
    # one (mirrors `ArtifactProvenance.advance(...)`'s own producer
    # mechanics -- see artifact_record.py module docstring).
    record.advance(Measurement(4), origin=ArtifactOrigin.NODE)
    assert record.provenance.producer is sentinel_producer


def test_advance_rejects_a_value_of_a_different_domain_type():
    record = ArtifactRecord(value=Measurement(1))

    with pytest.raises(TypeError):
        record.advance(Estimate(1), origin=ArtifactOrigin.NODE)

    # Rejected: the record's value/version/origin are untouched.
    assert record.value.value == 1
    assert record.version == ArtifactVersion.pending()
    assert record.provenance.origin is None


def test_advance_rejects_a_subclass_of_the_original_domain_type():
    class MoreSpecificMeasurement(Measurement):
        pass

    record = ArtifactRecord(value=Measurement(1))

    # `type(value) is not type(self.value)` is an exact-type check, not
    # `isinstance` -- a record's domain type is fixed at first commit
    # (it is the ArtifactRepository dict key, keyed by `type(value)`),
    # so even a subclass is rejected.
    with pytest.raises(TypeError):
        record.advance(MoreSpecificMeasurement(1), origin=ArtifactOrigin.NODE)
