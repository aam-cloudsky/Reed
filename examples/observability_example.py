"""
Reed Observability example (Issue #7).

Demonstrates the full observability stack implemented across Milestones O1-O7:

    - Identity: stable flow_id/node_id, one execution_id per Session (Milestone O1).
    - Instrument + Recording: typed Instrument Definitions, discovered
      dynamically at execution time -- ctx.record(SomeInstrument, value)
      (Milestone O2; redesigned at Milestone O7, Slice O7i).
    - Local durable storage: opt-in via Flow.session(storage_root=...) -- writes
      recordings.csv / provenance.csv / manifest.json / instruments.json
      (Milestone O3).
    - Provenance: "generated"/"used" events for artifacts flowing between
      Nodes (Milestone O4).
    - Execution Trace: an in-memory ring buffer (Level 1) plus a Rich
      terminal renderer and post-hoc replay (Milestone O5).
    - Tooling: Instrument introspection (describe), cross-Execution
      aggregation (query), and a provenance-graph renderer (graph)
      (Milestone O6).
    - Terminal presentation control: flow.session(observability=<preset>) --
      silent, errors, progress, instruments, nodes, verbose (Milestone O7,
      Slices O7d/O7e). Presentation is purely a terminal *view* over
      Reed's observability model -- it never changes what gets collected
      or persisted (see main()'s final section).

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
from reed.observability.instrument import Instrument, InstrumentKind
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
# Instruments -- typed Instrument Definitions (Milestone O7, Slice O7i).
#
# There is no separate declaration step: an Instrument is discovered the
# first time a Node calls ctx.record(SomeInstrument, value) during a real
# Session. The class itself -- never an instance -- is passed to ctx.record(...).
# ============================================================================


class Temperature(Instrument[float]):
    kind = InstrumentKind.GAUGE
    unit = "celsius"
    description = "Latest sensor reading observed by track_temperature."


class AnomalyCount(Instrument[int]):
    kind = InstrumentKind.COUNTER
    unit = "1"
    description = "Number of readings that crossed the anomaly threshold."


# ============================================================================
# Nodes
# ============================================================================


def track_temperature(
    ctx: NodeContext[None, TrackedReading],
    reading: SensorReading,
) -> TrackedReading:
    """
    ctx.record(Temperature, ...) references the Instrument Definition
    directly and exclusively -- no separate flow.add(instruments=[...])
    declaration exists to duplicate or drift out of sync with this.
    """
    ctx.record(Temperature, reading.celsius)
    return TrackedReading(celsius=reading.celsius)


def detect_anomaly(
    ctx: NodeContext[None, Anomaly],
    reading: TrackedReading,
) -> Anomaly:
    threshold = 80.0
    is_anomaly = reading.celsius > threshold

    if is_anomaly:
        ctx.record(AnomalyCount, 1)

    return Anomaly(celsius=reading.celsius, threshold=threshold, is_anomaly=is_anomaly)


def log_anomaly(
    ctx: NodeContext[None, LoggedAnomaly],
    anomaly: Anomaly,
) -> LoggedAnomaly:
    return LoggedAnomaly(
        celsius=anomaly.celsius, threshold=anomaly.threshold, is_anomaly=anomaly.is_anomaly
    )


def main() -> None:
    flow = Flow()
    flow.add(track_temperature)
    flow.add(detect_anomaly)
    flow.add(log_anomaly)

    console = Console()

    # ------------------------------------------------------------------
    # Milestone O6, Slice O6b (redesigned at Milestone O7, Slice O7i):
    # describe_flow(...) needs no execution, but since Instruments are now
    # discovered dynamically rather than prospectively declared, it can
    # only report which Nodes exist -- not which Instruments (if any)
    # they will record. describe_instruments_manifest(...) below is what
    # actually shows discovered Instrument bindings, once a Session exists.
    # ------------------------------------------------------------------
    print("=== reed describe (no execution required -- Nodes only, O7i) ===")
    console.print(describe_flow(flow))

    # ------------------------------------------------------------------
    # Milestone O3: durable storage is opt-in via storage_root. Using a
    # temporary directory here so this example leaves nothing behind;
    # omit storage_root entirely for an in-memory-only Session (Milestone O2
    # behavior, completely unaffected).
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        storage_root = Path(tmp) / ".reed"
        session = flow.session(storage_root=str(storage_root))

        readings = [SensorReading(celsius=c) for c in (18.0, 22.5, 91.3, 19.8, 95.0)]
        for reading in readings:
            session.feed(reading)
            session.push()

        print(f"\nexecution_id = {session.execution_id}")
        print(f"flow_id      = {flow.flow_id}")

        # ------------------------------------------------------------------
        # Milestone O6, Slice O6b: now that this Session has discovered and
        # persisted real Instrument bindings, describe_instruments_manifest
        # can report them -- name/kind/unit, per Node.
        # ------------------------------------------------------------------
        from reed.observability.describe import describe_instruments_manifest

        manifest_path = storage_root / "flows" / flow.flow_id / "instruments.json"
        print("\n=== reed describe --manifest (Instruments actually discovered) ===")
        console.print(describe_instruments_manifest(manifest_path))

        # ------------------------------------------------------------------
        # Milestone O5, Slice O5b: render the Level 1 Execution Trace --
        # what ran, in what order -- as a Rich table.
        # ------------------------------------------------------------------
        print("\n=== reed trace (Level 1, live ring buffer) ===")
        print_trace(session.trace)

        run_dir = storage_root / "runs" / session.execution_id

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
        # Execution of this Flow -- a second Session below aggregates with the
        # first via the same flow_id.
        # ------------------------------------------------------------------
        second_session = flow.session(storage_root=str(storage_root))
        second_session.feed(SensorReading(celsius=42.0))
        second_session.push()

        rows = query_recordings(storage_root, flow.flow_id)
        print(
            f"\n=== reed query (cross-Execution) ===\n"
            f"{len(rows)} recordings across "
            f"{len({row['execution_id'] for row in rows})} Executions of flow_id={flow.flow_id}"
        )

    # ------------------------------------------------------------------
    # Milestone O7, Slices O7d/O7e: terminal presentation control.
    #
    # The SAME Flow is run six times below, once per preset, over the
    # SAME fed values. Only what is *shown in the terminal*
    # changes -- the computed domain results are identical every time
    # (verified by the assertion at the end of this section), and a
    # silent terminal does not stop Reed from persisting Recordings and
    # Provenance to storage_root, demonstrated in the final block.
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("Milestone O7: terminal presentation presets over the same Flow")
    print("=" * 78)

    presets = ("silent", "errors", "progress", "instruments", "nodes", "verbose")
    domain_results: dict[str, float] = {}

    for preset in presets:
        print(f"\n--- observability={preset!r} " + "-" * (48 - len(preset)))
        preset_flow = Flow()
        preset_flow.add(track_temperature)
        preset_flow.add(detect_anomaly)
        preset_flow.add(log_anomaly)

        preset_session = preset_flow.session(observability=preset)
        snapshot = preset_session.invoke(SensorReading(celsius=91.3))
        domain_results[preset] = snapshot[TrackedReading].celsius

    assert len(set(domain_results.values())) == 1, (
        "presentation choice must never change the computed domain result"
    )
    print(
        f"\nAll six presets computed the identical domain result "
        f"(celsius={next(iter(domain_results.values()))}) -- presentation "
        "configuration changed only what was shown in the terminal, never "
        "the Flow's computational semantics."
    )

    # ------------------------------------------------------------------
    # Collection vs. presentation are fully independent (Milestone O7,
    # Slice O7d): observability="silent" here still persists byte-for-byte
    # the same Recordings/Provenance a "verbose" Session would.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        silent_root = Path(tmp) / ".reed"
        silent_flow = Flow()
        silent_flow.add(track_temperature)
        silent_session = silent_flow.session(storage_root=str(silent_root), observability="silent")
        silent_session.feed(SensorReading(celsius=50.0))
        silent_session.push()

        from reed.observability.replay import load_recordings

        run_dir = silent_root / "runs" / silent_session.execution_id
        recordings = load_recordings(run_dir)
        print(
            f"\nobservability='silent' + storage_root=... -- terminal was "
            f"silent, but {len(recordings)} Recording(s) were still durably "
            "persisted (silence is a terminal presentation choice, never a "
            "collection choice)."
        )


    # ------------------------------------------------------------------
    # Milestone O8: structured logging + terminal rendering visual grammar.
    #
    # `on_artifact_generated`/`on_artifact_consumed` (reed.observability.
    # presenter) render the same Node -> Artifact -> Repository fact
    # `_emit_generated_provenance_event`/`_emit_used_provenance_events`
    # already observe -- "propagation" is the compact normal-mode grammar,
    # "verbose" adds explicit CONSUME/RECORD/COMMIT operation labels.
    # `StructuredLogPresenter` (reed.observability.logging) turns the same
    # hook calls into stable-field `LogEvent` dicts -- never scraped from
    # terminal strings.
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("Milestone O8: structured logging and terminal rendering")
    print("=" * 78)

    from reed.observability.logging import StructuredLogPresenter
    from reed.observability.presenter import CompositePresenter, TerminalPresenter
    from reed.observability.presentation import resolve_presentation_policy

    for label, preset in (("normal (propagation)", "propagation"), ("verbose", "verbose")):
        print(f"\n--- {label} " + "-" * (40 - len(label)))
        o8_flow = Flow()
        o8_flow.add(track_temperature)
        o8_flow.add(detect_anomaly)
        o8_session = o8_flow.session(observability=preset)
        o8_session.feed(SensorReading(celsius=91.3))
        o8_session.push()

    print("\n--- structured representation of the same events " + "-" * 10)
    captured_events: list[dict] = []
    o8_flow = Flow()
    o8_flow.add(track_temperature)
    o8_flow.add(detect_anomaly)
    o8_session = o8_flow.session(observability="silent")
    o8_session._presenter = CompositePresenter(
        [
            TerminalPresenter(resolve_presentation_policy("silent")),
            StructuredLogPresenter(sink=captured_events.append),
        ]
    )
    o8_session.feed(SensorReading(celsius=91.3))
    o8_session.push()
    import json as _json

    for event in captured_events:
        print(_json.dumps(event))

if __name__ == "__main__":
    main()
