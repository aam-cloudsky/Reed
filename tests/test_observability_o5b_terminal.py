"""
Milestone O5, Slice O5b -- Rich-based terminal renderer over the Level 1
Execution Trace (design record §1, §8, §22.2).
"""

from __future__ import annotations

from rich.console import Console


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


def test_render_trace_table_has_one_row_per_firing():
    from reed.observability.terminal import render_trace_table

    flow, produce = _make_flow()
    run = flow.run()
    run.publish(Measurement(1))
    run.publish(Measurement(2))

    table = render_trace_table(run.trace)

    assert table.row_count == 2


def test_print_trace_renders_node_id_and_finished_status():
    from reed.observability.terminal import print_trace

    flow, produce = _make_flow()
    run = flow.run()
    run.publish(Measurement(1))

    console = Console(record=True, width=200)
    print_trace(run.trace, console=console)
    output = console.export_text()

    assert "produce" in output
    assert "finished" in output


def test_render_trace_table_shows_running_when_only_started_recorded():
    from reed.observability.terminal import render_trace_table
    from reed.observability.trace import ExecutionTrace, TraceEvent

    trace = ExecutionTrace()
    trace.record(
        TraceEvent(
            event_type="node_started",
            execution_id="exec",
            flow_id="flow",
            node_id="mod.node",
            node_execution_id="ne-1",
            execution_seq=1,
            timestamp=0.0,
        )
    )

    table = render_trace_table(trace)
    assert table.row_count == 1
    row = table.columns[3]._cells[0]
    assert row == "running"


def test_render_trace_table_empty_trace_has_no_rows():
    from reed.observability.terminal import render_trace_table
    from reed.observability.trace import ExecutionTrace

    table = render_trace_table(ExecutionTrace())
    assert table.row_count == 0
