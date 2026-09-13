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
    from reed.observability.instrument import Instrument

    speed = Instrument(name="speed", kind="gauge", unit="m/s")

    def produce(
        ctx: NodeContext[None, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        ctx.record(speed, measurement.value)
        return Estimate(measurement.value * 2)

    flow = Flow()
    flow.add(produce, instruments=[speed])
    return flow, produce


def test_render_replay_table_interleaves_recordings_and_provenance(tmp_path):
    from reed.observability.replay import render_replay_table

    flow, produce = _make_flow_with_recording()
    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root))
    run.publish(Measurement(1))

    run_dir = root / "runs" / run.execution_id
    table = render_replay_table(run_dir)

    assert table.row_count == 2  # one recording row, one "generated" provenance row


def test_load_recordings_and_provenance_read_back_rows(tmp_path):
    from reed.observability.replay import load_provenance, load_recordings

    flow, produce = _make_flow_with_recording()
    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root))
    run.publish(Measurement(1))

    run_dir = root / "runs" / run.execution_id
    recordings = load_recordings(run_dir)
    provenance = load_provenance(run_dir)

    assert len(recordings) == 1
    assert recordings[0]["name"] == "speed"
    assert len(provenance) == 1
    assert provenance[0]["event_type"] == "generated"


def test_replay_raises_when_no_storage_was_configured(tmp_path):
    from reed.observability.replay import load_recordings

    with pytest.raises(FileNotFoundError):
        load_recordings(tmp_path / "nonexistent-run-dir")


def test_print_replay_renders_detail_text(tmp_path):
    from rich.console import Console

    from reed.observability.replay import print_replay

    flow, produce = _make_flow_with_recording()
    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root))
    run.publish(Measurement(1))

    run_dir = root / "runs" / run.execution_id
    console = Console(record=True, width=200)
    print_replay(run_dir, console=console)
    output = console.export_text()

    assert "speed=1" in output
    assert "generated" in output
