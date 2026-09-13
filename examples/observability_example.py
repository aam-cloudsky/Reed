"""
Reed Observability example (Issue #7).

Demonstrates the full observability stack implemented across Milestones O1-O6:

    - Identity: stable flow_id/node_id, one execution_id per Run (Milestone O1).
    - Instrument + Recording: declared-mode and lazy-mode ctx.record(...)
      (Milestone O2).
    - Local durable storage: opt-in via Flow.run(storage_root=...) -- writes
      recordings.csv / provenance.csv / manifest.json / instruments.json
      (Milestone O3).
    - Provenance: "generated"/"used" events for artifacts flowing between
      Nodes (Milestone O4).
    - Execution Trace: an in-memory ring buffer (Level 1) plus a Rich
      terminal renderer and post-hoc replay (Milestone O5).
    - Tooling: Instrument introspection (describe), cross-Execution
      aggregation (query), and a provenance-graph renderer (graph)
      (Milestone O6).

Run it directly:

    uv run python examples/observability_example.py

Everything here is read from `docs/observability_design.md`/`observability_goals.md` -- this
script is a demonstration of already-implemented behavior, not a new design.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from reed import Flow, NodeContext
from reed.observability.describe import describe_flow
from reed.observability.graph import render_provenance_dot, render_provenance_tree
from reed.observability.instrument import Instrument
from reed.observability.query import query_recordings
from reed.observability.replay import print_replay
from reed.observability.terminal import print_trace


# ============================================================================
# Domain types
# ============================================================================


@dataclass(frozen=True)
class SensorReading:
    celsius: float


@dataclass(frozen=True)
class TrackedReading:
    celsius: float


@dataclass(frozen=True)
class Anomaly:
    celsius: float
    threshold: float
    is_anomaly: bool


@dataclass(frozen=True)
class LoggedAnomaly:
    celsius: float
    threshold: float
    is_anomaly: bool


# ============================================================================
# Instruments -- declared once, per Node (Milestone O2, Slice O2a/O2b)
# ============================================================================

temperature = Instrument(
    name="temperature",
    kind="gauge",
    unit="celsius",
    description="Latest sensor reading observed by track_temperature.",
)

anomaly_count = Instrument(
    name="anomaly_count",
    kind="counter",
    unit="1",
    description="Number of readings that crossed the anomaly threshold.",
)


# ============================================================================
# Nodes
# ============================================================================


def track_temperature(
    ctx: NodeContext[None, TrackedReading],
    reading: SensorReading,
) -> TrackedReading:
    """
    Declared-mode recording: `temperature` was declared up front via
    `flow.add(track_temperature, instruments=[temperature])`, so
    `ctx.record(temperature, ...)` is validated against that declaration.
    """
    ctx.record(temperature, reading.celsius)
    return TrackedReading(celsius=reading.celsius)


def detect_anomaly(
    ctx: NodeContext[None, Anomaly],
    reading: TrackedReading,
) -> Anomaly:
    """
    Declared-mode recording only: once a Node opts into an explicit
    `instruments=[...]` list, every `ctx.record(...)` call must reference
    a declared name (docs/observability_goals.md Section 2.3) -- lazy-mode
    recording is demonstrated separately, in `log_note`, a Node declared
    with no `instruments=[...]` at all.
    """
    threshold = 80.0
    is_anomaly = reading.celsius > threshold

    if is_anomaly:
        ctx.record(anomaly_count, 1)

    return Anomaly(celsius=reading.celsius, threshold=threshold, is_anomaly=is_anomaly)


def log_note(ctx: NodeContext[None, LoggedAnomaly], anomaly: Anomaly) -> LoggedAnomaly:
    """
    Lazy-mode recording (Milestone O2, Slice O2e): `"note"` was never
    declared via `instruments=[...]` -- `flow.add(log_note)` below passes
    no `instruments=` at all, so this is a non-metric fact, a `Recording`
    with `kind=None`, not backed by any `Instrument`.
    """
    if anomaly.is_anomaly:
        ctx.record("note", f"exceeded threshold of {anomaly.threshold}")
    else:
        ctx.record("note", "within normal range")
    return LoggedAnomaly(
        celsius=anomaly.celsius,
        threshold=anomaly.threshold,
        is_anomaly=anomaly.is_anomaly,
    )


def main() -> None:
    flow = Flow()
    flow.add(track_temperature, instruments=[temperature])
    flow.add(detect_anomaly, instruments=[anomaly_count])
    flow.add(log_note)

    # ------------------------------------------------------------------
    # Milestone O6, Slice O6b: introspect declared Instruments with no
    # execution required at all.
    # ------------------------------------------------------------------
    console = Console()
    print("=== reed describe (no execution required) ===")
    console.print(describe_flow(flow))

    # ------------------------------------------------------------------
    # Milestone O3: durable storage is opt-in via storage_root. Using a
    # temporary directory here so this example leaves nothing behind;
    # omit storage_root entirely for an in-memory-only Run (Milestone O2
    # behavior, completely unaffected).
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        storage_root = Path(tmp) / ".reed"
        run = flow.run(storage_root=str(storage_root))

        readings = [SensorReading(celsius=c) for c in (18.0, 22.5, 91.3, 19.8, 95.0)]
        for reading in readings:
            run.publish(reading)

        print(f"\nexecution_id = {run.execution_id}")
        print(f"flow_id      = {flow.flow_id}")

        # ------------------------------------------------------------------
        # Milestone O5, Slice O5b: render the Level 1 Execution Trace --
        # what ran, in what order -- as a Rich table.
        # ------------------------------------------------------------------
        print("\n=== reed trace (Level 1, live ring buffer) ===")
        print_trace(run.trace)

        run_dir = storage_root / "runs" / run.execution_id

        # ------------------------------------------------------------------
        # Milestone O5, Slice O5c: post-hoc replay reading recordings.csv/
        # provenance.csv back from disk, interleaved by execution_seq.
        # ------------------------------------------------------------------
        print("\n=== reed replay (post-hoc, from recordings.csv + provenance.csv) ===")
        print_replay(run_dir)

        # ------------------------------------------------------------------
        # Milestone O6, Slice O6d: reconstruct and render the provenance
        # graph -- who produced each artifact, who consumed it.
        # ------------------------------------------------------------------
        print("\n=== reed graph (Rich tree) ===")
        console.print(render_provenance_tree(run_dir))

        print("\n=== reed graph (Graphviz DOT) ===")
        print(render_provenance_dot(run_dir))

        # ------------------------------------------------------------------
        # Milestone O6, Slice O6c: query recordings.csv across every past
        # Execution of this Flow -- a second Run below aggregates with the
        # first via the same flow_id.
        # ------------------------------------------------------------------
        second_run = flow.run(storage_root=str(storage_root))
        second_run.publish(SensorReading(celsius=42.0))

        rows = query_recordings(storage_root, flow.flow_id)
        print(
            f"\n=== reed query (cross-Execution) ===\n"
            f"{len(rows)} recordings across "
            f"{len({row['execution_id'] for row in rows})} Executions of flow_id={flow.flow_id}"
        )


if __name__ == "__main__":
    main()
