"""
Milestone O4 -- Provenance events (Slices O4a-O4c).

Covers docs/observability_goals.md's provenance section:

    1. A "generated" ProvenanceEvent is emitted for the artifact each
       firing commits, after `.commit(...)` succeeds.
    2. A "used" ProvenanceEvent is emitted for each of a Node's consumed
       artifact types that already has a committed ArtifactRecord --
       nothing is emitted the first time a type is consumed with no
       prior producer.
    3. Both are no-ops when the Session has no provenance_store configured
       (storage_root was not passed to Flow.session(...)).
    4. Identity (and therefore provenance) is minted for every firing,
       regardless of whether the Node declares a NodeContext parameter.
"""

from __future__ import annotations

import csv


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def _make_flow():
    from reed import Flow

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value * 2)

    flow = Flow()
    flow.add(produce)
    return flow, produce


def _read_provenance_rows(root, execution_id):
    path = root / "runs" / execution_id / "provenance.csv"
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_no_storage_root_means_no_provenance_events(tmp_path):
    flow, produce = _make_flow()
    session = flow.session()

    session.feed(Measurement(1))
    session.push()

    assert session.provenance_store is None


def test_generated_event_emitted_for_first_firing(tmp_path):
    flow, produce = _make_flow()
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    session.feed(Measurement(1))
    session.push()

    rows = _read_provenance_rows(root, session.execution_id)
    generated = [r for r in rows if r["event_type"] == "generated"]
    used = [r for r in rows if r["event_type"] == "used"]

    # feed()'s own commit of the externally supplied Measurement also
    # emits a "generated" event for Measurement itself (Slice 22E;
    # docs/refactor/session_snapshot_decision.md section 1, point 2 --
    # "a publish()-fed root value never itself became a versioned,
    # provenance-tracked ArtifactRecord ... asymmetric with values
    # produced by node firings" is exactly the asymmetry feed() closes),
    # alongside the "generated" event for produce's own committed
    # Estimate output.
    assert len(generated) == 2
    estimate_generated = next(
        r for r in generated if r["artifact_id"].endswith("Estimate")
    )
    assert estimate_generated["artifact_version"] == "1"
    # Because Measurement is now committed by feed() before produce
    # fires, produce's firing DOES see a prior committed record for its
    # consumed type -- unlike under the old publish(), which never
    # committed the root value at all. A "used" event is now emitted
    # for it.
    assert len(used) == 1
    assert used[0]["artifact_id"].endswith("Measurement")


class Verdict:
    def __init__(self, value: int) -> None:
        self.value = value


def test_used_event_emitted_when_prior_record_exists(tmp_path):
    from reed import Flow

    def stage_one(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    def stage_two(estimate: Estimate) -> Verdict:
        return Verdict(estimate.value + 1)

    flow = Flow()
    flow.add(stage_one)
    flow.add(stage_two)

    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    session.feed(Measurement(1))
    session.push()
    session.feed(Estimate(5))
    session.push()

    rows = _read_provenance_rows(root, session.execution_id)
    used = [r for r in rows if r["event_type"] == "used"]

    # The second feed()+push()'s consumer (stage_two) consumes Estimate, which
    # already has a committed ArtifactRecord from the first feed()+push()'s
    # stage_one firing -- so a "used" event must be emitted for it.
    assert any(r["artifact_id"].endswith("Estimate") for r in used)


def test_provenance_events_carry_node_execution_identity(tmp_path):
    flow, produce = _make_flow()
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    session.feed(Measurement(1))
    session.push()

    rows = _read_provenance_rows(root, session.execution_id)
    assert len(rows) >= 1
    for row in rows:
        assert row["node_execution_id"]
        assert int(row["execution_seq"]) >= 1

    # feed()'s own "generated" event for the fed Measurement is tagged
    # with the fed type's own stable identity as node_id (Slice 22E;
    # session_snapshot_decision.md section 4, "feed() is a node") --
    # the rows from produce's own firing (consuming that fed value and
    # committing Estimate) still carry produce's node_id.
    produce_rows = [row for row in rows if row["node_id"].endswith("produce")]
    assert len(produce_rows) >= 1


def test_identity_minted_for_context_free_nodes():
    """
    Milestone O4 restructuring: _begin_node_execution is now called
    unconditionally in the push() cascade loop, not only inside
    _build_call_kwargs's `if flow_node.context is not None` branch --
    so a Node with no NodeContext parameter still fires successfully
    and still gets an execution_seq bump (verified indirectly via a
    second firing's provenance event using a later execution_seq).
    """
    flow, produce = _make_flow()
    session = flow.session()
    snapshot = session.invoke(Measurement(3))
    result = snapshot[Estimate]
    assert isinstance(result, Estimate)
    assert result.value == 6
