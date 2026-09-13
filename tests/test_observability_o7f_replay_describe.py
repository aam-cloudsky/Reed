"""
Milestone O7, Slice O7f -- replay/describe presentation corrections.

    1. describe_flow distinguishes "no Instruments declared, but may still
       emit lazy Recordings" from "declared Instrument list" -- a blank
       row previously implied nothing at all, when in fact a Node with no
       instruments=[...] is exactly the one still eligible for lazy-mode
       ctx.record(...) calls (docs/observability_goals.md Section 2.3).
    2. replay presentation groups rows by node_execution_id rather than
       relying on execution_seq alone to order same-seq rows -- Section
       10 of the task that opened Milestone O7: execution_seq is
       deterministic *observation* ordering only, never causality
       (architectural invariants #7/#8), so the renderer must not imply a
       stronger within-seq ordering than the data actually guarantees.
"""

from __future__ import annotations


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def test_describe_flow_marks_no_instruments_nodes_as_lazy_capable():
    from reed import Flow
    from reed.observability.describe import describe_flow

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)

    table = describe_flow(flow)

    assert table.row_count == 1
    # Not a blank string -- must say something that distinguishes "may
    # still emit lazy Recordings" from "declared nothing, no signal at all".
    instrument_cell = table.columns[1]._cells[0]
    assert instrument_cell != ""
    assert "lazy" in instrument_cell.lower()


def test_describe_flow_declared_instrument_node_is_unaffected():
    from reed import Flow
    from reed.observability.describe import describe_flow
    from reed.observability.instrument import Instrument

    speed = Instrument(name="speed", kind="gauge", unit="m/s")

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce, instruments=[speed])

    table = describe_flow(flow)
    assert table.columns[1]._cells[0] == "speed"


def test_describe_instruments_manifest_marks_lazy_nodes_too(tmp_path):
    from reed import Flow
    from reed.observability.describe import describe_instruments_manifest

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)

    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root))
    run.publish(Measurement(1))

    manifest_path = root / "flows" / flow.flow_id / "instruments.json"
    table = describe_instruments_manifest(manifest_path)

    assert "lazy" in table.columns[1]._cells[0].lower()


def test_replay_groups_rows_by_node_execution_id_not_bare_execution_seq(tmp_path):
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument
    from reed.observability.replay import render_replay_table

    speed = Instrument(name="speed", kind="gauge", unit="m/s")

    def produce(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record("speed", measurement.value)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce, instruments=[speed])
    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root))
    run.publish(Measurement(1))

    run_dir = root / "runs" / run.execution_id
    table = render_replay_table(run_dir)

    # node_execution_id column must exist and every row for the one firing
    # must share the same node_execution_id, making the grouping explicit
    # rather than relying on execution_seq alone.
    column_names = [c.header for c in table.columns]
    assert "node_execution_id" in column_names
    ne_id_col = table.columns[column_names.index("node_execution_id")]
    assert len(set(ne_id_col._cells)) == 1
