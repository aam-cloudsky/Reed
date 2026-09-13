# Reed Observability — Goals (Desired API and Mechanics)

Status: companion to `docs/observability_design.md` (the full design record, rounds 1-5).
This document distills that record into what is actually to be built: the target public
API, the identity model, the storage mechanics, and the guarantees Reed commits to. Where
this document and `observability_design.md` conflict, `observability_design.md`'s latest
round (17) is authoritative and this document should be updated to match — this file is a
summary for implementers, not a second source of truth.

See also `docs/observability_non_goals.md` for what is explicitly out of scope or rejected.

## 1. Core vocabulary

```
Flow            = observational namespace (logical aggregation across many Executions)
Node            = computational identity within a Flow
Instrument      = observable definition (what can be measured), owned by a Node
Execution (Run) = persistence/correlation boundary (one physical dataset)
NodeExecution   = local execution context (one firing)
Recording       = one observation of one Instrument
execution_seq   = deterministic ordering, not causality
Provenance edge = causality (generated/used)
```

**Instrument is the logical unit of observation; Execution is the physical unit of
persistence; Flow is the logical unit of aggregation and analysis.**

## 2. Desired public API

### 2.1 Declaring an Instrument

```python
speed = Instrument(
    name="speed",
    kind="gauge",           # "gauge" | "counter" | "updown_counter"
    unit="m/s",
    description="Aircraft ground speed",
)
```

`kind`, `unit`, and `description` are declared once, not repeated on every call.

### 2.2 Attaching Instruments to a Node

```python
flow.add(
    update_aircraft,
    instruments=[speed, altitude],
)
```

This is the **primary, recommended path**. It gives Reed the full observability surface of
a Flow before any execution runs — every Instrument a Node will ever emit, with its
`kind`/`unit`/`description` — which is what makes a `reed describe <flow>`-style
introspection tool possible.

A Node may omit `instruments=` entirely and use `ctx.record(name, value, ...)` with a plain
string name instead (see 2.4) — pure lazy/prototyping mode, no explicit `Instrument` object
required.

### 2.3 Recording an observation

**Preferred style (Milestone O7 self-containment audit):** reference a declared Instrument
by its plain string name, not the `Instrument` object itself:

```python
def update_aircraft(ctx, aircraft):
    ...
    ctx.record("speed", aircraft.speed)
```

`ctx.record("speed", ...)` resolves purely against `update_aircraft`'s own FlowNode-declared
schema (`flow.add(update_aircraft, instruments=[speed, altitude])`) -- the Node body needs no
import of, or reference to, the `speed` object at all. This keeps the Node function
self-contained: it depends only on a name it and the composition call agree on, the same way
a logger call depends on a string key, not on a shared global object. It also means the same
Node function can be composed into a different Flow with a differently-configured Instrument
for the same name (different `unit`, say) with zero change to the Node body.

Passing the `Instrument` object itself still works, for callers who prefer it (e.g. to reuse
one Python object as the single source of truth for a name used in several places):

```python
ctx.record(speed, aircraft.speed)
```

but it is always validated against the FlowNode's own declared schema, never trusted
directly -- an `Instrument` object that was never declared via `instruments=[...]`, or whose
`kind`/`unit` contradicts what was actually declared for that name, raises `ValueError`
rather than silently overriding the declaration.

or, in lazy mode:

```python
ctx.record(name="reason", value="conflict avoidance")
```

Rules:
- `ctx.record(...)` returns immediately (synchronous call, asynchronous persistence — see
  Section 5).
- `value` is **scalar only**: `str | int | float | bool`. No mappings, no dataclasses, no
  nested structures.
- A compound fact (e.g. a 3D velocity) is multiple explicit calls with dot-segmented names
  (`velocity.x`, `velocity.y`, `velocity.z`) — never a single call with a nested value, and
  never automatic array-splitting by Reed.
- If a Node declared an explicit `instruments=` list, calling `ctx.record(...)` with a name
  not in that list is an error at first call — no silent ad hoc registration once a Node has
  opted into explicit declarations.
- In lazy mode, the first observed `kind`/`unit` for a given `name` is authoritative; a
  later call for the same `name` with a different `unit` raises.
- `ctx.record()` never accepts or exposes OTel/Grafana vocabulary directly
  (`ctx.metrics.gauge(...)`, `ctx.otel.span(...)`, `ctx.grafana.add_chart(...)` do not
  exist). The only vocabulary on `ctx` is Reed's own.
- `ctx.record()` contains only information explicitly recorded by application code —
  exceptions and cancellations are never injected into it (Section 6).

### 2.4 Node identity is separate from its display name

```python
flow.add(update_aircraft)   # node_id assigned by Reed; node_name = "update_aircraft"
```

`node_id` is the real identity (used in `instrument_id`, in every Recording/Provenance row).
`node_name` (defaulting to the wrapped function's `__name__`) is a display label only, and
is **not required to be unique** — two Nodes named identically, in the same or different
Flows, are not an error. Composition fails only if it violates the real invariant: within a
Flow, each Artifact type has exactly one producer.

## 3. Identity model

```
execution_id       -- one Run instance (UUID, minted in Run.__init__)
flow_id            -- one logical Flow definition, deterministically derived from its
                       registered nodes (Flow.flow_id) -- stable ACROSS separate process
                       runs of "the same" Flow as of Milestone O1, Slice O1a; see
                       observability_design.md Section 18
node_id            -- one FlowNode within a Flow, deterministically derived from the
                       wrapped function's module + qualname (FlowNode.node_id) -- same
                       stability property as flow_id (Section 18)
node_execution_id  -- one firing of one Node within one Run
instrument_id       = (flow_id, node_id, instrument_name)
execution_seq      -- monotonic counter per execution_id, incremented once per
                      node_execution_id minted; a DETERMINISTIC OBSERVATION ORDER, never a
                      causality claim
record_id           = (node_execution_id, name, seq)  -- seq: monotonic counter scoped to
                      one node_execution_id
```

`NodeContext` gains a small, read-only identity bundle (no back-reference to `Run`/`Flow`/
`NodeRuntime`) so `ctx.record(...)` can attach `execution_id`/`node_execution_id` without
every call site passing them manually.

## 4. Two observability levels, two different guarantees

| | Level 1 — Execution Trace / propagation | Level 2 — Recordings + Provenance |
|---|---|---|
| What | which Node fired, in response to what | user-declared Instrument observations; artifact generated/used events |
| Persistence | in-memory ring buffer, optional debug-log mirror; **not required to be durable** | durable, tabular, one file per Execution |
| Consumer | live/replayable terminal renderer | `reed query`, `reed graph`, OTel/Grafana exporters, spreadsheets, DuckDB/Polars |

## 5. Durability boundary (explicit contract, not an absolute claim)

> Recordings accepted during a `NodeExecution` are guaranteed to be durably flushed when
> that `NodeExecution` exits — normally, exceptionally, or through cancellation. A hard
> process crash before that durability boundary may lose the current in-flight batch.

Flush happens in a `finally`-equivalent block wrapping the Node body, covering success,
exception, and cancellation paths alike — never only the happy path. This is not the same
as an absolute "never lossy" guarantee, which is not achievable without an `fsync` per call
(which would destroy the hot-path latency the synchronous, non-blocking `ctx.record()` call
is designed to protect).

## 6. Storage mechanics

```
.reed/
├── flows/
│   └── <flow_id>/
│       └── instruments.json      -- static, derived from Flow composition; write-once-
│                                     if-absent, or generated on demand; not rewritten by
│                                     every ordinary run
│
└── runs/
    └── <execution_id>/
        ├── manifest.json         -- indexes the files below + their schema_version
        ├── recordings.csv        -- ONE file per Execution (not per Node, not per
        │                            Instrument): long/tidy, instrument_id is a data
        │                            column, never a filename or column header
        └── provenance.csv        -- normalized generated/used event log
```

`recordings.csv` columns: `instrument_id, value, timestamp, execution_id, flow_id, node_id,
node_execution_id, execution_seq, attributes`. `attributes`, if present, is a single
JSON-string cell — the only field allowed to be "structured."

`provenance.csv` columns: `event_type ("generated"|"used"), artifact_id, artifact_version,
node_execution_id, node_id, timestamp, execution_seq`. A producer/consumer graph is
reconstructed by grouping on `(artifact_id, artifact_version)` — never a wide row with
multiple consumer columns.

Both files: append-only, crash-safe (flush+fsync per batch; a reader must tolerate and
discard a truncated final line rather than fail the whole parse).

`RecordingStore`/`ProvenanceStore` are logical interfaces; CSV is the V1 implementation.
Partitioning (by Instrument, by time chunk) or switching to Parquet are implementation
swaps behind that interface, never a change to `ctx.record()` or to what a `Recording`
means.

## 7. Cross-Execution querying: a Flow-level view without a Flow-level file

No physical file is shared across Executions of the same Flow (avoids cross-process
write contention and unbounded growth). Cross-run analysis is a **query-time** concern:

```sql
SELECT *
FROM read_csv('.reed/runs/*/recordings.csv')
WHERE flow_id = ? AND instrument_id = ?
ORDER BY timestamp;
```

DuckDB (or Polars) globbing multiple CSV/Parquet files gives "how did `aircraft.speed`
behave across the last 50 Executions of this Flow" without Reed needing to maintain a
shared, contended file or a database of its own.

## 8. OTel and other exporters are projections, never the source of truth

- OTel (`TracerProvider`/`SpanProcessor`/`SpanExporter`) is one optional consumer, translating
  Reed's own Run/NodeExecution/Trigger events into OTel spans/links/events via a dedicated
  adapter. Reed's own `execution_id`/`node_execution_id`/etc. are authoritative; OTel's
  `trace_id`/`span_id` are a derived, optional projection.
- Only Instruments of `kind` `"gauge"`/`"counter"`/`"updown_counter"` are eligible for
  projection into an OTel Metric — the mapping is explicit and opt-in per Instrument, never
  inferred from a value's Python type.
- The terminal renderer that replaces the pre-Issue-4 Bus/Depot tracing output is built as a
  consumer of Level 1 (the live ring buffer), optionally also reading `recordings.csv`/
  `provenance.csv` for post-hoc replay.
- A provenance-graph tool (`reed graph <execution_id>`, or similar) is a separate CLI
  consumer of `provenance.csv` — never baked into Reed's core — that can render a terminal
  tree, a Mermaid/DOT diagram, or a standalone HTML report.

## 9. Sequencing and pipeline discipline (from the concurrency/failure-isolation work)

- Each registered sink/exporter is called inside its own try/except; one broken sink never
  breaks the Node body being observed or any other sink.
- `ctx.record(...)` appends to an in-memory buffer / queue and returns immediately; the
  actual write to the local record and any network export happen off that path, batched.
- The buffer is a single-consumer append-only queue, not a shared mutable dict — this is
  what makes concurrent Node executions (of different Nodes) safe without per-call locking.
- The recording pipeline (buffer + writer + exporters) is instantiable fresh per `Run`, not
  a process-wide singleton.
- Sampling/decimation for high-frequency recordings is an explicit, opt-in policy, separate
  from the durability guarantee.

## 10. Open items this document does not resolve (tracked in `observability_design.md`
Section 17/18/19, not repeated here in full)

- `flow_id`/`node_id` cross-run stability is now resolved (Milestone O1, Slice O1a;
  Section 18) — no longer an open item.
- Non-metric, non-Instrument facts are now resolved (Milestone O2, Slice O2e; Section 19):
  a `Recording` produced in lazy mode (no `Instrument`) always has `kind=None` — no longer
  an open item.
- Whether registration-order changes alone should count as a new `flow_id` (Section 18.4's
  narrowed remainder of Section 17.2) — still open, non-blocking.
