"""
Milestone O7, Slice O7b -- Artifact version identity across repeated
firings of the same Node (design record: causally distinct Artifact
generations must be distinguishable).

Regression for a confirmed defect: `NodeSession.wrap(...)` previously
constructed a *fresh* `ArtifactProvenance()` on every call, so every
firing's committed `ArtifactRecord.version` was always `ArtifactVersion.
initial()` (1), regardless of how many times that Node had already fired
in this Session. This silently collapsed causally distinct Artifact
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
    session = flow.session()

    session.feed(Measurement(1))
    session.push()
    first_record = session.repository.get_artifact_record(Estimate)
    assert first_record.version.number == 1

    session.feed(Measurement(2))
    session.push()
    second_record = session.repository.get_artifact_record(Estimate)
    assert second_record.version.number == 2

    session.feed(Measurement(3))
    session.push()
    third_record = session.repository.get_artifact_record(Estimate)
    assert third_record.version.number == 3


def test_earlier_retrieved_records_now_observe_a_later_advance_in_place():
    """
    Slice 22C -- DELIBERATE, OPENLY-RECORDED TEST REVERSAL (Test Integrity
    Rule precedent set during issue #21: never silently weaken a test;
    rewrite it openly with the rationale recorded in the test itself).

    This test used to be named
    `test_earlier_committed_records_keep_their_own_version_after_later_firings`
    and asserted the OPPOSITE of what it asserts now: that a committed
    `ArtifactRecord` was never mutated by a later firing, because
    `NodeSession.wrap()` built a brand-new `ArtifactRecord`/
    `ArtifactProvenance` every time. That name would now be a lie about
    what this test checks, which is itself a form of silent deception --
    so it is renamed along with its assertion, in the open, here.

    `docs/refactor/session_snapshot_decision.md` section 7
    ("`ArtifactRecord` becomes mutable in place") and
    `architectural_invariants.md` #27 deliberately reverse the old
    invariant: `ArtifactRecord.advance(...)` (added this slice) mutates
    `.value`/`.provenance` on the SAME object rather than replacing it.
    This was verified safe first (session_snapshot_decision.md section 7):
    the only production code that depended on the old guarantee was this
    one regression test.

    A record retrieved before a later `.advance()` call on that same
    object is now **aliased** to it and observes the mutation, rather
    than keeping the independent **value semantics** it had before (see
    `references/ingested/glossary.md`, "Aliasing" / "In-place mutation" /
    "Value semantics" / "Reference semantics").

    This slice narrowly adds `ArtifactRecord.advance()`; it does NOT wire
    `NodeSession.wrap()` to call it yet (that unification is slice 22D),
    so the publish path (now `session.feed(...)`/`session.push()`) still
    commits a fresh `ArtifactRecord` per firing today. To exercise the
    new aliasing behavior this test calls
    `.advance()` directly on a record retrieved from the repository --
    exactly what a future, 22D-wired `wrap()`/`commit()` will do to the
    repository's one persistent record per type.
    """
    from reed.execution.artifact_record import ArtifactOrigin

    flow, produce = _make_flow()
    session = flow.session()

    session.feed(Measurement(1))
    session.push()
    first_record = session.repository.get_artifact_record(Estimate)
    assert first_record.version.number == 1
    assert first_record.value.value == 1

    # Simulate a later firing's in-place commit (slice 22D's eventual
    # wrap()/commit() wiring) by advancing the SAME ArtifactRecord object
    # already sitting in the repository.
    first_record.advance(Estimate(99), origin=ArtifactOrigin.NODE)

    # A second, independent retrieval from the repository is the identical
    # object -- not a new one -- and reads the mutation `first_record`
    # applied: this is aliasing, not value semantics.
    second_retrieval = session.repository.get_artifact_record(Estimate)
    assert second_retrieval is first_record
    assert second_retrieval.version.number == 2
    assert second_retrieval.value.value == 99

    # first_record itself -- the reference retrieved BEFORE the .advance()
    # call -- also observes the mutation, which is exactly the reversal
    # this test now protects.
    assert first_record.version.number == 2
    assert first_record.value.value == 99


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
    session = flow.session(storage_root=str(root))

    session.feed(Measurement(1))
    session.push()
    session.feed(Measurement(2))
    session.push()
    session.feed(Measurement(3))
    session.push()

    run_dir = root / "runs" / session.execution_id
    rows = load_provenance(run_dir)
    # feed()'s own commit of each fed Measurement now also emits its own
    # "generated" event per feed (Slice 22E), interleaved with produce's;
    # narrow to produce's own committed Estimate to keep testing exactly
    # what this test's name says: distinct, increasing versions across
    # repeated firings of the SAME Node.
    generated_versions = [
        int(row["artifact_version"])
        for row in rows
        if row["event_type"] == "generated" and row["artifact_id"].endswith("Estimate")
    ]

    assert generated_versions == [1, 2, 3]


def test_two_different_artifact_types_version_independently():
    """
    Version is scoped per (NodeSession, domain type) -- a second Node
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
    session = flow.session()

    session.feed(Measurement(1))
    session.push()
    session.feed(Measurement(2))
    session.push()

    estimate_record = session.repository.get_artifact_record(Estimate)
    doubled_record = session.repository.get_artifact_record(Doubled)

    assert estimate_record.version.number == 2
    assert doubled_record.version.number == 2
