# Reed Logging &amp; Terminal Rendering — Design Record (Issue #8)

## 1. Problem

Issue #7 gave Reed a rigorous observation model (Execution Trace, Data Provenance,
Instrument/Recording) and a `Presenter`/`PresentationPolicy` terminal layer that
consumes it. What it deliberately did *not* give Reed:

- a **stable, machine-readable structured event schema** a future JSON/OTel-logs/other
  sink could consume without depending on terminal string formatting;
- a **denser, more legible terminal visual language** — the current `TerminalPresenter`
  (`reed.observability.presenter`) prints plain `-> node_id` / `✓ node_id (12.3ms)`
  lines; it never shows artifact publication (Node → Artifact → Repository), so a
  reader cannot visually scan a run's data flow the way the legacy (pre-Issue-4)
  `EventRenderer` let them.

Issue #8 closes both gaps without opening a second observability model.

## 2. Historical context (UX reference only)

No literal source for the legacy `EventRenderer` survives in git history (searched full
history for `EventRenderer`/`Depot`/`Outpost`/`Parcel` renderer code; only prose
references remain, in `docs/observability_design.md` Section 1 and Section 19). Its
described visual language, which this design borrows as *aesthetic*, not architecture:

- one compact line per event, `●` activity marker, semantic color per category;
- short correlation ids (`DEPOT#p:3 → BROADCAST#p:1`) rather than full UUIDs;
- arrows (`→`) showing direction of data movement;
- high information density, no `[INFO]`-style narration, no large panels/tables for
  ordinary per-event output.

What is explicitly **not** reused: the `Bus`/`Depot`/`Outpost`/`Parcel` architecture, its
live-subscription model, or its message-traffic vocabulary (`DEPOT_REGISTRY`, etc.) —
all retired at Milestone 3 / Issue #4, and Issue #7's own non-goals already forbid
reviving them.

## 3. Relationship to observability (no second source of truth)

A structured **log event** is a *projection* of data Reed already collects at the same
semantic boundaries Issue #7 defined — `NodeExecutionIdentity`, `ProvenanceEvent`
("generated"/"used"), `Recording`, and `Run`'s own error/duration bookkeeping. Issue #8
adds:

- `reed.observability.logging.LogEvent` — a frozen dataclass that *represents* one of
  those already-observed facts in a stable, named-field shape suitable for
  serialization (`to_dict()` → JSON-safe `dict`). It is built from existing objects
  (`NodeExecutionIdentity`, `ProvenanceEvent`, `Recording`), never stored as an
  independent record Reed must keep in sync with them.
- `reed.observability.logging.StructuredLogPresenter` — a `Presenter` (the existing
  Issue #7 hook Protocol) that turns each hook call into a `LogEvent` and hands its
  `to_dict()` to a sink callable (default: `print(json.dumps(...))`, i.e. JSON Lines to
  stdout/stderr, or any file/OTel-logs adapter a caller supplies).

Both plug into the *same* `Presenter` hook surface `TerminalPresenter` already uses —
Issue #8 adds no new hook mechanism, no second place `Run` calls into. `Run` still only
knows about "the current `Presenter`" (isolated per `_safe_presenter_call`); a
`CompositePresenter` (new, in `presenter.py`) fans one `Run` out to several concrete
`Presenter`s (e.g. a `TerminalPresenter` for humans + a `StructuredLogPresenter` for a
JSON sink) without `Run` ever knowing more than one `Presenter` exists.

```
Reed runtime (Run)
      |
      +-- Execution Trace / Provenance / Recordings / Framework Errors   (unchanged, O1-O6)
                 |
                 v
      Presenter hooks (on_node_started/finished/error, on_artifact_generated/consumed,
                        on_recording)                          <-- single semantic boundary
                 |
        +--------+--------+
        v                 v
 TerminalPresenter   StructuredLogPresenter
 (human rendering)   (LogEvent -> dict -> sink)
                                 |
                                 v
                          JSON / OTel-logs / future sinks
```

This is the smallest architecture that avoids duplicating a source of truth: nothing new
is *computed*, only *represented* differently for two different consumers of the same
already-existing hook calls.

## 4. Relationship to presentation

`PresentationPolicy` (terminal-only) is untouched in shape; Issue #8 adds one new
dimension, `verbose_ops: bool`, set by the `"verbose"` preset (also settable directly),
controlling whether the terminal shows the compact grammar (Section 6, "normal mode") or
the explicit-operation grammar (Section 6, "verbose mode"). It is a presentation
*detail level*, never a logging *severity* — see Section 7. `StructuredLogPresenter` has
no notion of `PresentationPolicy` at all: whether structured events are emitted is
controlled independently (a caller passes a sink or not), matching the pre-existing
invariant that terminal silence must never imply "stop observing."

## 5. Schema

`LogEvent` (all fields JSON-safe; `to_dict()` drops `None`-valued optional fields):

Stable base fields (every event):
- `timestamp: float` (unix epoch seconds, matches `Recording`/`ProvenanceEvent`)
- `severity: str` (`"info" | "warning" | "error"`)
- `event: str` (a small closed vocabulary — see below)
- `execution_id: str`
- `flow_id: str`
- `node_id: str | None` (absent for publish-level events with no single Node)
- `node_execution_id: str | None`

Event-specific fields, present only on the relevant `event` value:
- `"node_finished"`: `duration: float`
- `"node_error"`: `error_type: str`, `error_message: str`, `duration: float`
- `"artifact_generated"`: `artifact_type: str`, `artifact_version: int`
- `"artifact_consumed"`: `artifact_type: str`, `artifact_version: int`
- `"instrument_recorded"`: `instrument_name: str`, `value: str | int | float | bool`,
  `unit: str | None`, `kind: str | None`

`event` values are a small closed set (mirrors `Instrument.kind`'s own closed-vocabulary
reasoning, `docs/observability_goals.md`): `node_started`, `node_finished`, `node_error`,
`artifact_generated`, `artifact_consumed`, `instrument_recorded`.

Field names deliberately match the existing `NodeExecutionIdentity`/`ProvenanceEvent`/
`Recording` field names verbatim (`execution_id`, `flow_id`, `node_id`,
`node_execution_id`, `artifact_version`, `unit`, `kind`) — no renaming for cosmetic
reasons, so a reader who already knows Issue #7's vocabulary needs to learn nothing new.

## 6. Visual grammar

See `docs/observability_invariants.md` for the corresponding test-enforceable invariants.
Rendering is built with Rich `Text`/style composition (`console.print(Text(...))`),
never preformatted ANSI strings — matching `TerminalPresenter`'s existing approach.

Palette (stable per category, not per-instance):

| Category                         | Style          |
|----------------------------------|----------------|
| activity marker (`●`)            | green (success) / red (failure) / yellow (warning) |
| Node name                        | yellow         |
| Repository / infrastructure      | magenta        |
| Artifact type / version          | bold (default) |
| secondary identity (short id)    | dim / grey     |
| explicit operation label (verbose)| cyan          |

Normal mode (compact — no operation words, no timestamps, no full UUIDs; the arrow and
column position already say "this Node published this Artifact version to the
Repository"):

```
● TrackedReading@v3   (a82f91)   TemperatureTracker → REPOSITORY
● Anomaly@v3          (bc172e)   AnomalyDetector    → REPOSITORY
```

Verbose mode (`verbose_ops=True`) additionally spells out each discrete operation, using
an explicit cyan label — for readers who want the underlying generate/use/record
sequence, not just the net publication:

```
● CONSUME   (a82f91)   SensorReading@v3    → TemperatureTracker
● RECORD    (a82f91)   TemperatureTracker  → Temperature 91.3 °C
● COMMIT    (a82f91)   TemperatureTracker  → TrackedReading@v3
```

`(a82f91)` is `node_execution_id[:6]` — enough to correlate lines from the same firing
without the visual noise of a full UUID; never claimed as a causality marker on its own
(temporal/vertical proximity is not causality — `docs/observability_invariants.md` #9).
Column order is fixed (marker, artifact-or-op, short id, node/flow), so scanning down one
column reads consistently across every line — no information is repeated that is already
implied by column position (no `fired`/`published`/`committed`/`[INFO]`/full timestamps
in normal mode).

Understandable without color: the arrow direction, column order, and `@vN` suffix carry
the same information the color reinforces.

## 7. Detail levels vs. logging severity

Two independent axes, deliberately not merged:

- **Detail level** (presentation-only): `PresentationPolicy`'s existing dimensions
  (`nodes`, `propagation`, `instruments`, `timings`) plus the new `verbose_ops` — *how
  much of what already happened gets shown*, purely a terminal concern.
- **Severity** (`LogEvent.severity`): `info`/`warning`/`error` — a property of the event
  itself (a `node_error` event is always `"error"` regardless of how verbose the
  terminal is). Severity never gates whether a `LogEvent` is emitted; a sink is free to
  filter on it, but `StructuredLogPresenter` itself emits every hook call it receives —
  filtering is a sink concern, matching standard structured-logging practice (Section 9).

This mirrors structlog's own separation of "what happened" (structured event, always
complete) from "how much is shown" (console renderer's own verbosity), rather than
conflating a Python `logging`-style level with terminal presentation detail.

## 8. Failure isolation

`StructuredLogPresenter` is a `Presenter`; `Run._safe_presenter_call` already isolates
every hook call regardless of which concrete `Presenter` (or `CompositePresenter`
fan-out) is installed — a broken sink (e.g. a JSON-encoding error, a closed file handle)
can never affect execution, exactly like a broken `TerminalPresenter` (Issue #7 Slice
O7g, preserved verbatim, tested again in Issue #8's harness for the composite case).

## 9. Extension points

- A new sink (OTel Logs, a file, a queue) is a new `sink: Callable[[dict], None]` passed
  to `StructuredLogPresenter`, never a new hook or a new Run-facing concept.
- A future parallel-execution model: every `LogEvent` already carries
  `node_execution_id`/`execution_seq`-free identity (deliberately no ordering claim baked
  into the schema itself beyond `timestamp`), so concurrent firings each emit their own
  independent events without any schema change.
- `CompositePresenter` accepts any number of `Presenter`s, so a caller can add a metrics
  presenter, a second log sink, etc., without touching `Run`.

## 10. Trade-offs

- `StructuredLogPresenter` defaults to a synchronous `print`-based JSON-lines sink —
  simplest possible default, not a production logging pipeline; a real OTel Logs
  adapter is future work (Issue #8 non-goal: "not implementing every possible logging
  sink").
- The verbose visual grammar's operation vocabulary (`CONSUME`/`RECORD`/`COMMIT`) is a
  judgment call, not derived from any existing Reed vocabulary token — documented here as
  a naming decision, changeable without touching the schema.

## 11. Research influences

(Established knowledge; no live web search available in this environment — noted per
Issue #8's Phase 2c instruction.)

- **structlog**'s core idea — keep the *event* (a dict of key/value pairs) fully
  decoupled from its *renderer* (console vs. JSON) — is the direct model for
  `LogEvent`/`StructuredLogPresenter` vs. `TerminalPresenter` here.
- **OpenTelemetry Logs/Events semantic conventions** favor small, stable, named
  attributes over free-form messages; `LogEvent`'s closed `event` vocabulary and named
  fields (rather than one interpolated string) follow that shape, while intentionally
  not adopting OTel's own attribute names verbatim where Reed already has its own
  (`node_id`, not OTel's generic `span.name`) — Reed's own vocabulary wins per Issue #7's
  existing `otel_export.py` precedent (OTel is "an optional projection, not Reed's
  source of truth", invariant #27).
- **Standard Python `logging` severities** (`info`/`warning`/`error`) are reused
  directly for `LogEvent.severity` rather than inventing a new scale.
- General "human-readable developer logging" guidance (dense, single-line, aligned,
  color-coded, no redundant narration) is what Section 6's grammar follows, and matches
  the legacy `EventRenderer`'s described visual language independently.
