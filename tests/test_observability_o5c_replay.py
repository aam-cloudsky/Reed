"""
Milestone O5, Slice O5c (optional) -- post-hoc replay of a past Execution
by reading recordings.csv/provenance.csv back (design record §24).
"""

from __future__ import annotations

import pytest


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def _make_flow_with_recording():
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument, InstrumentKind

    class Speed(Instrument[int]):
        kind = InstrumentKind.GAUGE
        unit = "m/s"

    def produce(
        ctx: NodeContext[None, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        ctx.record(Speed, measurement.value)
        return Estimate(measurement.value * 2)

    flow = Flow()
    flow.add(produce)
    return flow, produce, Speed


def test_render_replay_table_interleaves_recordings_and_provenance(tmp_path):
    from reed.observability.replay import render_replay_table

    flow, produce, Speed = _make_flow_with_recording()
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))
    session.feed(Measurement(1))
    session.push()

    run_dir = root / "runs" / session.execution_id
    table = render_replay_table(run_dir)

    # One recording row, plus three provenance rows: feed()'s own
    # "generated" event for the fed Measurement, the "used" event for
    # Measurement that produce's firing now emits (it already has a
    # committed record, unlike under the old publish()), and the
    # "generated" event for produce's own committed Estimate output
    # (Slice 22E; session_snapshot_decision.md section 1, point 2).
    assert table.row_count == 4


def test_load_recordings_and_provenance_read_back_rows(tmp_path):
    from reed.observability.replay import load_provenance, load_recordings

    flow, produce, Speed = _make_flow_with_recording()
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))
    session.feed(Measurement(1))
    session.push()

    run_dir = root / "runs" / session.execution_id
    recordings = load_recordings(run_dir)
    provenance = load_provenance(run_dir)

    assert len(recordings) == 1
    assert recordings[0]["name"] == Speed.instrument_name()
    # feed()'s own "generated" event for Measurement, produce's "used"
    # event for the now-already-committed Measurement, and produce's
    # own "generated" event for Estimate (Slice 22E).
    assert len(provenance) == 3
    assert [row["event_type"] for row in provenance] == ["generated", "used", "generated"]


def test_replay_raises_when_no_storage_was_configured(tmp_path):
    from reed.observability.replay import load_recordings

    with pytest.raises(FileNotFoundError):
        load_recordings(tmp_path / "nonexistent-run-dir")


def test_print_replay_renders_detail_text(tmp_path):
    from rich.console import Console

    from reed.observability.replay import print_replay

    flow, produce, Speed = _make_flow_with_recording()
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))
    session.feed(Measurement(1))
    session.push()

    run_dir = root / "runs" / session.execution_id
    console = Console(record=True, width=200)
    print_replay(run_dir, console=console)
    output = console.export_text()

    assert f"{Speed.instrument_name()}=1" in output
    assert "generated" in output
