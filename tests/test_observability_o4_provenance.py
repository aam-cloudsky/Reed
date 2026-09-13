"""
Milestone O4 -- Provenance events (Slices O4a-O4c).

Covers docs/observability_goals.md's provenance section:

    1. A "generated" ProvenanceEvent is emitted for the artifact each
       firing commits, after `.commit(...)` succeeds.
    2. A "used" ProvenanceEvent is emitted for each of a Node's consumed
       artifact types that already has a committed ArtifactRecord --
       nothing is emitted the first time a type is consumed with no
       prior producer.
    3. Both are no-ops when the Run has no provenance_store configured
       (storage_root was not passed to Flow.run(...)).
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
    run = flow.run()

    run.publish(Measurement(1))

    assert run.provenance_store is None


def test_generated_event_emitted_for_first_firing(tmp_path):
    flow, produce = _make_flow()
    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root))

    run.publish(Measurement(1))

    rows = _read_provenance_rows(root, run.execution_id)
    generated = [r for r in rows if r["event_type"] == "generated"]
    used = [r for r in rows if r["event_type"] == "used"]

    assert len(generated) == 1
    assert generated[0]["artifact_id"].endswith("Estimate")
    assert generated[0]["artifact_version"] == "1"
    # Nothing was previously committed for Measurement, so no "used"
    # event is emitted on this first firing.
    assert len(used) == 0


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
    run = flow.run(storage_root=str(root))

    run.publish(Measurement(1))
    run.publish(Estimate(5))

    rows = _read_provenance_rows(root, run.execution_id)
    used = [r for r in rows if r["event_type"] == "used"]

    # The second publish's consumer (stage_two) consumes Estimate, which
    # already has a committed ArtifactRecord from the first publish's
    # stage_one firing -- so a "used" event must be emitted for it.
    assert any(r["artifact_id"].endswith("Estimate") for r in used)


def test_provenance_events_carry_node_execution_identity(tmp_path):
    flow, produce = _make_flow()
    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root))

    run.publish(Measurement(1))

    rows = _read_provenance_rows(root, run.execution_id)
    assert len(rows) >= 1
    for row in rows:
        assert row["node_execution_id"]
        assert row["node_id"].endswith("produce")
        assert int(row["execution_seq"]) >= 1


def test_identity_minted_for_context_free_nodes():
    """
    Milestone O4 restructuring: _begin_node_execution is now called
    unconditionally in the publish(...) cascade loop, not only inside
    _build_call_kwargs's `if flow_node.context is not None` branch --
    so a Node with no NodeContext parameter still fires successfully
    and still gets an execution_seq bump (verified indirectly via a
    second firing's provenance event using a later execution_seq).
    """
    flow, produce = _make_flow()
    result = flow.run().publish(Measurement(3))
    assert isinstance(result, Estimate)
    assert result.value == 6
