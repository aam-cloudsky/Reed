"""
Level 1 terminal renderer (Milestone O5, Slice O5b).

Rebuilds the terminal-rendering experience lost with the legacy Bus/Depot/Outpost tracing
system (docs/refactor/observability_design.md Section 1, Section 8) as **a consumer of Level 1**
(the `ExecutionTrace` ring buffer, Slice O5a) -- not by reviving any of that legacy
machinery (`docs/refactor/observability_non_goals.md` Section 9 forbids that).

The legacy `EventRenderer` subscribed live to Bus traffic and printed as messages arrived.
This renderer is deliberately simpler for V1: it is a pull-based snapshot renderer over
`session.trace.events` (a `tuple`, already an immutable point-in-time view -- Slice O5a), not a
live subscriber. A caller renders whenever it wants a picture of the trace so far (after
each `session.push()`, or once at the end, or periodically) rather than this module
pushing output as events occur. This is a legitimate, explicitly scoped V1 simplification: it
needs no callback/subscription mechanism on `ExecutionTrace` (which does not have one), and
it still reconstructs the same trace-id-correlated, Node-named, state-labeled shape the
legacy renderer showed, just polled rather than streamed. Live streaming is available as
future work if a real need for it appears (it would mean adding a subscriber list to
`ExecutionTrace.record(...)`, not changing this module's rendering logic).
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from reed.observability.trace import ExecutionTrace, TraceEvent


def _pair_events(events: tuple[TraceEvent, ...]) -> dict[str, dict[str, TraceEvent]]:
    """
    Group `events` by `node_execution_id`, keyed further by `event_type` --
    so a "node_started"/"node_finished" pair for the same firing renders as
    one row instead of two.
    """
    paired: dict[str, dict[str, TraceEvent]] = {}
    for event in events:
        paired.setdefault(event.node_execution_id, {})[event.event_type] = event
    return paired


def render_trace_table(trace: ExecutionTrace) -> Table:
    """
    Build a Rich `Table` of `trace`'s current events, one row per Node
    firing (`node_execution_id`), ordered by `execution_seq` -- the
    deterministic observation order Section 13.1 defines (never a
    causality claim).

    Columns: `seq` (execution_seq), `node` (node_id), `node_execution_id`
    (truncated for readability), and `status` ("running" if only a
    "node_started" event has been recorded so far -- e.g. the renderer was
    called mid-firing or the buffer dropped the "node_finished" half past
    capacity -- else "finished").
    """
    table = Table(title="Reed Execution Trace")
    table.add_column("seq", justify="right")
    table.add_column("node")
    table.add_column("node_execution_id")
    table.add_column("status")

    paired = _pair_events(trace.events)
    rows = sorted(paired.items(), key=lambda item: _row_seq(item[1]))

    for node_execution_id, by_type in rows:
        started = by_type.get("node_started")
        finished = by_type.get("node_finished")
        anchor = finished or started
        assert anchor is not None
        status = "finished" if finished is not None else "running"
        table.add_row(
            str(anchor.execution_seq),
            anchor.node_id,
            node_execution_id[:8],
            status,
        )

    return table


def _row_seq(by_type: dict[str, TraceEvent]) -> int:
    anchor = by_type.get("node_started") or by_type.get("node_finished")
    assert anchor is not None
    return anchor.execution_seq


def print_trace(trace: ExecutionTrace, *, console: Console | None = None) -> None:
    """Render `trace` as a table to `console` (a fresh `Console()` if omitted)."""
    (console or Console()).print(render_trace_table(trace))
