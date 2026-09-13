"""
Milestone O7, Slice O7b -- Artifact version identity across repeated
firings of the same Node (design record: causally distinct Artifact
generations must be distinguishable).

Regression for a confirmed defect: `NodeRuntime.wrap(...)` previously
constructed a *fresh* `ArtifactProvenance()` on every call, so every
firing's committed `ArtifactRecord.version` was always `ArtifactVersion.
initial()` (1), regardless of how many times that Node had already fired
in this Run. This silently collapsed causally distinct Artifact
generations into indistinguishable "version 1" records, which is exactly
what the `reed graph`/`reed replay` acceptance-example output showed:
every `TrackedReading` line read "v1", including ones from later
publications.
"""

from __future__ import annotations


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def _make_flow():
    from reed import Flow

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)
    return flow, produce


def test_repeated_firings_of_the_same_node_increment_artifact_version():
    flow, produce = _make_flow()
    run = flow.run()

    run.publish(Measurement(1))
    first_record = run.repository.get_artifact_record(Estimate)
    assert first_record.version.number == 1

    run.publish(Measurement(2))
    second_record = run.repository.get_artifact_record(Estimate)
    assert second_record.version.number == 2

    run.publish(Measurement(3))
    third_record = run.repository.get_artifact_record(Estimate)
    assert third_record.version.number == 3


def test_earlier_committed_records_keep_their_own_version_after_later_firings():
    """
    A committed ArtifactRecord must not be mutated by a later firing --
    each ArtifactRecord.provenance must be an independent snapshot, not a
    shared, mutable ArtifactProvenance object aliased across firings.
    """
    flow, produce = _make_flow()
    run = flow.run()

    run.publish(Measurement(1))
    first_record = run.repository.get_artifact_record(Estimate)
    assert first_record.version.number == 1

    run.publish(Measurement(2))
    run.publish(Measurement(3))

    # first_record must still read version 1 -- it must not have been
    # mutated in place by subsequent firings' wrap()/advance() calls.
    assert first_record.version.number == 1


def test_provenance_generated_events_carry_distinct_artifact_versions_across_publications(
    tmp_path,
):
    """
    End-to-end: with durable storage configured, provenance.csv's
    "generated" events for repeated publications of the same Node must
    show distinct, monotonically increasing artifact_version values --
    not all "1" (Milestone O4's provenance wiring reads
    ArtifactRecord.version.number directly, so this is the observable,
    on-disk consequence of the ArtifactRecord-level bug).
    """
    from reed.observability.replay import load_provenance

    flow, produce = _make_flow()
    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root))

    run.publish(Measurement(1))
    run.publish(Measurement(2))
    run.publish(Measurement(3))

    run_dir = root / "runs" / run.execution_id
    rows = load_provenance(run_dir)
    generated_versions = [
        int(row["artifact_version"]) for row in rows if row["event_type"] == "generated"
    ]

    assert generated_versions == [1, 2, 3]


def test_two_different_artifact_types_version_independently():
    """
    Version is scoped per (NodeRuntime, domain type) -- a second Node
    producing a different Artifact type must start its own version count
    at 1, unaffected by how many times a different Node has fired.
    """
    from reed import Flow

    class Doubled:
        def __init__(self, value: int) -> None:
            self.value = value

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    def double(estimate: Estimate) -> Doubled:
        return Doubled(estimate.value * 2)

    flow = Flow()
    flow.add(produce)
    flow.add(double)
    run = flow.run()

    run.publish(Measurement(1))
    run.publish(Measurement(2))

    estimate_record = run.repository.get_artifact_record(Estimate)
    doubled_record = run.repository.get_artifact_record(Doubled)

    assert estimate_record.version.number == 2
    assert doubled_record.version.number == 2
