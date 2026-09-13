"""
Milestone O3 -- Local Recording Store (Slices O3a-O3e).

Covers docs/observability_goals.md Section 6:

    1. With no storage_root, Recordings stay in-memory only (no files
       written) -- Milestone O2 behavior is completely unaffected.
    2. With storage_root, recordings.csv/provenance.csv/manifest.json
       are created under <root>/runs/<execution_id>/, and
       instruments.json under <root>/flows/<flow_id>/.
    3. recordings.csv contains one row per ctx.record(...) call, with
       the documented columns.
    4. instruments.json is discovered dynamically (Milestone O7, Slice
       O7i): it does not exist until a Node's first ctx.record(...) call
       is flushed, and is stable (untouched) once a given (node_id,
       Instrument) binding is already known -- a second Run that
       discovers nothing new does not rewrite existing entries.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass

import pytest


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


@dataclass
class TrackerMemory:
    previous_confidence: float | None = None


def _make_flow_with_tracker():
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument, InstrumentKind

    class Speed(Instrument[int]):
        kind = InstrumentKind.GAUGE
        unit = "m/s"

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        ctx.record(Speed, measurement.value)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    return flow, track, Speed


def test_no_storage_root_means_in_memory_only(tmp_path):
    flow, track, Speed = _make_flow_with_tracker()
    run = flow.run()

    run.publish(Measurement(1))

    assert run.recording_store is None
    assert run.provenance_store is None
    assert len(run.node_runtime(track).recordings) == 1
    assert not (tmp_path / ".reed").exists()


def test_storage_root_creates_expected_files(tmp_path):
    flow, track, Speed = _make_flow_with_tracker()
    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root))

    run.publish(Measurement(1))

    run_dir = root / "runs" / run.execution_id
    assert (run_dir / "recordings.csv").exists()
    assert (run_dir / "provenance.csv").exists()
    assert (run_dir / "manifest.json").exists()

    flow_dir = root / "flows" / flow.flow_id
    assert (flow_dir / "instruments.json").exists()


def test_recordings_csv_has_documented_columns_and_one_row_per_record(tmp_path):
    flow, track, Speed = _make_flow_with_tracker()
    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root))

    run.publish(Measurement(1))
    run.publish(Measurement(2))

    run_dir = root / "runs" / run.execution_id
    with open(run_dir / "recordings.csv", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 2
    assert set(rows[0].keys()) == {
        "instrument_id",
        "name",
        "value",
        "kind",
        "unit",
        "execution_id",
        "flow_id",
        "node_id",
        "node_execution_id",
        "execution_seq",
        "attributes",
        "timestamp",
    }
    assert rows[0]["name"] == Speed.instrument_name()
    assert rows[0]["kind"] == "gauge"
    assert rows[0]["value"] == "1"
    assert rows[1]["value"] == "2"


def test_manifest_json_has_schema_version_and_file_index(tmp_path):
    flow, track, Speed = _make_flow_with_tracker()
    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root))
    run.publish(Measurement(1))

    manifest = json.loads(
        (root / "runs" / run.execution_id / "manifest.json").read_text()
    )
    assert manifest["execution_id"] == run.execution_id
    assert manifest["flow_id"] == flow.flow_id
    assert "schema_version" in manifest
    assert manifest["files"] == {
        "recordings": "recordings.csv",
        "provenance": "provenance.csv",
    }


def test_instruments_json_merges_on_discovery_and_is_stable_once_known(tmp_path):
    flow, track, Speed = _make_flow_with_tracker()
    root = tmp_path / ".reed"

    first_run = flow.run(storage_root=str(root))
    first_run.publish(Measurement(1))

    instruments_path = root / "flows" / flow.flow_id / "instruments.json"
    original_mtime = instruments_path.stat().st_mtime_ns
    original_content = instruments_path.read_text()

    second_run = flow.run(storage_root=str(root))
    second_run.publish(Measurement(2))

    assert instruments_path.stat().st_mtime_ns == original_mtime
    assert instruments_path.read_text() == original_content

    content = json.loads(original_content)
    assert content["flow_id"] == flow.flow_id
    node_id = flow.flow_nodes[0].node_id
    assert content["nodes"][node_id]["node_name"] == "track"
    assert content["nodes"][node_id]["instruments"][0]["name"] == Speed.instrument_name()
