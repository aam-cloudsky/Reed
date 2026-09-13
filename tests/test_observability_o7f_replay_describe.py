"""
Milestone O7, Slice O7f -- replay/describe presentation corrections
(generalized by Slice O7i's typed-Instrument redesign: describe's
"declared vs. lazy" distinction no longer exists -- every Instrument is
runtime-discovered uniformly; see test_observability_o6b_describe.py for
the current describe_flow/describe_instruments_manifest contract).

    1. replay presentation groups rows by node_execution_id rather than
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


def test_replay_groups_rows_by_node_execution_id_not_bare_execution_seq(tmp_path):
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument, InstrumentKind
    from reed.observability.replay import render_replay_table

    class Speed(Instrument[int]):
        kind = InstrumentKind.GAUGE
        unit = "m/s"

    def produce(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record(Speed, measurement.value)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)
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
