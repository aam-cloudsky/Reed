"""
Focused tests for Slice 2C (Domain Value <-> ArtifactRecord execution
boundary).

No target-architecture-contract test is expected to move for this slice.
All remaining xfail tests either need `ctx.memory`/`.publish(...)`
(Milestone 2D/2E) or `on_output` dispatch/serialization (2F/2G); none of
them constructs or reads an `ArtifactRecord` directly, and
`run.repository.get(...)` (used by the 2F-tagged tests) still does not
exist -- see `reed/execution/artifact_record.py`'s module docstring for
why that is explicitly out of scope here. This file is Slice 2C's
dedicated focused verification, following the same rationale used for
Slices 1A-1E, 2A, and 2B.

Covers exactly the representation and boundary properties this slice
establishes:

    1. `ArtifactRecord` wraps a domain value via composition, not
       inheritance -- `Domain Value != ArtifactRecord`
       (architectural_invariants.md #7).
    2. A fresh `ArtifactRecord` defaults to a pending version, empty
       dependencies, and no producer.
    3. `ArtifactProvenance.advance(...)` preserves `ParcelProvenance`'s
       exact versioning/provenance mechanics (pending -> initial ->
       next, producer/dependencies only overwritten when given).
    4. Dependencies are keyed by domain type, not by legacy `Parcel`
       subclass type.
    5. `NodeRuntime.unwrap(record)` returns exactly the wrapped domain
       value (the "NodeRuntime boundary -> unwrap -> DomainValue" step).
    6. Nothing was made to (a) wrap/commit a domain value into the
       repository, or (b) make `ArtifactRepository` (`run.repository`) able to hold
       an `ArtifactRecord` -- both remain explicitly out of scope, and
       `ArtifactRepository`'s existing regression behavior (rejecting non-`Parcel`
       values) is unchanged.
"""

from __future__ import annotations

import pytest

from reed.execution.artifact_record import (
    ArtifactProvenance,
    ArtifactRecord,
    ArtifactVersion,
)


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def test_artifact_record_wraps_a_domain_value_distinct_from_itself():
    domain_value = Estimate(3)
    record = ArtifactRecord(value=domain_value)

    assert record.value is domain_value
    assert not isinstance(domain_value, ArtifactRecord)
    assert not isinstance(record, Estimate)


def test_fresh_artifact_record_has_pending_version_and_no_producer():
    record = ArtifactRecord(value=Estimate(1))

    assert record.version == ArtifactVersion.pending()
    assert record.version.number == 0
    assert record.dependencies == {}
    assert record.provenance.producer is None


def test_artifact_version_orders_and_advances_like_parcel_version():
    assert ArtifactVersion.pending().number == 0
    assert ArtifactVersion.initial().number == 1
    assert ArtifactVersion.pending().next() == ArtifactVersion.initial()
    assert ArtifactVersion.pending() < ArtifactVersion.initial()


def test_artifact_provenance_advance_moves_pending_to_initial_version():
    provenance = ArtifactProvenance()

    provenance.advance()

    assert provenance.version == ArtifactVersion.initial()


def test_artifact_provenance_advance_sets_producer_and_dependencies():
    from reed import Flow

    def produce_measurement() -> Measurement:
        return Measurement(1)

    flow = Flow()
    flow.add(produce_measurement)
    run = flow.run()
    producer_runtime = run.node_runtime(produce_measurement)

    provenance = ArtifactProvenance()
    provenance.advance(
        producer=producer_runtime,
        dependencies={Measurement: ArtifactVersion.initial()},
    )

    assert provenance.producer is producer_runtime
    assert provenance.dependencies == {Measurement: ArtifactVersion.initial()}


def test_artifact_provenance_advance_does_not_overwrite_when_not_given():
    from reed import Flow

    def produce_measurement() -> Measurement:
        return Measurement(1)

    flow = Flow()
    flow.add(produce_measurement)
    run = flow.run()
    producer_runtime = run.node_runtime(produce_measurement)

    provenance = ArtifactProvenance()
    provenance.advance(producer=producer_runtime, dependencies={})

    provenance.advance()

    assert provenance.producer is producer_runtime
    assert provenance.version == ArtifactVersion.initial().next()


def test_artifact_provenance_copy_advances_independently_from_the_original():
    # Mirrors test_parcel_record_origin_inherits_previous_version_before_advancing:
    # a new record's provenance can inherit a previous one's state via
    # .copy() before advancing further, without the two provenances
    # afterward sharing identity or state.
    previous = ArtifactProvenance()
    previous.advance()

    current = previous.copy()
    current.advance()

    assert current.version == previous.version.next()
    assert previous.version == ArtifactVersion.initial()


def test_artifact_record_dependencies_are_keyed_by_domain_type():
    source = ArtifactRecord(value=Measurement(1))
    source.provenance.advance()

    derived = ArtifactRecord(
        value=Estimate(1),
        provenance=ArtifactProvenance(
            dependencies={Measurement: source.version}
        ),
    )
    derived.provenance.advance()

    assert derived.dependencies == {Measurement: source.version}
    assert all(isinstance(key, type) for key in derived.dependencies)
    assert Measurement in derived.dependencies


def test_node_runtime_unwrap_returns_the_wrapped_domain_value():
    from reed import Flow

    def produce_estimate() -> Estimate:
        return Estimate(9)

    flow = Flow()
    flow.add(produce_estimate)
    run = flow.run()
    node_runtime = run.node_runtime(produce_estimate)

    domain_value = Estimate(9)
    record = ArtifactRecord(value=domain_value)

    assert node_runtime.unwrap(record) is domain_value


def test_artifact_record_has_no_wrap_or_commit_capability_yet():
    record = ArtifactRecord(value=Estimate(1))

    assert not hasattr(ArtifactRecord, "wrap")
    assert not hasattr(record, "commit")


def test_node_runtime_wrap_capability_was_introduced():
    # Slice 2E legitimately adds NodeRuntime.wrap as part of the commit
    # path, making this test's original negative assertion
    # (not hasattr(node_runtime, "wrap")) stale by construction --
    # corrected here in place, the same Test Integrity Rule precedent
    # already applied in Slices 2B and 2D (see docs/refactor_state.md).
    from reed import Flow

    def produce_estimate() -> Estimate:
        return Estimate(1)

    flow = Flow()
    flow.add(produce_estimate)
    run = flow.run()
    node_runtime = run.node_runtime(produce_estimate)

    assert hasattr(node_runtime, "wrap")


def test_depot_still_rejects_non_parcel_values_including_artifact_record():
    # Confirms the reported mismatch directly and guards against a future
    # slice silently assuming ArtifactRepository already supports ArtifactRecord:
    # ArtifactRepository's regression-protected set_parcel(...) is unchanged and still
    # hard-typed to Parcel instances.
    from reed import Flow

    def produce_estimate() -> Estimate:
        return Estimate(1)

    flow = Flow()
    flow.add(produce_estimate)
    run = flow.run()

    record = ArtifactRecord(value=Estimate(1))

    with pytest.raises(TypeError, match="Only Parcel instances"):
        run.repository.set_parcel(record)
