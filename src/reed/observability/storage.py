"""
RecordingStore / ProvenanceStore (Milestone O3, Slices O3a-O3e).

Logical interfaces plus a V1 CSV implementation
(docs/observability_goals.md Section 6): each `Execution` owns its own
physical files under `<storage_root>/runs/<execution_id>/`, never shared
across Executions (docs/observability_non_goals.md Section 7).
`instruments.json` under `<storage_root>/flows/<flow_id>/` is
write-once-if-absent (Section 17.3's resolved concurrency concern) --
never rewritten by an ordinary run.

CSV is the V1 implementation; `RecordingStore`/`ProvenanceStore` are
`Protocol`s so a future Parquet (or other) backend is a drop-in swap
behind the same interface, never a change to `ctx.record()` or to what a
`Recording` means (docs/observability_goals.md Section 6).

Durability boundary (Slice O3c; docs/observability_goals.md Section 5):
`CSVRecordingStore.append`/`CSVProvenanceStore.append` flush and fsync
synchronously, on every call -- stronger than the documented boundary
("durable when the NodeExecution exits"), not weaker: a Recording is
durable the instant `ctx.record(...)` accepts it, before the Node body
even returns. This is a deliberate V1 simplicity/latency trade-off
(no batching), not a violation of docs/observability_non_goals.md
Section 5 ("no fsync per ctx.record() call" was a caution about forcing
this trade-off as a workaround for an unqualified "never lossy" claim --
here it is a documented, chosen implementation, not a patch over a
broken guarantee). Batching before the boundary is legitimate future
work if hot-path latency becomes a concern; it is not required for
Milestone O3's definition of done.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Protocol

from reed.observability.instrument import Instrument
from reed.observability.provenance import ProvenanceEvent
from reed.observability.recording import Recording

RECORDING_FIELDS: tuple[str, ...] = (
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
)

PROVENANCE_FIELDS: tuple[str, ...] = (
    "event_type",
    "artifact_id",
    "artifact_version",
    "node_execution_id",
    "node_id",
    "timestamp",
    "execution_seq",
)

SCHEMA_VERSION = 1


class RecordingStore(Protocol):
    def append(self, recording: Recording) -> None: ...


class ProvenanceStore(Protocol):
    def append(self, event: ProvenanceEvent) -> None: ...


def _write_csv_header_if_absent(path: Path, fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(fields)


def _append_csv_row(path: Path, row: list[object]) -> None:
    with open(path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())


class CSVRecordingStore:
    """V1 `RecordingStore`: one append-only `recordings.csv` per Execution."""

    def __init__(self, path: Path) -> None:
        self._path = path
        _write_csv_header_if_absent(self._path, RECORDING_FIELDS)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, recording: Recording) -> None:
        _append_csv_row(
            self._path,
            [
                recording.instrument_id,
                recording.name,
                recording.value,
                recording.kind or "",
                recording.unit or "",
                recording.execution_id,
                recording.flow_id,
                recording.node_id,
                recording.node_execution_id,
                recording.execution_seq,
                json.dumps(recording.attributes) if recording.attributes else "",
                recording.timestamp,
            ],
        )


class CSVProvenanceStore:
    """V1 `ProvenanceStore`: one append-only `provenance.csv` per Execution."""

    def __init__(self, path: Path) -> None:
        self._path = path
        _write_csv_header_if_absent(self._path, PROVENANCE_FIELDS)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, event: ProvenanceEvent) -> None:
        _append_csv_row(
            self._path,
            [
                event.event_type,
                event.artifact_id,
                event.artifact_version,
                event.node_execution_id,
                event.node_id,
                event.timestamp,
                event.execution_seq,
            ],
        )


def write_manifest(
    root: Path, *, execution_id: str, flow_id: str
) -> Path:
    """
    Write `<root>/runs/<execution_id>/manifest.json` (Slice O3d), indexing
    `recordings.csv`/`provenance.csv` and their `schema_version`.
    """
    run_dir = root / "runs" / execution_id
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "execution_id": execution_id,
                "flow_id": flow_id,
                "schema_version": SCHEMA_VERSION,
                "files": {
                    "recordings": "recordings.csv",
                    "provenance": "provenance.csv",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest_path


def write_instruments_manifest_if_absent(
    root: Path,
    *,
    flow_id: str,
    nodes: "list[tuple[str, str, tuple[Instrument, ...]]]",
) -> Path:
    """
    Write `<root>/flows/<flow_id>/instruments.json` (Slice O3e), unless it
    already exists -- write-once-if-absent, never rewritten by an ordinary
    run (Section 17.3's resolved concurrency concern).

    `nodes` is `[(node_id, node_name, instruments), ...]`.
    """
    flow_dir = root / "flows" / flow_id
    flow_dir.mkdir(parents=True, exist_ok=True)
    instruments_path = flow_dir / "instruments.json"

    if instruments_path.exists():
        return instruments_path

    instruments_path.write_text(
        json.dumps(
            {
                "flow_id": flow_id,
                "schema_version": SCHEMA_VERSION,
                "nodes": {
                    node_id: {
                        "node_name": node_name,
                        "instruments": [
                            {
                                "name": instrument.name,
                                "kind": instrument.kind,
                                "unit": instrument.unit,
                                "description": instrument.description,
                            }
                            for instrument in instruments
                        ],
                    }
                    for node_id, node_name, instruments in nodes
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return instruments_path
