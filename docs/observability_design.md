# Reed Observability: Design Decision (Issue #7)

Status: **DRAFT — architectural decision and implementation plan, not yet implemented.**
Author: drafted by Claude (Sonnet 5), for review by Davi / Instituto Curvelo.
Scope: tracing, provenance, structured recording, and local/offline persistence of Reed
execution. Out of scope: a LangSmith-like UI, MCP integration, automated trace analysis
(explicitly deferred by Issue #7 itself).

---

## 1. Motivation

Before the Issue #4 refactor, Reed had a working, visually rich observability path built
directly into the `Bus`/`Depot`/`Outpost` machinery: trace IDs correlated request/reply
message traffic (`DEPOT_REGISTRY`, `DEPOT_GET`, `DEPOT_SET`), and `EventRenderer` produced
Rich-formatted terminal output showing `joined`/`synced` states and broadcast fan-out
(`DEPOT#p:3 → BROADCAST#p:1`) per Outpost. That system was tightly coupled to the legacy
Bus-based execution path and was correctly *not* preserved as-is when that path was removed
in Issue #4 — it answered a narrower question ("what happened on the bus") than what Reed
now needs to answer ("what happened during this Run, across which Nodes, over which
Artifacts, and why").

Issue #7 asks for something structurally different and more durable: a persistent,
machine-readable execution record, built on OpenTelemetry vocabulary and semantics where
they fit, that can (a) reconstruct causal execution history, (b) reconstruct data
provenance, (c) carry arbitrary structured recordings an application chooses to emit, and
(d) still support the terminal-rendering experience that was lost, as one projection among
several.

The guiding principle, taken directly from the issue and preserved here as the load-bearing
constraint on everything that follows:

> Reed defines what an execution means; OpenTelemetry provides the infrastructure to
> instrument, correlate, record, and export it.

This document treats that principle as a hypothesis to be checked, not a foregone
conclusion — per the explicit instruction to critically evaluate rather than assume the
proposed design is correct. Section 9 records where the hypothesis holds, and where it
needed revision.

## 2. Reed's current baseline (as of this branch)

Confirmed by direct inspection of `src/reed/composition/node/node_context.py`,
`src/reed/execution/run.py`, `src/reed/composition/flow/flow_node.py`, and
`src/reed/execution/artifact_record.py`:

- `NodeContext` is deliberately minimal: `__slots__ = ("_memory", "_last_output")`. It has
  no reference back to `NodeRuntime`, `Run`, or `Flow` (architectural invariant #26 forbids
  this).
- `Run` holds `_flow`, `_repository`, `_node_runtimes`, `callback_failures`,
  `_pending_callback_coroutines`, `_last_known_values`, `_fresh_since_last_firing`. None of
  these are identifiers; there is no `run_id`.
- `FlowNode` carries `definition`, `trigger_policy`, `on_output` — no node id.
- `ArtifactRecord` / `ArtifactVersion` / `ArtifactProvenance` already carry a provenance
  notion (which artifact version produced/depended on which), but it is scoped to the
  artifact repository, not to a Run-wide causal trace, and it has no timestamp/duration/
  exception model.

**Conclusion:** every identifier this design proposes — execution id, flow id, node id,
node-execution id, trace id, span id — is a net-new addition to Reed's runtime model, not
an extension of something partially built. This matters because it means the design is free
to choose the *right* shape rather than being constrained by an existing half-built one, but
it also means nothing below should be read as "already partially there."

## 3. Two established prior-art lineages, and why both matter

Two independent lineages converge on the same shape, which is itself evidence about what
the right shape is.

**Lineage A — observer/callback fan-out (Python `logging.Handler` → LangChain
callbacks).** Python's `logging.Handler` established the pattern: a `Logger` fires an
event; a list of registered `Handler`s each decide independently what to do with it.
LangChain's `BaseCallbackHandler` / `AsyncCallbackHandler` reused this shape almost exactly:
a list of handlers in `config["callbacks"]`, each implementing lifecycle methods
(`on_chain_start/end`, `on_tool_start/end`, `on_llm_end`, etc.); one logical event fires
once, every handler is notified, and `LangChainTracer` (which is what makes LangSmith work)
is *just another handler in that same list* — not a distinguished or privileged mechanism.
This is the right model for "one thing happened, an open-ended set of parties may care."

**Lineage B — pipeline/exporter separation (OpenTelemetry `SpanProcessor`/
`SpanExporter`).** OTel's `TracerProvider` registers one or more `SpanProcessor`s. A
processor decides *when and how* to hand spans off to its own `SpanExporter` (console,
OTLP, Jaeger, ...). Critically, the *instrumented application code never knows which
backends exist* — it only ever talks to a `Span`/`Tracer`. The processor/exporter split
exists specifically to move the expensive part (network I/O, batching, retry) off the hot
path.

These are not competing designs; they solve different halves of the same problem. Lineage A
answers "how does the producer notify consumers without either knowing about the other's
implementation." Lineage B answers "how do you keep that notification cheap and safe when
some consumers are slow, remote, or unreliable." Reed needs both: a `logging.Handler`-style
fan-out at the point where the application emits a recording, and an OTel-style
processor/exporter split at the point where that recording is turned into bytes on a wire
or a disk. Conflating them — e.g. letting the application call directly into an exporter —
reproduces the exact hot-path-blocking failure mode OTel's split exists to avoid.

**Lineage C — provenance modeling (W3C PROV-O / ProvONE).** The W3C PROV data model
(entities, activities, agents, `wasGeneratedBy`, `used`, `wasDerivedFrom`) and its
scientific-workflow specialization ProvONE are the mature prior art for exactly the
"Data Provenance" view Issue #7 asks for (Node A → Parcel/Artifact → Node B). Reed's
`ArtifactRecord`/`ArtifactProvenance` is already a PROV-shaped model in miniature: an
`ArtifactVersion` is a PROV *entity*, a `NodeExecution` is a PROV *activity*, and
"artifact X was generated by execution Y, which used artifact Z" is exactly
`wasGeneratedBy`/`used`. This document does not propose adopting PROV-O's RDF/OWL
machinery — that would be a large, unjustified dependency for Reed's current scale — but it
does propose keeping Reed's provenance edges shaped so a PROV export is a small, later
projection rather than a rewrite. This is the same "exporters are projections, not the
source of truth" principle the user already arrived at independently for recordings
(Section 6, open question 15), and it should apply uniformly to all three views, not only
to recordings.

Sources consulted: [OpenTelemetry Traces concepts](https://opentelemetry.io/docs/concepts/signals/traces/), [OpenTelemetry trace semantic conventions](https://opentelemetry.io/docs/specs/semconv/general/trace/), [opentelemetry.sdk.trace.export (Python)](https://opentelemetry-python.readthedocs.io/en/latest/sdk/trace.export.html), [W3C PROV family overview](http://homepages.cs.ncl.ac.uk/paolo.missier/doc/PROV-Tutorial-paper.pdf), [ProvONE data model](https://purl.dataone.org/provone-v1-dev), and LangChain's own callbacks reference (`reference.langchain.com/python/langchain-core/callbacks`), already gathered by Davi prior to this document.

## 4. The three complementary views

Issue #7 and the proposal converge on three views of the same underlying execution, which
this document adopts unchanged as the right decomposition — this is the one part of the
proposal that needed no revision:

1. **Execution Trace** — the causal shape of *what ran, in what order, caused by what*.
   `Run` → root Span; `NodeExecution` → child Span; `Trigger` → the edge/attributes that
   explain why a Node fired. Hierarchical by default (a Run contains Node executions),
   with **Span Links** used specifically for the non-hierarchical case: fan-in (a Node
   firing because two independent upstream Nodes both changed) and fan-out where a single
   upstream change causes siblings to fire "in parallel" rather than in a parent-child
   relationship.
2. **Data Provenance** — the causal shape of *what data came from what*. Node A produces
   Artifact P; Node B consumes P and produces Q. This is PROV/ProvONE-shaped (Section 3),
   and in Reed maps onto `ArtifactRecord`/`ArtifactVersion`/`ArtifactProvenance`, extended
   to carry the producing/consuming `node_execution_id`s so provenance edges can be walked
   independently of the trace tree.
3. **Recordings** — arbitrary structured application data emitted during execution that is
   neither a trace-shape fact nor a provenance-shape fact: a planner's decision, a scalar
   time series (aircraft speed), a snapshot of intermediate state. This is Issue #7's
   `ctx.record(...)` surface, evaluated in Section 6.

All three are correlated through one shared execution context (Section 5).

**Note (corrected by Section 11.1, restated here so this section is not misleading on its
own):** the three views do **not** all share one uniform persistence contract. Execution
Trace (view 1) is ephemeral/best-effort by default — a live or replayable projection over a
Run, not a durable artifact Reed commits to keeping. Data Provenance (view 2) and Recordings
(view 3) are both durably persisted, as **two separate tabular stores** (Section 8 gives the
concrete layout: `recordings/<node_name>.csv` per Node, and a Run-level `provenance.csv`),
correlated by the same identity columns (`execution_id`, `node_execution_id`, ...) rather
than physically merged into one file. This is the corrected, narrower reading of open
question 15: Recording and Provenance are both first-class, Reed-owned, and durable;
Execution Trace is Reed-owned but not required to be durable.

## 5. Execution identity: the part everything else depends on

Before any recording, span, or provenance edge can be correlated, Reed needs identity that
does not exist today (Section 2). This is the one piece of net-new runtime state this
design requires Reed to add, and it is intentionally small:

- `execution_id` — identifies one `Run` instance (today: nothing; proposed: a UUID assigned
  in `Run.__init__`).
- `flow_id` — identifies the `Flow` definition being run (stable across Runs of the same
  Flow; useful for dashboards that aggregate across Runs).
- `node_id` — identifies a `FlowNode` within a Flow (stable across firings).
- `node_execution_id` — identifies one firing of one Node within one Run (this is the OTel
  Span-equivalent unit).
- `trace_id` / `span_id` — OTel's own identifiers, generated when (and only when) OTel
  export is active; Reed's own IDs above are authoritative and OTel's are a derived,
  optional projection (see Section 8, "OTel coupling").

Placement: `execution_id` and `flow_id` belong on `Run` (or a small `ExecutionContext`
value object `Run` owns); `node_id` belongs on `FlowNode` (a stable id assigned at
composition time, not at runtime); `node_execution_id` is minted once per firing by
`NodeRuntime` immediately before invoking the Node body, and is the value threaded into
`NodeContext` for the duration of that firing.

This last point requires a deliberate, narrow exception to architectural invariant #26
("`NodeContext` has no reference back to `Run`/`Flow`/`NodeRuntime`"). This document
proposes narrowing the invariant, not deleting it: `NodeContext` continues to hold no
*reference* to those objects (no `ctx.run`, no way to reach the `Flow` or mutate runtime
state through `ctx`), but gains a small, read-only, string/UUID-only identity bundle
(`ctx.execution` or similar) purely for correlation. This is a materially smaller surface
than a back-reference, and it is the minimum needed for `ctx.record(...)` to attach
`execution_id`/`node_execution_id` to what it emits without every call site having to pass
those values manually. If the maintainers judge even this too much, the fallback is to
thread identity as an explicit parameter to `ctx.record(...)` rather than storing it on
`ctx` — Section 9 records this as an open decision for review, not a foregone one.

## 6. `ctx.record(...)` — critical evaluation

The proposal's `Recording` shape:

```python
ctx.record({
    "name": "aircraft.speed",
    "value": aircraft.speed,
    "unit": "m/s",
    "attributes": {"aircraft_id": aircraft.id},
})
```

with `data` (name/value/unit?/description?/attributes?, application-owned) separated from
`context` (timestamp/execution_id/flow_id/node_id/node_execution_id/trace_id/span_id,
Reed-owned), plus a `schema_version`.

**What is right about this shape, and should be kept:**

- The data/context split is correct and should be enforced structurally (two dataclasses,
  not one flat dict), because it is exactly the boundary between "what the application
  wants to say" and "what Reed needs to say regardless of what the application wants." This
  mirrors OTel's own separation of a span's application-set attributes from its
  infrastructure-set trace context, and Reed should not blur it the way a single flat dict
  would.
- Rejecting `ctx.metrics.gauge(...)` / `ctx.otel.span(...)` / `ctx.grafana.add_chart(...)`
  is the correct call. Exposing backend vocabulary on `ctx` would let OTel's data model leak
  into application code that should only ever depend on Reed's model — precisely the
  coupling Issue #7's own risk list warns against ("OTel coupling").
- Modeling this after Stable-Baselines3's `logger.record(key, value)` is a good instinct
  for the *call-site ergonomics* (one call, no ceremony, works from inside a hot loop), but
  SB3's logger is metrics-only (scalars/images/videos for TensorBoard); Reed's `Recording`
  needs to carry arbitrary structured `value` (a dict, a dataclass, not just a scalar), so
  the analogy should stop at "single flat call, no backend vocabulary" and not be extended
  to "the value is always a number."

**Where this document disagrees with or sharpens the proposal:**

- **Name+value should not both be required.** Forcing every recording into
  `{name, value}` reproduces exactly the "too rigid" failure mode the proposal's own
  spectrum diagram warns about: a planner emitting `{"chosen_action": "climb", "reason":
  "conflict avoidance", "candidates": [...]}"` has no single `value`. The fix is not to loosen
  the schema to accept arbitrary top-level fields (that reproduces the "too loose"
  failure mode on the other end) — it is to make `value` polymorphic: a `Recording` has a
  `name` (required — this is what makes recordings queryable and dashboard-able, and is non-
  negotiable) and a `value` that may be a scalar, a mapping, or a dataclass instance, with
  Reed responsible only for making sure whatever it is is serializable, not for
  understanding its shape.
- **Schema evolution needs a policy stated now, even though it's not implemented now.**
  Because recordings are meant to be a *persistent, machine-readable execution record*
  (Issue #7's own words), and both `name` vocabularies and `attributes` shapes will change
  as an application evolves, the stored record needs `schema_version` at the `Recording`
  level (already proposed) plus a documented compatibility rule: consumers of the local
  record must tolerate unknown `attributes` keys and must not fail hard on an unrecognized
  `name`. This is the same rule structured-logging practice converges on independently
  (append-only, additive-only fields) and it should be written down before the first
  consumer is built, not discovered after one breaks.
- **High-cardinality attributes are a distinct, separately-flagged risk, not folded into
  general "excessive telemetry."** An `attributes` dict is exactly where a well-meaning
  caller puts something like `request_id` or a raw floating-point sensor reading — both of
  which are catastrophic as OTel metric *labels* (metric cardinality explosion) even though
  they are perfectly fine as span/event attributes or as free-form recording data. This
  document's recommendation: Reed's own record format places no cardinality limit on
  `attributes` (that would defeat the purpose for the non-metric use cases), but the
  **metrics exporter specifically** must apply an explicit allow-list or cardinality guard
  before promoting any `attributes` key to a metric label, and must default to *not*
  exporting a recording as an OTel metric at all unless the application has explicitly
  marked it as one (see next point).
- **Not every Recording is a metric, and the export mapping must be opt-in, not inferred.**
  Guessing "a numeric value → export as an OTel gauge" from shape alone is fragile (a
  `value` of `{"latitude": 1, "longitude": 2}` is numeric but is not a gauge). The mapping
  from `Recording` → {OTel metric, OTel span event, OTel log record, Reed-native-only}
  should be a small, explicit, per-`name` (or per-namespace) configuration the application
  supplies to the exporter, not inferred by the exporter from the value's Python type. This
  keeps the exporter dumb and the application's intent explicit, and it directly answers
  open question 7.
- **Delivery guarantees must be declared per event category, not globally.** The
  "engineering lessons" Davi supplied are correct and this document adopts them as binding
  constraints on the implementation, not just as anecdotes: (a) each registered
  sink/handler must be called inside its own try/except so one broken sink cannot break the
  Node body being observed — this is non-negotiable, mirroring both `logging.Handler`'s and
  LangChain callback runners' isolation; (b) the local, offline execution record (the
  durable store) is not allowed to be on a lossy path — writing to it must be treated like
  `_persist()` in Davi's own prior lesson, i.e., best-effort delivery is acceptable for
  *remote* exporters (OTLP endpoint down, Grafana unreachable) but never acceptable for the
  local record itself, because the local record is the source of truth every exporter
  reads from (Section 13.2 states the precise durability boundary this implies -- not an
  absolute zero-loss guarantee across a process crash, but a guarantee bounded by
  `NodeExecution` exit); (c) recordings emitted at very high frequency (a per-tick sensor value) need
  an explicit, opt-in sampling/decimation policy distinct from the durability guarantee —
  durability says "don't lose it," sampling says "don't record every one," and conflating
  them leads to either silently-lossy critical events or an unbounded local record.
- **State leaking by run_id, and the "second door," both apply directly to Reed and must
  be designed against from day one.** Because `node_execution_id` is minted at Node-firing
  start and a Node can raise, be cancelled, or (once Reed supports concurrent Node
  execution) run concurrently with other firings, any correlation table keyed by
  `node_execution_id` that is written at start and read-and-removed at end will leak or
  double-free exactly as Davi's prior lesson describes. The fix already implied by
  Section 5's design is to avoid a separate correlation table entirely: `node_execution_id`
  is generated once and threaded through `ctx` for the lifetime of that call, so there is no
  start/end pair to keep in sync — the identity is carried by the call stack, not looked up
  by a side table. Where a side table is unavoidable (e.g., matching an async span's start
  and end across an await boundary in the OTel exporter specifically, not in Reed's own
  core), it must use a bounded structure with a TTL or explicit cleanup on both the normal
  and the exceptional path, per the same lesson. "Second door" events — a Node execution
  that is cancelled or crashes before it ever calls `ctx.record(...)` or reaches a normal
  `on_output` — must be a declared category on `NodeRuntime`'s own execution-span lifecycle
  (start span → {normal end, exception end, cancellation end}) from the beginning, not
  bolted on after the first crash is observed to have never closed its span.
- **`ctx.record(...)` should be synchronous from the caller's perspective; persistence and
  export must not be.** This directly answers open question 13 and is the same argument as
  OTel's own processor/exporter split (Section 3, Lineage B): the call inside the Node body
  must return immediately (append to an in-memory buffer / fire-and-forget to a queue), and
  the actual write to the local record and any network export happen off that path,
  batched, exactly as `BatchSpanProcessor` does for spans today. This is required, not
  optional, given Reed's own hot-path-latency concerns for Node execution.
- **Concurrency**: any shared structure the recording pipeline touches (the in-memory
  buffer, the local record writer) must be safe under Reed's actual concurrency model —
  today, sequential-but-async Node execution; in the future, potentially concurrent
  firings. The buffer should be an append-only queue with a single consumer (the
  batching writer), not a shared mutable dict, which sidesteps most of the concurrency
  hazard by construction rather than by locking.
- **Testability**: the recording pipeline (buffer + writer + exporters) must be
  instantiable fresh per `Run`, not a process-wide singleton, exactly per Davi's own
  singleton/testability lesson — otherwise two tests running Flows in the same process
  will observe each other's recordings.

## 7. Answers to the 15 open questions

1. **Is `Recording` the right abstraction/name?** Yes, kept, with the scope broadened per
   Section 6 (value may be structured, not only scalar).
2. **Required fields: name+value, or arbitrary data?** `name` required; `value`
   polymorphic (scalar, mapping, or dataclass) rather than strictly required to be a single
   scalar. See Section 6.
3. **How much schema should Reed impose?** The `data`/`context` split, `name`,
   `schema_version`, and a serializability requirement on `value`/`attributes`. Nothing about
   the *meaning* of `name` or the shape of `attributes` beyond "must serialize."
4. **Should data/context be explicitly separated?** Yes, as two dataclasses, not a flat
   dict. Confirmed in Section 6.
5. **Should trace/span IDs be persisted directly or referenced?** Persisted directly on the
   `context` (cheap, denormalized, avoids a join to reconstruct a recording's trace
   position), but understood as a *projection of* Reed's own `execution_id`/
   `node_execution_id`, which remain authoritative. See Section 8.
6. **How should scalar vs. structured values differ?** They don't differ structurally —
   both live in `value` — but the metrics exporter (Section 6) only promotes scalar-shaped,
   explicitly-marked recordings to OTel metrics; structured values are exported as span
   events / log records / Reed-native only.
7. **How should OTel mapping work?** Explicit, opt-in, per-name/namespace configuration
   supplied to the exporter — never inferred from the Python type of `value`. See Section 6.
8. **Should exporters be allowed to lose information?** Remote/network exporters: yes,
   best-effort, by design (matches OTel's own delivery model). The local execution record:
   no, within the durability boundary stated precisely in Section 13.2 (durable as of
   `NodeExecution` exit, not as of the `ctx.record()` call itself) — it is the source of
   truth every exporter reads from, not the live call site.
9. **Sampling/filtering for high-frequency recordings?** An explicit, opt-in
   sampling/decimation policy, configured per recording name/namespace, separate from and
   layered on top of the durability guarantee — never inferred automatically from
   frequency.
10. **Schema evolution for long-lived records?** `schema_version` per `Recording`,
    additive-only field evolution, consumers must tolerate unknown `attributes` keys and
    unknown `name`s. Written down now (Section 6) rather than discovered after a breakage.
11. **High-cardinality attributes?** No limit in Reed's own record; an explicit allow-list/
    cardinality guard specifically in the metrics exporter before any `attributes` key is
    promoted to a metric label. See Section 6.
12. **Delivery guarantees?** Per-category, not global: local record = durable as of
    `NodeExecution` exit (Section 13.2's explicit boundary, not an absolute guarantee across
    a process crash); remote exporters = best-effort/configurable, isolated per-sink via
    try/except so one broken sink never affects the Node body or any other sink.
13. **Sync call, async persistence/export?** Yes — `ctx.record(...)` returns immediately;
    persistence and export are buffered/batched off that path, mirroring
    `BatchSpanProcessor`.
14. **Interaction with parallel `NodeExecution`s?** Handled by not keying correlation off a
    mutable side table (Section 6's "state leaking" point); `node_execution_id` is
    thread/task-local via the call stack, not looked up. Any side table an exporter needs
    internally must be bounded/TTL'd.
15. **Should `Recording` be part of the persistent Execution Record?** Yes — and this
    document generalizes the same answer to Trace and Provenance (Section 4): all three are
    first-class, Reed-owned, persisted locally; OTel/Grafana/CSV/JSONL are projections over
    that persisted record, never the record itself.

## 8. The local execution record and OTel's role (revised, round 4: single
recordings store per Run, normalized provenance event log, provenance graph rendering)

This document proposes, per the corrected split in Section 11.1:

- **Level 1 (Execution Trace / propagation)**: an in-memory ring buffer per `Run`, scoped
  to the live process. Optionally mirrored to a plain debug log for post-mortem reading.
  Not a required, schema-committed artifact -- it may be dropped when the process exits
  without anyone having asked for it to be kept.
- **Level 2 (Recordings + Provenance)**: two separate durable, tabular stores under
  `.reed/runs/<execution_id>/` (one directory per Run -- i.e. per Flow execution; see the
  storage-partitioning correction below for why this is one flat store, not one file per
  Node):
  - `recordings.csv` -- **one file for the whole Run** (round-4 correction to the earlier
    "one file per Node" decision; see below), one row per `ctx.record(...)` call, shape
    fixed by Section 11.2, filterable by `node_id`/`node_name` since both are already
    columns on every row.
  - `provenance.csv` -- **one file per Run**, modeled as a normalized event log rather than
    a producer/consumer-pair row, following the W3C PROV distinction between generation and
    usage as separate relations/events rather than one combined row:

    ```
    event_type, artifact_id, artifact_version, node_execution_id, node_id,
    timestamp, execution_seq
    ```

    with `event_type` in `{"generated", "used"}`. A Node that produces `ArtifactX` and is
    consumed by two downstream Nodes B and C is three rows, not one wide row with multiple
    consumer columns:

    ```
    generated | ArtifactX | v1 | NodeExecA | ...
    used      | ArtifactX | v1 | NodeExecB | ...
    used      | ArtifactX | v1 | NodeExecC | ...
    ```

    Reconstructing `NodeA --generated--> ArtifactX <--used-- {NodeB, NodeC}` from this is a
    simple group-by on `(artifact_id, artifact_version)`, and it composes correctly for any
    fan-in/fan-out shape without needing a variable number of consumer columns or
    duplicating the generation row per consumer. This is much closer to PROV's own
    `wasGeneratedBy`/`used` relations than the earlier "one row with both producer and
    consumer" design, which is withdrawn.
  - A per-Run `manifest.json` (Section 13.3) indexes both files plus their schema versions.
- **Storage-partitioning correction, round 4: "one CSV per Node" (Section 12.5) is
  downgraded from an architectural decision to an implementation choice, and the default
  changes to a single `recordings.csv` per Run.** The identity columns already on every row
  (`execution_id`, `node_id`, `node_execution_id`, `name`, `execution_seq`) make a single
  file fully filterable without needing physical partitioning to get isolation; the
  contention concern that originally motivated per-Node files is already handled by the
  append-only-queue-plus-single-writer design (Section 6), which serializes writes
  regardless of how many Nodes are producing rows concurrently -- so per-Node files were
  solving a problem the pipeline design had already solved elsewhere. Partitioning by Node
  (or by time chunk, or as a columnar dataset for very large Runs) remains available as an
  **implementation detail behind one logical Recording Store interface**, not a contract
  `ctx.record()` callers or downstream consumers depend on: a Run with 200 Nodes is one
  `recordings.csv` a person can open in Polars/pandas/DuckDB directly, rather than 200 small
  files that need to be concatenated before any cross-Node analysis is possible. The
  boundary this document does commit to is: Reed always exposes a single logical Recordings
  relation and a single logical Provenance relation per Run; how many physical files back
  that relation is an implementation decision, revisited if/when Run sizes make a single
  file impractical (Section 13's `manifest.json` already anticipates this by describing
  files, not assuming exactly one).
- Large `Parcel`/`ArtifactRecord` values are never embedded directly in `provenance.csv`;
  the row stores type, size, a content hash, and a bounded preview (matching Issue #7's own
  requirement), with the actual value retrievable from the `ArtifactRepository` by hash/id
  when needed.
- OTel (`TracerProvider`, `SpanProcessor`, `SpanExporter`) is one *optional* consumer of
  Level 1 and Level 2 data: when enabled, Reed's own Run/NodeExecution/Trigger events are
  translated into OTel spans/links/events by a dedicated adapter, and Reed's own
  `trace_id`/`span_id` become OTel's identifiers for that translation -- but neither level
  depends on OTel being enabled, importable, or configured. This directly resolves the
  "OTel coupling" risk from Issue #7's own risk list: OTel is an exporter target, not a
  foundation Reed's core sits on top of.
- The terminal-rendering experience that was lost with the legacy Bus tracing (Section 1)
  is rebuilt as **a consumer of Level 1** (the live ring buffer) -- a Rich-based renderer
  that subscribes to it during a Run and reconstructs the same kind of trace-id-correlated,
  Node-named, state-labeled terminal output shown in the attached screenshots, but now
  driven by the generic `execution_id`/`node_execution_id`/trace-edge model rather than by
  Bus-specific message topics. It may optionally also read `recordings.csv` and
  `provenance.csv` for post-hoc replay of a past Run, which is strictly more capable than
  the old system (it can show provenance and recordings, not only Bus request/reply pairs),
  and it costs nothing extra to build once Level 1/2 exist, because it needs no OTel backend
  to work.
- **New: a provenance graph renderer, as its own consumer of `provenance.csv` (round 4
  addition).** Because `provenance.csv` is now a normalized `generated`/`used` event log, a
  small consumer can reconstruct the artifact-dependency graph of a Run directly from it (a
  group-by on `artifact_id`/`artifact_version` gives producer and consumers per artifact,
  and a group-by on `node_execution_id` gives everything one Node execution touched) and
  render it as: a Rich-based terminal tree/graph (same family as the Level-1 renderer,
  reusable rendering primitives), or a small self-contained HTML page (a static
  dependency-graph diagram -- e.g. rendered with a graph layout the page embeds, so it
  opens standalone with no server), or the CSV itself opened directly in a spreadsheet or
  DuckDB. This is explicitly a nice-to-have consumer, not a requirement this document
  commits an implementation date to, but it is cheap once `provenance.csv` exists in its
  normalized form and it is exactly the kind of "see what you actually coded" artifact that
  makes the design pay for itself for a user debugging their own Flow.

## 9. Where the original hypothesis needed revision

Section 1 asked whether "Reed defines meaning, OTel provides infrastructure" holds up.
It holds for the *trace* view essentially unmodified. It needed two revisions:

- **Recordings are not OTel's to own even as infrastructure**, because not every Recording
  maps to an OTel signal at all (a structured planner decision has no natural OTel shape).
  OTel is one possible exporter for a subset of recordings (the scalar, metric-shaped
  subset), not the general infrastructure for all of them. The general infrastructure for
  all three views is Reed's own local execution record (Section 8).
- **Provenance should not be bolted on as an OTel afterthought either.** Issue #7's own
  mapping table already treats Parcel/State as "Reed provenance entities" rather than OTel
  concepts, and this document keeps that: provenance uses OTel Span Links only for the
  causal-shape overlap with the trace view (fan-in/fan-out), and otherwise lives in Reed's
  own `ArtifactRecord`/`ArtifactProvenance` model, exported to PROV-shaped formats only if
  and when a consumer needs that (Section 3).

No fundamentally different architecture (event-sourcing-only, a bespoke non-OTel tracer,
adopting LangSmith's or MLflow's storage model wholesale) presented a clear advantage over
"local record + OTel as one exporter among several" during this review, given Reed's actual
requirement (local-first, offline-capable, no mandatory external backend) — so the core
shape of the proposal is retained, with the ownership boundary corrected per the two
revisions above.

## 10. Summary recommendation

1. Add minimal execution identity (`execution_id`, `flow_id`, `node_id`,
   `node_execution_id`) to `Run`/`FlowNode`/`NodeRuntime`; extend `NodeContext` with a
   narrow, read-only identity bundle rather than a back-reference (Section 5) — subject to
   maintainer review of whether even this narrow addition is acceptable under invariant #26.
2. Build one local, append-only, offline execution record per `Run`, covering all three
   views (trace, provenance, recordings) as first-class Reed-owned data (Sections 4, 8).
3. Implement `ctx.record(name, value, *, unit=None, description=None, attributes=None)`
   with the `data`/`context` split, synchronous call / asynchronous persistence, per-sink
   failure isolation, and no OTel/Grafana vocabulary on `ctx` (Section 6).
4. Treat OTel export, Grafana dashboards, CSV/JSONL dumps, and the resurrected Rich
   terminal renderer as independent, optional consumers of the local record — none of them
   a dependency of Reed's core execution path (Sections 8, 9).
5. Defer: sampling/cardinality policy configuration surface, schema-evolution tooling
   beyond `schema_version`, and the metrics-exporter allow-list mechanism, to the
   implementation phase — this document fixes the architecture and the invariants those
   mechanisms must respect, not their concrete APIs.

This document is a design decision, not an implementation. No code changes are proposed or
made as part of it.

## 11. Revision (informed by Davi's feedback): forced name+value, two observability levels, tabular persistence

This section supersedes parts of Sections 4, 6, 7, and 8 per explicit correction from Davi.
It does not delete those sections — they stay as the record of what was considered and why
it changed — but this section is now the governing decision on the points below.

### 11.1 Two observability levels, not one

The original draft blurred together two genuinely different things under "the three
views." They must be split by their persistence contract, not just by their content:

- **Level 1 — Propagation / execution tracing (network level).** This is what the
  pre-Issue-4 Bus/Depot/Outpost system did: which Node fired, in response to what,
  correlated by trace id, rendered live in the terminal (Section 1, Section 4's "Execution
  Trace" view). This is inherently observational: valuable while a Run executes or
  immediately after for debugging, but Reed does not need to durably persist it as a matter
  of architecture. It is a live/replayable view over the Run's own execution, not an
  artifact someone loads into a spreadsheet later. Persistence here is optional/best-effort
  (an in-memory ring buffer, optionally mirrored to a debug log), never a required feature.
- **Level 2 — User Recordings (`ctx.record(...)`).** Application data the user explicitly
  chose to record and unambiguously wants to keep: a metric, a decision, a state snapshot.
  This must be durably persisted. Data Provenance (`ArtifactRecord`/`ArtifactProvenance`)
  belongs here too, since it already must persist for Reed's own artifact-dependency
  mechanics to work.

Section 8's original framing ("one append-only local store... covering all three views")
overreached: Level 1 does not need the same durability contract as Level 2. This is the
correction.

### 11.2 (Revised, round 4) `Recording` adopts an OTel-compatible measurement
vocabulary via an `Instrument` abstraction — not the OTel Metric data model itself

**Correction to the original framing.** The earlier claim that `Recording` "adopts the
OpenTelemetry Metric data model directly" was not technically accurate and is withdrawn. In
OTel, a metric is produced by an **Instrument** (`name`, `kind` -- Counter, UpDownCounter,
Gauge, Histogram, ... --, `unit`, `description`), and an *observation* is a `(instrument,
number)` pair with attributes; the backend deals in streams/timeseries, not a generic
`name + value + unit + attributes` table. Reed does not need or want that machinery, but it
is worth being honest that the earlier wording implied an equivalence that does not hold.
The corrected framing:

> `Recording` intentionally adopts an OTel-compatible measurement vocabulary, not the
> OpenTelemetry Metric data model itself.

**What this changes concretely: recordings are declared against a named `Instrument`.**
The first `ctx.record(...)` call for a given local `name` (within one Node) implicitly
declares an `Instrument`:

- `name` (required, `str`) -- the binding/join key, local to the Node (Section 11.6/12.1).
- `kind` (required on first declaration, optional/ignored thereafter -- one of a small,
  Reed-defined set: `"gauge"`, `"counter"`, `"updown_counter"`, `"event"`). `kind` is what
  makes the OTel-metric export mapping explicit and opt-in, directly satisfying Section 7's
  Q7 ("never inferred from the Python type of `value`"): only `"gauge"`, `"counter"`, and
  `"updown_counter"` are eligible for projection into an OTel Metric at all; `"event"` is
  the default for arbitrary application facts (a decision, a label, a state snapshot) that
  are not metrics in OTel's sense and are never promoted to one. `kind="event"` is the
  right default when the caller does not specify one, so `ctx.record(name="reason",
  value="conflict avoidance")` keeps working without forcing every call site to think about
  metric semantics.
- `unit` (optional, `str`), `description` (optional, `str`) -- instrument-level metadata,
  meaningful mainly for `"gauge"`/`"counter"`/`"updown_counter"`.
- `value` (required on every call, **scalar only**: `str | int | float | bool`) -- the
  per-observation number/value. Section 6's earlier recommendation that `value` be
  polymorphic (mapping/dataclass) remains withdrawn, per Section 11.2's original (still
  correct) reasoning: scalar-only keeps the persisted record trivially tabular.
- `attributes` (optional, small flat mapping of scalars -- the one field allowed to be
  "structured," mirroring OTel Metric attributes/labels).
- context columns, appended by the runtime, not the caller: `timestamp`, `execution_id`,
  `flow_id`, `node_id`, `node_execution_id`, `execution_seq` (Section 13.1).

Reed caches the declared `kind`/`unit`/`description` against the qualified instrument
identity (`node_id`/`node_name` + `name`) the first time it is seen; subsequent calls need
only supply `name` and `value` (`attributes` optional), exactly like an OTel SDK caches an
Instrument handle after its first creation and only takes the observed number on each
subsequent call. Together, one `ctx.record(...)` call is exactly one row of a table.

### 11.3 No nested structure at the call site — one `ctx.record()` call per fact

```python
ctx.record(name="planner.chosen_action", value="climb")
ctx.record(name="planner.reason", value="conflict avoidance")
```
rather than a single call with a nested `value={"chosen_action": ..., "reason": ...}`. This
is the required calling convention, not merely an option: `name` is the bind/join key that
lets a downstream consumer reconstruct which individual scalar facts belong together (same
`node_execution_id`, correlated timestamps), rather than Reed needing to understand or
preserve arbitrary nesting. This resolves the earlier "too rigid vs. too loose" tension by
resolving it in favor of "flat, and that's fine" — flattening is pushed to the call site
(the application decides how to name each scalar), not into a schema Reed must interpret.

This revises three of Section 7's answers:
- **Q2** (name+value required, or arbitrary data?): forced `name` + scalar `value`. The
  earlier "value polymorphic" answer is withdrawn.
- **Q3** (how much schema should Reed impose?): the full OTel-Metric-shaped row above, not
  a looser envelope.
- **Q6** (scalar vs. structured values): there is no structured `value` at Reed's
  persistence layer. Structure is achieved by composing multiple named scalar recordings,
  correlated by `node_execution_id`/timestamp — never by nesting.

### 11.4 Persistence format: flat, tabular, CSV-compatible

The local execution record for Recordings (Level 2) is a flat table, one row per
`ctx.record()` call. The natural flush point is when a Node execution completes — the Node
runtime can dump the buffered rows for that firing at that point, rather than holding them
for the whole Run. This directly satisfies the requirement that the artifact be easy to
process downstream: CSV (or a CSV-compatible columnar format such as Parquet, if volume
later warrants it) is the natural fit precisely because the schema is already flat
(Section 11.2) — nothing needs to be un-nested at export time. `attributes`, if present, is
serialized as a single JSON-string cell, keeping the rest of the row scalar (the same
approach OTel/Prometheus exporters themselves use for labels in tabular exports).
Conversion to an OTel Metric export or Grafana ingestion is a projection over these rows,
not the row format itself — consistent with Section 8's original "exporters are
projections, not the source of truth" principle, which is unaffected by this revision.

### 11.5 Summary of what changed

- Section 6: `value` is scalar-only, not polymorphic. The nested-`data`-dict call shape is
  replaced by repeated flat `ctx.record(name=..., value=...)` calls.
- Section 7, Q2/Q3/Q6: superseded by 11.2/11.3 above.
- Section 8: split into Level 1 (propagation/trace — ephemeral, best-effort) and Level 2
  (Recordings + Provenance — durable, tabular, CSV-first). Only Level 2 is the persisted
  local execution record this document commits to building.

### 11.6 `name` is local to the call site; Reed derives a qualified id automatically

Refinement on top of 11.2/11.3: the caller only ever writes the local, short `name`
(`"chosen_action"`, `"reason"`) — not a manually-prefixed one. Reed derives a qualified
identifier automatically, without the caller having to think about collisions:

```python
ctx.record(name="chosen_action", value="climb")
ctx.record(name="reason", value="conflict avoidance")
```

Reed computes `qualified_id = f"{node_id_or_name}.{name}"` (e.g. `planner.chosen_action`,
`planner.reason`) at the point of persistence, the same way `node_execution_id` and the
other context columns are appended (Section 11.2) — the caller never constructs this string
itself. This is what lets two different Nodes both use the local name `"reason"` without
their recordings colliding or being conflated downstream: the row's true primary key is
`(node_id, name)` (equivalently, `qualified_id`), not `name` alone.

This does not change the row shape from Section 11.2 — `qualified_id` is a derived/computed
column (or the persisted `name` field is simply pre-qualified at write time), not a new
caller-facing field. It also does not change the calling convention from Section 11.3 (one
flat `ctx.record()` per fact); it only clarifies that the "binding" `name` is scoped to the
Node, not global, and that Reed — not the application — is responsible for qualifying it.

## 12. Further refinement (informed by Davi's feedback, round 2): record identity, node-name uniqueness, per-node files, compound values

### 12.1 `qualified_id` is a series/grouping key, not a row's primary key

Correction to 11.6: `(node_id, name)` — equivalently `qualified_id` — identifies a *series*
(the same conceptual measurement across firings), the same way an OTel metric name
identifies a series across samples. It is **not** unique per row: a Node that fires
repeatedly produces many rows sharing the same `qualified_id`. The actual unique identity
of one row is:

```
record_id = (node_execution_id, name, seq)
```

`seq` is a monotonically increasing counter scoped to one `node_execution_id`, assigned by
the Reed runtime (never by the caller) at the moment a `ctx.record(...)` call is buffered.
It exists because a timestamp alone cannot guarantee either uniqueness or ordering between
two `ctx.record()` calls made in the same firing (both can land in the same millisecond).
`node_id` is redundant with `node_execution_id` (every execution belongs to exactly one
Node) but is kept as a denormalized column so a row can be filtered/grouped without a join.

### 12.2 `description` — free-form, optional, outside the correlation key

Added as an optional per-call field: a short human-readable string the caller may attach to
explain context ("chosen after 3 candidates were filtered by fuel margin"). It is not part
of `record_id` or `qualified_id`, is never interpreted by the Reed runtime or by any
exporter, and exists purely for a human or an LLM reading the record later.

### 12.3 Node-name uniqueness is not yet enforced by Reed — this is a real gap, not an
assumption (**superseded by Section 16.5 — this validation is retracted, not needed**)

Direct inspection of `src/reed/composition/node/domain_node_description.py` and
`src/reed/composition/flow/flow_composition.py` confirms: a Node has no explicit `name`
parameter today. Its identity for display purposes is `DomainNodeDefinition`'s
`self.function.__name__` property. The uniqueness validation `Flow.add(...)` already
performs (`ArtifactDependencyGraph`'s "unique-producer" check) is scoped to **output
artifact type**, not to function name — two Node functions named identically (e.g. two
closures both called `update`, registered from different call sites) would silently
collide once `qualified_id = f"{node_name}.{name}"` is introduced.

**This document adds a new, small requirement on `Flow.add(...)` as a prerequisite for
Section 11's design to be safe**: composition-time validation that rejects a second Node
whose `function.__name__` collides with an already-registered Node in the same `Flow`,
raising immediately (matching the "fail fast, not silently" posture already adopted for
schema in Section 11.4). This is a small, targeted addition to `flow_composition.py`, not a
reopening of Issue #4's scope, but it must land before `ctx.record(...)` ships, or
`qualified_id` cannot be trusted as a series key.

### 12.4 Compound/vector values: manual flattening only, no automatic expansion

Prior art check: Stable-Baselines3's `logger.record()` does **not** flatten compound values
into multiple scalar calls — it resolves this with typed wrapper classes (`Video`, `Image`,
`Figure`, `HParam`) that the logger recognizes by type and dispatches per-backend. This is
polymorphism-by-recognized-type, which is the opposite of the flat/scalar-only, schema-
locked-now posture Davi has explicitly chosen for Reed, given its target use (scientific
experiments and safety-critical systems where consistency must not degrade under future
extension).

Decision: Reed does **not** adopt SB3's typed-wrapper approach, and does **not** auto-expand
array/sequence values into multiple rows. A compound value (e.g. a 3D velocity) is recorded
as multiple explicit, manually-named calls:

```python
ctx.record(name="velocity.x", value=vx)
ctx.record(name="velocity.y", value=vy)
ctx.record(name="velocity.z", value=vz)
```

`name` dot-segments (`velocity.x`) are a documented, recommended convention for expressing
"this scalar is part of a compound fact," resolved entirely at the call site by the
application — Reed performs no automatic splitting, joining, or type-based dispatch. This
keeps the row shape and the failure modes exactly as narrow as Section 11.2 already
committed to.

### 12.5 One record file per Node, not one per Run

Confirmed: the local Recordings store is partitioned per Node
(`.reed/runs/<execution_id>/recordings/<node_name>.csv`), not one shared file for the whole
Run. This follows directly from 12.3 (Node names are unique within a Flow).

**Correction to the original justification:** partitioning by Node is *not* what keeps the
column schema stable — the row format is already fixed regardless of partitioning, because
the table is **long/tidy** (Section 11.2): `name` is a *data value* in a row, not a column
header, so the file's columns (`record_id`, `name`, `value`, `unit`, `attributes`,
`description`, the identity columns) never change no matter which `name`s a Node happens to
emit. The real reasons for one file per Node are: (1) namespace/ownership isolation — a
Node's own recordings are physically separate from every other Node's, so nothing about one
Node's instrumentation can corrupt or interleave with another's file; (2) independent flush
cadence — each Node's `NodeExecution`s can flush on their own schedule without contending on
a shared file (Section 13.5 revisits when this isolation still doesn't eliminate all
contention); and (3) simpler per-file `schema_version` bookkeeping if the row shape itself
ever needs to change — a version bump for one Node's file does not force renegotiating every
other Node's file in the same Run.

### 12.6 A note on relying on pylint/static tooling for name uniqueness

Worth being precise here rather than overstating the help static analysis gives: a linter's
"function redefined" check (pylint, or ruff/flake8's `F811`) only fires when two functions
with the same name are defined in the **same lexical scope** — the same module, or the same
class body. It does **not** fire across different modules (a Node function called `update`
in `planner.py` and another called `update` in `controller.py` are two completely legitimate,
non-conflicting definitions from the linter's point of view) and it does not fire for
closures/factories that generate a function object at runtime with a chosen `__name__`. The
exact case Section 12.3 worries about — two Nodes registered into the same `Flow` from
different modules, both wrapping a function literally named `update` — is precisely the case
static tooling has no visibility into, because nothing about it is wrong at the level of a
single file. So static analysis meaningfully narrows the *accidental, same-file* case, but
the `Flow.add(...)` runtime check from 12.3 remains the actual guarantee for the case that
matters most in a larger, multi-module Flow — it is not a redundant backstop, it is the
only check that covers cross-module collisions at all.

## 13. Fixes from the third-round diagnostic: causal ordering, crash safety, durability-to-flush, manifest, concurrency assumption

### 13.1 `execution_seq`: a global, monotonic sequence for deterministic ordering
-- explicitly NOT a claim of causality (renamed from `causal_seq`, round 4 correction)

`seq` (Section 12.1) is scoped to one `node_execution_id` and resolves ordering *within* one
firing. It does not resolve ordering *across* different Nodes' firings within the same Run —
which is exactly what the Execution Trace view (Level 1, Section 11.1) needs in order to
reconstruct "what happened before what" across the whole Run. `node_execution_id` is a UUID
and carries no order; `timestamp` alone is not trustworthy for this at high firing rates
(the same problem already identified intra-firing in Section 12.1 applies between Nodes
too).

**Fix**: Reed maintains one monotonically increasing counter per `execution_id` (a simple
Lamport-style logical clock, not a wall-clock value), incremented once whenever a
`node_execution_id` is minted (Section 5) -- call it `execution_seq`.

**Correction, round 4: the original name (`causal_seq`) overclaimed what this column
means, and the name is changed for that reason, not merely for style.** If two Nodes B and
C both depend on a common upstream A and fire concurrently, a global counter will still
assign B and C some total order (`B=2, C=3` or `C=2, B=3`) -- but that order is an artifact
of *when the runtime happened to observe them*, not a claim that one caused or preceded the
other. `execution_seq` gives a deterministic, replayable **observation order** -- useful for
sorting a table, for reproducible test assertions, for a stable iteration order when
rendering a Run -- and nothing more. **Causality is a separate concept, already covered by
this document's own provenance edges and by OTel Span Links (Section 4, view 1 and view 2)
-- never by `execution_seq`.** A consumer that wants to know whether B genuinely happened
before C in a way that matters (as opposed to merely being assigned a smaller number) must
look at the provenance graph or the trace's span links, not at `execution_seq` ordering.
`provenance.csv` and `recordings.csv` rows both carry the `execution_seq` of the
`node_execution_id` they belong to (denormalized, same rationale as `node_id` in Section
12.1), so a plain sort gives a deterministic replay order -- described strictly as
"deterministic order," never as "causal order," anywhere in this document from here on.

### 13.2 The durability boundary, stated explicitly (round 4 correction: "never
lossy" was too strong, and exception/cancellation records are removed from `ctx.record()`)

**Correction: "durable / never best-effort" (Section 6/7 Q8, Q12) cannot be an absolute
guarantee if `ctx.record()` returns immediately (Section 6) and the process can crash
between that return and the next durable flush.** Those two properties -- synchronous,
non-blocking `record()`, and zero data loss under every failure -- are not simultaneously
achievable without an `fsync` on every single call, which would destroy exactly the hot-path
latency the synchronous-call design exists to protect (Section 6, Lineage B). The earlier
wording overclaimed. The corrected contract replaces "never lossy" with an explicit
durability boundary:

> Recordings accepted during a `NodeExecution` are guaranteed to be durably flushed when
> that `NodeExecution` exits -- normally, exceptionally, or through cancellation. A hard
> process crash before that durability boundary may lose the current in-flight batch.

This is what "the flush point is not 'on successful completion' but 'on every path out of a
Node execution'" (unchanged from the original fix) actually buys: it closes the gap between
*Node-body-level* failures (an exception inside the Node, a cancellation) and durability --
those are covered, because `NodeRuntime` flushes the buffered rows for a `node_execution_id`
in a `finally`-equivalent block wrapping the Node body regardless of how it exits. It does
**not** and cannot cover a *process*-level failure (the whole interpreter crashing, the
machine losing power) between `ctx.record()`'s return and that flush -- that narrow window
is the honestly-stated boundary of what this design guarantees, not a gap that was missed.

**Correction: exception/cancellation are no longer recorded through `ctx.record()`.** The
original fix proposed a reserved `name` (`__exception__`/`__cancelled__`) so a Node's
failure would show up as a row in the same store. This is withdrawn: it mixes **application
recordings** (only what the caller explicitly chose to record) with **runtime lifecycle
events** (`NodeExecutionFailed`, `NodeExecutionCancelled`), which the runtime already knows
about independently of anything the application called `ctx.record()` for. Keeping this
boundary clean matters: it lets a user look at `recordings.csv` and know, without exception,
that every row in it is something their own code explicitly chose to write --

> `ctx.record()` contains only information explicitly recorded by application code.

Exception and cancellation outcomes stay where they already belong: the Execution Trace /
NodeRuntime lifecycle (Level 1, Section 11.1), which may itself be persisted later as its
own runtime-metadata record (a `node_executions.csv` or similar, out of this document's
current scope) if a durable record of *outcomes* -- as opposed to a durable record of
*recordings* -- turns out to be needed. That is a separate design question from `ctx.record()`
and is not conflated with it here.

### 13.3 Crash-safe, append-only writes, plus a per-Run manifest

Two related gaps:

- **Partial-write safety.** A process crash mid-write can leave a truncated last line in a
  CSV file. Given Reed's target use (safety-critical, scientific), this must be treated as
  an expected failure mode, not an edge case: writes are append-only, one row flushed and
  `fsync`'d (or the platform equivalent) per batch, and any reader of `recordings/*.csv` or
  `provenance.csv` must tolerate and discard a truncated final line rather than failing the
  whole parse. This is a requirement on both the writer (never rewrite/truncate an existing
  file; only append) and on any reference reader Reed ships (be lenient at end-of-file).
- **Discoverability.** With data spread across one file per Node plus `provenance.csv`,
  nothing today lets a consumer discover, without directory-scanning, which files exist for
  a Run, what each file's `schema_version` is, or which `node_id`/`node_name` a given
  `recordings/*.csv` file belongs to. **Fix**: a `manifest.json` written once per Run (at
  `Run` start, updated — not rewritten wholesale, appended-to or upserted — as Nodes are
  registered) listing: `execution_id`, `flow_id`, start timestamp, and per-file entries
  `{path, node_id, node_name, schema_version}` for every `recordings/*.csv` plus one entry
  for `provenance.csv`. This satisfies Issue #7's own "machine-readable" goal for a
  CLI/LLM/MCP consumer more directly than directory-scanning would.

### 13.4 Provenance storage: resolved in Section 8 (cross-reference)

The Section 8 rewrite above already resolves the previously-open question of where
Provenance is persisted: it gets its own `provenance.csv` (one per Run), populated from
`ArtifactRecord`/`ArtifactRepository` as its source of truth, rather than being folded into
the per-Node Recordings files or left solely inside the repository with no tabular
projection. This is restated here only to close the loop explicitly against the diagnostic
that flagged it as unresolved.

### 13.5 Open assumption to revisit: no two concurrent firings of the same Node

Partitioning Recordings by Node (Section 12.5) reduces write contention *between* Nodes to
zero (each Node owns its own file), but it does not eliminate contention *within* one Node's
file if that Node could ever have two `NodeExecution`s in flight at the same time writing to
`recordings/<node_name>.csv` concurrently. Today's execution model (sequential-but-async
Node execution, one firing of a given Node at a time) makes this a non-issue in practice.
This is flagged explicitly as an assumption this design leans on, not a guarantee independently
re-derived here: if Reed's roadmap ever introduces concurrent firings of the *same* Node
(as opposed to concurrent firings of *different* Nodes, which the per-Node partitioning
already handles safely), the single-writer-queue requirement from Section 6 needs to be
revisited specifically for the intra-Node case, most likely by giving each in-flight
`node_execution_id` of that Node its own append buffer that a single background writer
drains in `causal_seq` order.

## 14. Node-name uniqueness: scope corrected to per-Flow, not global; no new `name=` parameter

### 14.1 The scope was already per-Flow, but this was not said explicitly

Section 12.3's fix was phrased as "`Flow.add(...)` rejects a second Node whose
`function.__name__` collides with an already-registered Node **in the same `Flow`**" — this
was already scoped to one `Flow` instance (since `Flow.add` is a method on one `Flow`), not
global across the process. This document did not previously say so explicitly, which is
worth correcting for clarity: **the same function, wrapped as a Node, may be reused across
different `Flow`s without restriction.** Two independent `Flow`s each having a Node built
from `update_aircraft` is fine and expected — the collision Section 12.3 guards against is
two Nodes *within the same Flow* sharing a name, not the same function appearing in two
unrelated Flows.

### 14.2 No new `name=` parameter on `flow.add(...)`

A natural-seeming fix would be to let `flow.add(function, name="aircraft_update")` give a
Node an explicit identity independent of `function.__name__`, solving reuse and closures in
one move. This document does not adopt that: the existing scope-corrected rule (unique
`function.__name__` within one `Flow`) already covers the actual failure mode (accidental
collision inside one Flow) without adding a new keyword argument and a new invariant
("declared name overrides derived name, and interacts with `on_output`/`trigger_policy`
some other way") to Reed's already-established `flow.add(...)` signature. Introducing a
parallel identity system when the derived one, correctly scoped, already works is exactly
the kind of expansion of API surface this document has been trying to avoid elsewhere
(Section 6's rejection of `ctx.metrics`/`ctx.otel`/`ctx.grafana` is the same instinct
applied here).

### 14.3 Uniqueness of Node name is a related but *separate* rule from artifact-type
uniqueness — not a strict logical consequence of it

Worth being precise rather than asserting a stronger connection than actually holds: Reed
already enforces that no two Nodes in a `Flow` produce the same output artifact **type**
(`ArtifactDependencyGraph`'s unique-producer check, Section 12.3). It is tempting to treat
Node-name uniqueness as an automatic consequence of that — "if the artifact type is unique,
the Node producing it is effectively unique" — but this does not strictly follow: two Nodes
in the same `Flow` could produce two *different* artifact types while both being built from
functions that happen to share a name (`__name__`), e.g. two generic closures both literally
named `handler`, each producing a distinct output type. Artifact-type uniqueness and
function-name uniqueness are two different partitions of the same `Flow`'s Nodes, and one
does not imply the other. Both checks are needed; this document keeps them as two separate
validations in `Flow.add(...)` rather than presenting one as derived from the other.

### 14.4 Cross-Flow binding/composition: a forward-looking note, not a current requirement

Direct inspection (this session) confirms Reed today has no mechanism for composing or
"binding" two separate `Flow` instances together — `Flow` is presently a self-contained
unit, and the unique-producer/unique-name checks are already naturally scoped to it. If a
future version of Reed introduces a way to combine Flows (the legacy `bind(...)` API removed
in Issue #4 was a different, decorator-era mechanism and is not being revived here), that
future feature would need its own re-validation pass over the combined Node/name space at
bind time — the same collision check Section 12.3 already performs for `Flow.add(...)`,
just re-run across the union of both Flows' Nodes. This document records that requirement
for whenever cross-Flow composition is designed, without treating it as in scope now.

## 15. Summary of round-4 corrections

1. **`Recording` is OTel-compatible, not "the OTel Metric data model."** Reframed around an
   `Instrument` abstraction (`name`, `kind`, `unit`, `description`, declared once) plus a
   per-call scalar `value` — `kind` also resolves Section 7's Q7 (explicit, opt-in
   OTel-metric export mapping) more cleanly than the earlier free-standing recommendation
   (Section 11.2).
2. **`causal_seq` → `execution_seq`, and it is now explicitly documented as a deterministic
   *observation order*, not a claim of causality.** Causality remains the job of provenance
   edges and OTel Span Links (Section 13.1).
3. **`provenance.csv` normalized to a `generated`/`used` event log**, matching W3C PROV's
   own separation of generation and usage as distinct relations, plus a new provenance-graph
   rendering consumer (terminal or HTML) built directly from it (Section 8).
4. **"One CSV per Node" downgraded from architecture to implementation choice**; the default
   is now a single `recordings.csv` per Run, since the identity columns already make it
   filterable and the single-writer queue already solves the contention this was meant to
   avoid (Section 8).
5. **The durability guarantee is now an explicit boundary, not an absolute claim**:
   durable as of `NodeExecution` exit (success, exception, or cancellation), not as of the
   `ctx.record()` call itself — a hard process crash before that boundary can still lose the
   in-flight batch, and this document says so plainly instead of overclaiming (Section 13.2).
6. **Exception/cancellation are removed from `ctx.record()`** (no more reserved
   `__exception__`/`__cancelled__` names) and stay in the Execution Trace / NodeRuntime
   lifecycle, keeping `recordings.csv` strictly limited to what application code explicitly
   chose to record (Section 13.2). Node-name uniqueness is confirmed to be correctly scoped
   to a single `Flow` already, with no new `name=` API parameter added (Section 14).

Everything from round 3 not listed above stands unchanged, including: Reed IDs independent
of OTel IDs (Section 5), `NodeContext` without a back-reference (Section 5), `ctx.record()`
staying backend-agnostic (Section 6), local-first/offline as the foundation (Sections 1, 8),
exporters kept off the hot path (Sections 3, 6), trace/provenance/recordings as three
distinct concepts (Section 4), and PROV as a conceptual model rather than an RDF/OWL
dependency (Section 3).

## 16. Round 5 consolidation: `Instrument` as first-class entity, per-Execution physical
storage as the persistence boundary, `node_id`/`node_name` identity split

This section is the converged, governing decision on the `Instrument`/`Recording` API, the
physical storage layout, and Node identity. It supersedes: Section 11.2 ("adopts the OTel
Metric data model" framing, already corrected once in round 4, refined further here),
Section 12.5 (per-Node file partitioning), Section 12.3 (the `function.__name__`-uniqueness
validation — retracted), and Section 14 (the node-naming debate — resolved differently and
more cleanly than either round 3 or round 4's answer). Sections 11.2/12.3/12.5/14 are kept
in place as the record of how this was arrived at, not deleted.

### 16.1 Three separated levels: namespace, definition, physical persistence

The earlier rounds conflated "where does this live" across three genuinely different
questions. They are now kept apart deliberately:

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

**`Instrument` is the logical unit of observation; `Execution` is the physical unit of
persistence; `Flow` is the logical unit of aggregation and analysis.** This sentence is the
central decision of this round and should be read as the one-line summary of everything
below.

### 16.2 `Instrument` is declared, not repeated per call

```python
speed = Instrument(
    name="speed",
    kind="gauge",
    unit="m/s",
    description="Aircraft speed",
)

flow.add(
    update_aircraft,
    instruments=[speed],
)
```

and, during execution:

```python
def update_aircraft(ctx, aircraft):
    ...
    ctx.record(speed, aircraft.speed)
```

**Explicit pre-declaration via `flow.add(..., instruments=[...])` is the primary,
recommended path — not merely one of two equally-weighted options.** This is a firmer
position than round 4's "support both equally": pre-declaration gives Reed a Flow's full
observability surface *before any execution runs* (every Instrument a Node will ever emit,
with its `kind`/`unit`/`description`), which is exactly what makes `reed describe <flow>`
possible and is genuinely valuable for simulation/experiment tooling. Lazy declaration
(`ctx.record("speed", 18.4)`, no prior `Instrument` object) remains available purely as a
prototyping convenience, with one hard rule: if a Node declared an explicit `instruments=`
list, calling `ctx.record(...)` with a name not in that list is a composition-time-adjacent
error (raised at first call, not silently accepted as a new ad hoc instrument) — mixing
"fully declared" and "whatever shows up" within one Node is not allowed. A Node with no
`instruments=` list at all stays in pure lazy mode, unchanged from round 4.

`Instrument.kind` is kept to **`"gauge"`, `"counter"`, `"updown_counter"`** for now.
`"event"` (round 4's default for non-metric facts) is **explicitly withdrawn from `kind`
pending further research**, not decided here: an event is conceptually not a repeated
*measurement* of an Instrument at all, and forcing it into the same enum risks recreating
the recording/execution-event conflation this document has been trying to avoid since
Section 6. Until this is resolved, a non-metric fact (a decision, a label) should still go
through `ctx.record(...)`, just without implying it is an "Instrument measurement" in the
OTel sense — the concrete mechanism for this (a separate lightweight `Fact`/tagged-value
concept, vs. simply not requiring `kind` for non-metric recordings) is left as an open
question for the next round, not resolved here. **`Histogram` is deliberately excluded from
V1**, and the earlier reasoning for excluding it (bucket/quantile configuration is extra
complexity Reed doesn't need to own) is corrected on one technical point: OTel does not
strictly require an Instrument's `kind` to carry bucket configuration itself (aggregation
can be defined separately, e.g. via a View in the OTel SDK) — but the conclusion is
unchanged regardless: Reed persists every raw observation, so a histogram can always be
computed downstream from raw `gauge`/`counter` recordings, and there is no concrete use case
yet that requires Reed itself to understand histogram semantics at the instrumentation
point. Add it only when a real need appears.

### 16.3 Identity: `instrument_id = (flow_id, node_id, name)` — never `node_name`

```
Instrument
├── instrument_id   (derived: flow_id + node_id + name)
├── flow_id
├── node_id
├── name
├── kind
├── unit
└── description
```

and correspondingly, `Recording` shrinks to only what varies per observation:

```
Recording
├── instrument_id
├── value
├── timestamp
├── execution_id
├── node_execution_id
├── execution_seq
└── attributes
```

`flow_id`/`node_id` are resolvable via `instrument_id` alone, but are denormalized onto
every `Recording` row anyway (the same "a little redundancy avoids joins for simple
questions" reasoning already used for `node_id` in Section 12.1) — a consumer using
DuckDB/pandas/an LLM should never need a join just to filter "give me everything Node X
recorded."

### 16.4 Physical layout: static definitions per Flow, durable data per Execution

```
.reed/
├── flows/
│   └── <flow_id>/
│       └── instruments.json          -- static, derived from Flow composition
│
└── runs/
    └── <execution_id>/
        ├── manifest.json
        ├── recordings.csv            -- one file per Execution (not per Instrument, not
        │                                 per Node): long/tidy, instrument_id is a data
        │                                 column, not a filename or a header
        └── provenance.csv            -- normalized generated/used event log (Section 8)
```

`recordings.csv` stays **one file per Execution**, confirming and slightly narrowing round
4's "one CSV per Run, not per Node" decision: the option of one file *per Instrument* was
considered and rejected for the same class of reason that killed "one file per Node" — a
Flow with 100 Nodes × 10 Instruments each is 1,000 small files per Run, which is worse for
the filesystem, for glob-based tooling, and for compaction than one flat, filterable table.
`Instrument` is a **logical** unit of a series (Section 16.1's central sentence), not a
**physical** partitioning requirement — the same distinction Section 12.5 already drew for
Nodes, now generalized. If Run volume ever justifies partitioning (by Instrument, by time
chunk, or by switching `recordings.csv` to a Parquet file — trivially filterable/pushdown-
capable by `instrument_id` without any change to `ctx.record()` or to what a `Recording`
means), that is an implementation swap behind one `RecordingStore` interface
(`CSVStore` today, `ParquetStore` later), never a change to the public API.

`instruments.json` lives under the **Flow**, not the Run, because it is static — derived
once from a Flow's composition (`flow.add(..., instruments=[...])` calls), true regardless
of how many times or in how many processes that Flow is executed. It should be treated as an
export/introspection artifact (what `reed describe <flow>` produces), not something every
running process must write to disk on every start; see Section 17's diagnostic for the
concurrency and stability questions this raises.

### 16.5 `node_id` is identity; `node_name` is a display label — Section 12.3's validation
is retracted

The more fundamental invariant Reed already has is: **within a Flow, each Artifact type has
exactly one producer** (Section 2, `ArtifactDependencyGraph`'s unique-producer check). Node
naming should not be given its own independent uniqueness rule on top of that, because doing
so lets an observability concern (wanting a nice qualified name in a CSV) constrain
composition semantics that have nothing to do with observability:

```
Flow A                  Flow B
node_id = a91           node_id = f17
name    = "update"      name    = "update"
```

Two Nodes named identically in two different Flows are not a problem. Even after a future
Flow composition/bind (Section 16's note on this: still not a mechanism Reed has today, per
the confirmed absence checked in round 3), `a91` and `f17` coexisting under one combined
Flow is fine — composition should fail only if it violates the real invariant (two producers
for the same Artifact type), never merely because two Nodes share a display name. Where a
UI or CSV needs to disambiguate, it shows `update [a91]` / `update [f17]` — a presentation
concern, not a composition-time error.

This retracts Section 12.3's proposed `Flow.add(...)` validation (reject a second Node whose
`function.__name__` collides within the same Flow) entirely — it is not needed. `node_id`
was always meant to be Reed-assigned (Section 5: "a stable id assigned at composition
time"); this round confirms explicitly that it, not `function.__name__`, is the only
identity `instrument_id`, `Recording`, and any other identity-bearing structure should ever
reference. `node_name` (still derived from `function.__name__` by default) is retained
purely as a human-readable label, allowed to collide freely.

## 17. Risk diagnostic (round 5)

This design converges on something genuinely cleaner than round 4, but it introduces a
requirement that was never made explicit before and is now load-bearing: cross-Execution
aggregation (Section 16.1's whole reason for existing) only works if certain identifiers are
stable **across separate process runs of "the same" Flow**, not merely unique within one
Run. This is the most severe open item below.

### 17.1 (Most severe) `flow_id` and `node_id` must be stable across separate Executions,
and nothing in this document yet says how

Section 5 defined `node_id` as "a stable id assigned at composition time" and `flow_id` as
identifying "the `Flow` definition being run" — but "stable" there only ever meant "does not
change during one Run." Section 16's entire cross-Execution story (`reed query <flow_id>`
globbing `runs/*/recordings.csv`, `instrument_id = (flow_id, node_id, name)` being the join
key across many Executions, `instruments.json` living once per `flow_id` rather than per
Run) requires something stronger: **the same logical Flow, executed as separate OS processes
on separate occasions, must produce the same `flow_id` and the same `node_id` for the same
Node each time.** If either is a freshly-minted UUID per process (which is what "assigned at
composition time" reads as most naturally, and is exactly how `execution_id` is deliberately
defined in Section 5), then every run of "the same" experiment gets a new `flow_id`
directory under `.reed/flows/`, `reed query` has nothing stable to glob against, and
`instrument_id` never matches across two Executions of the same code — silently defeating
the entire point of Section 16.

This needs a concrete resolution before implementation, not just a naming fix: `flow_id`
and `node_id` must be **derived deterministically** from something that is stable across
process restarts — e.g., a hash of the Flow's composition shape (the ordered set of
registered Node functions' qualified names/signatures) for `flow_id`, and a hash of
(qualified function name, registration order or explicit position) for `node_id` — or, more
simply, an explicit identifier the user assigns once (`Flow(id="aircraft_sim_v1")`,
`flow.add(update_aircraft, id="update_aircraft")`) with a derived fallback when omitted.
Either approach is workable; what matters is that this document currently has no answer,
and Section 16's design silently assumes one exists.

### 17.2 Flow-shape drift across the Executions being aggregated

Even once `flow_id` is stable, `reed query <flow_id>` aggregating many Executions
implicitly assumes those Executions ran a structurally comparable Flow. If a Node is added,
removed, or its Instrument's `unit` changes between two Executions that share a `flow_id`
(because the user only bumped a parameter, not the identifier), a cross-run query can
silently mix incompatible series. This document does not resolve when a change to a Flow's
code should force a new `flow_id` versus keep the old one — that is a judgment call this
design pushes onto the user (analogous to deciding when an experiment's "version" changes),
and it should be stated as such rather than left implicit.

### 17.3 `instruments.json` is described as "static" but is written by an ordinary,
possibly-concurrent process

Section 16.4 treats `instruments.json` as a derived, low-concern artifact, but if every
process that constructs a given Flow also writes (or refreshes) `flows/<flow_id>/
instruments.json` on start, two processes doing this concurrently — or one process starting
while an old one's file write is mid-flight — reintroduces a small version of the exact
concurrent-writer problem Section 16.4 otherwise avoids by keeping `recordings.csv` per
Execution. Recommended resolution (not yet in the document as a firm decision): treat
`instruments.json` as write-once-if-absent (never overwritten by an ordinary run; only
(re)written by an explicit `reed describe --refresh` or equivalent), or generate it purely
on demand from the Flow object in memory rather than persisting it automatically at all.

### 17.4 Lazy-vs-declared `Instrument` conflict detection is asserted but not designed

Section 16.2 states that calling `ctx.record(...)` with an undeclared name, when a Node
already has an explicit `instruments=` list, "is a composition-time-adjacent error" — but
does not say what happens if a *lazily*-declared Instrument's inferred `kind`/`unit` later
conflicts with a value recorded under the same name with a different `unit` (a Node not
using `instruments=` at all, calling `ctx.record("speed", 18.4, unit="m/s")` once and
`ctx.record("speed", 60, unit="mph")` later). This is exactly the kind of schema drift
Section 6/11 already worried about for `attributes`, but for `unit`/`kind` specifically on
an Instrument it is worse, because unit mismatches silently corrupt any aggregate computed
over that series. This needs an explicit rule (most likely: the first observed
`kind`/`unit` for a given lazy `name` within a Node execution's Instrument cache is
authoritative, and any later call with a different `unit` for the same `name` raises,
mirroring the fail-fast posture already used everywhere else in this document) before
`ctx.record()` ships.

### 17.5 `kind="event"` is explicitly unresolved, not merely deferred style

Flagging this so it isn't lost: Section 16.2 withdraws `"event"` from `Instrument.kind`
pending research, which means **there is currently no designed mechanism for the
non-metric, non-Instrument recordings that motivated much of Sections 6–13** (a planner's
decision, a label, an arbitrary fact) once `Instrument.kind` is restricted to
gauge/counter/updown_counter. Every worked example in Sections 11–13 using
`ctx.record(name="reason", value="conflict avoidance")` needs a concrete home under the
Section 16 model before this design is implementation-ready — either a separate `Fact`
concept parallel to `Instrument`, or a decision that such recordings still go through
`Instrument` with `kind` left optional/`None`. This is not a defect in the document so much
as an explicitly-flagged unfinished piece that should not quietly disappear between rounds.

### 17.6 Minor: redundant identity columns need one documented rule, not ad hoc denormalization

Section 16.3 denormalizes `flow_id`/`node_id` onto every `Recording` row "for convenience,"
following the same reasoning already used for `node_id` in Section 12.1 and `node_id`/
`execution_seq` in Section 8/13.1. Worth stating once, in one place, rather than repeating
the justification piecemeal each time a new redundant column is added: **any identifier
resolvable via a join is nonetheless denormalized onto `Recording`/`provenance.csv` rows
whenever doing so lets a simple filter avoid a join** — this is now a general rule of this
design, not a series of one-off decisions, and should be written as such rather than
rediscovered per section.

---

## Round 6 (implementation, Milestone O1, Slice O1a) — resolving `flow_id`/`node_id`
cross-run stability (Section 17.1)

This section resolves the most severe open item flagged in Section 17.1 and, as a direct
byproduct, most of Section 17.2. It is written as part of implementing
`docs/observability_harness.md`'s Slice O1a, per that slice's own definition of done: "this
is a design decision, not just code — it must be written back into `observability_design.md`
as a new round/section... before O1b proceeds."

### 18.1 The decision: derive both ids deterministically from source-level identity

`node_id` = `f"{function.__module__}.{function.__qualname__}"` for the function wrapped by a
`FlowNode` (implemented as `FlowNode.node_id`). This is stable across separate process runs
of the same source code, because it depends only on where the function is defined in the
module tree — never on `id(self)`, memory addresses, or anything else that differs between
processes. It is deliberately **not** required to be globally unique (Section 16.5's
retraction of the uniqueness-validation proposal stands unchanged): two `FlowNode`s, in the
same Flow or different Flows, can share a `node_id` without correlation ambiguity, because
every observability key that uses `node_id` uses it together with `flow_id`
(`instrument_id = (flow_id, node_id, name)`).

`flow_id` = the first 16 hex characters of the SHA-256 digest of this Flow's registered
`FlowNode.node_id` values, joined by `"|"`, in registration order (implemented as
`Flow.flow_id`). Computed fresh from the Flow's current `flow_nodes` on every access, never
cached — `flow_id` is a pure function of "which FlowNodes are registered, in what order" at
read time, so it is never stale relative to the Flow's actual composition.

No new parameter is added to `Flow.add(...)` or anywhere else (`docs/observability_non_goals.md`
Section 8 stands: no `name=` parameter). No user-supplied identifier is required at all —
both ids fall directly out of source code that already exists.

### 18.2 Why this resolves Section 17.1

Running the same script — the same sequence of `Flow.add(...)` calls over the same function
objects — in two separate OS processes produces the same `flow_id` and the same `node_id`s
both times, because the derivation depends only on module path, qualified name, and
registration order, none of which vary between process runs of unchanged source. This is
the cross-run stability Section 17.1 flagged as undesigned.

### 18.3 Why this resolves most of Section 17.2 as a byproduct, not a separate mechanism

Section 17.2 asked "should a Flow code change force a new `flow_id`?" — this question
presupposed `flow_id` was an independent, storable value that could either change or be
kept the same under a code edit, requiring a policy either way. Under this section's
derivation, that presupposition is false: `flow_id` is never stored or assigned, only
computed from the current composition. Adding, removing, or reordering a `FlowNode`
necessarily changes the joined `node_id` string and therefore the hash — there is no
separate versioning mechanism to design, because there was never an independent value to
version. What remains of Section 17.2 (whether *reordering alone*, with no other semantic
change, "should" count as a new Flow) is a much narrower question than originally posed,
addressed directly in 18.4 below.

### 18.4 Known, accepted limitations (not blocking)

- **Order-sensitivity.** Reordering two independent `Flow.add(...)` calls changes `flow_id`,
  even though the resulting Flow is behaviorally identical (registration order does not
  currently affect dispatch, which is type-based via `ArtifactDependencyGraph`). This
  section chooses the simpler, more conservative rule — any structural change to the
  sequence of registrations produces a new `flow_id` — over a sorted-set derivation that
  would need its own justification for *which* structural changes matter. If this proves
  too strict in practice (e.g. two semantically-equivalent scripts that happen to register
  nodes in a different order), that is future work for a later round, not a defect this
  round leaves unstated.
- **Structural collision.** Two independently authored Flows that happen to register the
  exact same sequence of node functions (same modules, qualified names, and order) collide
  on `flow_id`. This is judged an acceptable, narrow, low-stakes trade-off of a fully
  deterministic, zero-configuration derivation — not the "some UUID will do" shortcut
  Section 17.1/`observability_non_goals.md` Section 10 warned against, which is a
  qualitatively different failure (non-reproducible identity, not an occasional identity
  collision between unrelated Flows).
- **Function identity edge case.** If the exact same function object is registered twice in
  one Flow (already an unusual case; ordinarily caught by the pre-existing one-producer-
  per-artifact-type invariant unless the two registrations produce different artifact
  types), both `FlowNode`s report the same `node_id`. This is the same category of accepted
  non-uniqueness already established in Section 16.5, extended to this literal edge case
  rather than special-cased away.

### 18.5 Status

Section 17.1 is resolved for Milestone O1's purposes as of this section; `execution_id`
(Slice O1b), `node_id`/`node_name` (Slice O1c), `node_execution_id` (Slice O1d),
`execution_seq` (Slice O1e), and the `NodeContext` identity bundle (Slice O1f) are
implemented on top of this section's `flow_id`/`node_id` derivation — see
`docs/observability_implementation_state.md` for the completed-slice record and
`src/reed/observability/identity.py`, `FlowNode.node_id`/`.node_name`, `Flow.flow_id`,
`Run.execution_id`/`.flow_id`/`._begin_node_execution`, and `NodeContext.identity` for the
implementation itself.

Section 17.2's narrower remaining question (whether registration-order changes alone should
count as a new Flow) and Section 17.5 (`kind="event"`'s fate) remain open, tracked in
`docs/observability_implementation_state.md`'s open-questions log, not resolved here.

---

## Round 7 (implementation, Milestone O2, Slice O2e) — resolving `kind="event"` (Section 17.5)

This section resolves Section 17.5/16.2's withdrawn `kind="event"` question, per
`observability_harness.md`'s Slice O2e definition of done: research the question, resolve
it, and write the decision back here before continuing to Milestone O3.

### 19.1 The decision: non-metric facts are `Recording`s with `kind=None`, never an
`Instrument.kind` value

`Instrument.kind` remains restricted to `"gauge"`/`"counter"`/`"updown_counter"` (Section
16.2 stands unchanged — no `"event"` is added to that set). Separately, `Recording.kind` is
typed `str | None`: a `Recording` produced from a declared `Instrument` always carries that
Instrument's concrete `kind`; a `Recording` produced in **lazy mode** — `ctx.record(name,
value)` with no `Instrument` object and no prior `instruments=[...]` declaration for that
Node — always carries `kind=None`. `kind=None` is the answer to "what happens to a
non-metric, non-Instrument fact": it is simply a `Recording` with no `Instrument` behind it,
not a special `Instrument.kind` value and not a separate `Fact` type.

This was implemented, ahead of this section being written, as the natural consequence of
Slice O2d's lazy-mode design (`docs/observability_implementation_state.md`'s O1d/O2c/O2d
entries; `NodeRuntime._resolve_instrument`, `reed/observability/recording.py`) — this
section formalizes that as the deliberate answer to Section 17.5, not an accident to
retroactively bless. `ctx.record(name="reason", value="conflict avoidance")` (Section 11-13's
running example) already works exactly this way: a plain string name, no `Instrument`,
`Recording.kind` is `None`, `Recording.value` is the scalar string.

### 19.2 Why not a separate `Fact` type

Section 17.5 posed two options: "either a separate `Fact` concept parallel to `Instrument`,
or a decision that such recordings still go through `Instrument` with `kind` left
optional/`None`." A separate `Fact` type was rejected: it would duplicate `Recording`'s
entire shape (`name`, `value`, identity columns, `attributes`) for no behavioral difference —
a `Fact` and a metric `Recording` are stored identically, queried identically (both are rows
in `recordings.csv`, Milestone O3), and differ only in whether an `Instrument` with a
concrete `kind` stands behind them. Encoding that one difference as `kind: str | None` on the
single existing `Recording` type is simpler, avoids a second parallel API surface on `ctx`
(`docs/observability_non_goals.md` Section 2: no new `ctx.*` vocabulary), and costs nothing a
`Fact` type would have bought.

### 19.3 Why not `Instrument.kind` left optional

The alternative — making `Instrument.kind` itself `str | None` and letting a `None`-kind
`Instrument` represent a fact — was also rejected: `Instrument` is specifically the
declaration of *how to interpret a metric for projection into OTel* (`kind` gates the OTel
Metric mapping, `docs/observability_goals.md` Section 8). A fact is not an
OTel-projectable metric at all; it should never need to go through `Instrument`'s
declaration path (`instruments=[...]`) to be recorded, and lazy mode already gives it a path
that requires no declaration whatsoever. Making `Instrument.kind` optional would blur
`Instrument`'s one concrete responsibility for a case that already has a simpler answer.

### 19.4 Consequence for declared mode

A Node that declares `instruments=[...]` and calls `ctx.record(...)` with a name in that list
always gets a concrete `kind` (Section 19.1) — declared mode is exclusively for metrics.
Declaring an `Instrument` is not, and does not become, the mechanism for recording a
non-metric fact; lazy mode is that mechanism, unconditionally available on every Node
regardless of whether it also declares `instruments=[...]` for its metrics.

### 19.5 Status

Section 17.5 is resolved. `docs/observability_goals.md` and `docs/observability_non_goals.md`
are updated to match (see their own edit history). No production code changed as a direct
result of this section — Slice O2d's implementation already matched this decision; this
section is the formal record that it was a deliberate choice, not an oversight.

---

## Round 8 (implementation, Milestone O3) — storage implementation notes

Milestone O3 (Local Recording Store, Slices O3a-O3e) is implemented on top of Sections 16.4
and Section 6 of `observability_goals.md`. Two implementation decisions worth recording here,
since they narrow prior open-ended language into concrete behavior:

### 20.1 Durable storage is opt-in per `Run` (`storage_root=`), not a default

`Flow.run()`/`Run.__init__` gained an optional `storage_root: str | None` parameter. When
omitted (the default), Recordings remain in-memory only (`NodeRuntime.recordings`) exactly
as Milestone O2 left them — no `.reed/` directory is created, no file is written. When
provided, `.reed`-style storage is created and populated under that root as Section 16.4
describes.

This was a deliberate, narrower choice than "durability is Reed's default behavior for every
Run," made for a concrete reason: the existing regression-protected test suite (`Run`,
`NodeRuntime`, `Flow`) calls `flow.run()` freely, dozens of times, with no expectation that
doing so writes files to disk. Defaulting durable storage to "on" would have silently turned
every such test (and every future one, and any script that calls `flow.run()` without
thinking about observability) into a filesystem side effect — directly in tension with
architectural_invariants.md #25, "observability failures must never change application
semantics," read here in its stronger form: observability *presence* should not change
application behavior either, unless explicitly requested. Opt-in via `storage_root=` keeps
every existing caller's behavior byte-for-byte unchanged and makes durable persistence a
conscious choice, matching how `flow.add(instruments=[...])` is also opt-in (Section 16.2)
rather than mandatory.

This does not contradict the durability boundary contract (Section 13.2/`observability_
goals.md` Section 5): that contract describes what happens *once storage is configured*, not
a claim that storage is always configured. Future work: revisit whether a process-wide
default `storage_root` (e.g. from configuration or an environment variable) is desirable once
there is a concrete “I want durability but forgot to ask for it” complaint — not designed
here, since no one has needed it yet.

### 20.2 The durability boundary is satisfied by synchronous per-call flush, not by
flush-on-exit wiring (Slice O3c)

Section 13.2/`observability_goals.md` Section 5 describe the boundary as "Recordings
accepted during a NodeExecution are guaranteed to be durably flushed when that NodeExecution
exits." The V1 CSV stores (`CSVRecordingStore`/`CSVProvenanceStore`,
`src/reed/observability/storage.py`) flush and `fsync` synchronously on every `append(...)`
call — meaning a Recording is durable the instant `ctx.record(...)` accepts it, strictly
before the boundary the contract requires, not merely by the boundary. This satisfies Slice
O3c's flush-wiring requirement without needing a separate `finally`-equivalent block around
the Node body: there is no deferred, in-flight batch to flush at exit, because nothing is
ever buffered past one `ctx.record()` call.

This is an explicit V1 latency/simplicity trade-off, not a batching optimization deferred by
oversight: `docs/observability_non_goals.md` Section 5's caution against "an `fsync` per
`ctx.record()` call" was aimed at using that as a patch over an unqualified "never lossy"
claim, which is not what is happening here — the boundary contract itself is unchanged and
still explicitly qualified (a crash *before* `ctx.record()` is called loses nothing that was
never recorded; there is no longer a window between "recorded" and "durable" to worry about
at all, because that window is now zero). If hot-path latency becomes a real concern for a
high-frequency-recording Node, buffering with an explicit flush-at-boundary is legitimate
future work, deferred rather than designed here.

## Round 9 (Milestone O4, Slices O4a-O4c): Provenance event wiring

### 21.1 Identity is minted for every firing, not only Nodes that declare `NodeContext`

Section 18/Slice O1f originally scoped `NodeExecutionIdentity` minting to "extend
`NodeContext` with the narrow, read-only identity bundle" — which, in the `Run._fire(...)`
implementation at the time, meant `_begin_node_execution(...)` was only ever called from
inside `_build_call_kwargs(...)`'s `if flow_node.context is not None:` branch. A Node with no
`NodeContext` parameter never had an identity minted for its firing at all.

Milestone O4 needs a `node_execution_id`/`node_id`/`execution_seq` to attach to every
Provenance event, for every firing, whether or not that Node ever asked for a `NodeContext`
handle — Provenance is about what the *Run* did, not about what a Node chose to look at. So
`Run.publish(...)`'s cascade loop now calls `self._begin_node_execution(flow_node)`
unconditionally, once per firing, before `_build_call_kwargs(...)` and `_fire(...)`, and
passes the resulting `identity` into both as a parameter rather than letting
`_build_call_kwargs(...)` mint it conditionally as a side effect.

This is a refinement of Section 18/21's original scope, not a reversal: `NodeContext.identity`
is still only *visible* to Nodes that declare a `NodeContext` parameter (nothing changes
there); what changes is that the identity now always exists, for every firing, regardless of
whether anything reads it via `ctx.identity`. `execution_seq` was already a Run-wide
monotonic counter (Section 13.1) incremented per firing; this change makes that increment
unconditional too, so `execution_seq` now advances once per firing for every Node, not only
for Nodes with a declared context.

### 21.2 "generated"/"used" events wired at the same two points the design already named

Section 13.2/`observability_goals.md`'s Provenance section already specified: a "generated"
event when a firing's own output is committed, and a "used" event for each already-committed
consumed artifact type a firing reads. `Run._fire(...)` now emits exactly these:

- `_emit_used_provenance_events(flow_node, identity)`, called before the node function runs,
  iterates `flow_node.consumed_artifacts` and looks up
  `self._repository.get_artifact_record(descriptor.domain_type)` for each; if a committed
  record already exists, a `"used"` `ProvenanceEvent` is appended carrying that record's
  `version.number`. If no record exists yet (nothing has produced that type before), nothing
  is emitted — there is no `artifact_version` to report, matching Section 13.2's "nothing to
  report the first time a type is consumed with no prior producer."
- `_emit_generated_provenance_event(record, identity)`, called after `node_runtime.commit(record)`
  succeeds, appends a `"generated"` `ProvenanceEvent` for the artifact this firing itself
  just committed.

Both are no-ops when `self._provenance_store is None` (Milestone O3's opt-in `storage_root=`
decision, Section 20.1, applies identically here — no `storage_root` means no Provenance
events are constructed or written at all, not merely that they're discarded).

`ProvenanceEvent.artifact_id` is derived via a new `Run._artifact_id(domain_type) -> str`
static helper using the same `f"{domain_type.__module__}.{domain_type.__qualname__}"`
derivation `FlowNode.node_id` uses (Section 18.1) — deliberately, for the same reason: stable
across process runs, no user-supplied identifier required, no new identity mechanism
introduced for artifact types.

### 21.3 Status

Milestone O4 (Slices O4a-O4c) complete. No new open design questions surfaced. The narrowed
registration-order-forces-new-`flow_id` question (Section 18.4/`observability_goals.md`
Section 10) remains the only explicitly open, non-blocking item.

## Round 10 (Milestone O5, Slice O5a): Level 1 Execution Trace implemented

### 22.1 `ExecutionTrace`/`TraceEvent` (`src/reed/observability/trace.py`)

Section 11.1's Level 1 is implemented as `reed.observability.trace.ExecutionTrace`: a
bounded, in-memory ring buffer (`collections.deque(maxlen=capacity)`, default capacity
1000) of `TraceEvent`s. `TraceEvent` is deliberately thinner than `Recording`/
`ProvenanceEvent` -- `event_type` (`"node_started"`/`"node_finished"`), the same identity
fields every Level 2 record already carries (`execution_id`, `flow_id`, `node_id`,
`node_execution_id`, `execution_seq`), and `timestamp`. No `value`, no `attributes`, no
`unit` -- Level 1 answers "what ran, in what order", not "what did it observe."

`Run` always constructs an `ExecutionTrace` (`self._trace`, exposed as `run.trace`),
unconditionally -- unlike `recording_store`/`provenance_store` (Milestone O3), which are
opt-in via `storage_root`. This is not an inconsistency: Level 1 has no durability contract
to opt in to (Section 11.1 says it "may be dropped when the process exits without anyone
having asked for it to be kept"), so there is no existing-caller behavior to protect by
defaulting it off the way Milestone O3's `storage_root=None` default protects every
pre-existing `flow.run()` call site from silently writing files to disk (Section 20.1). A
ring buffer with a bounded default capacity costs a fixed, small amount of memory per `Run`
regardless of whether anything ever reads `run.trace`.

`Run._fire(...)` records a `"node_started"` event immediately before calling the node
function and a `"node_finished"` event after `.commit(...)` succeeds, via a new
`_record_trace_event(...)` helper -- placed alongside, and after, the O4 `_emit_used_
provenance_events(...)`/`_emit_generated_provenance_event(...)` calls in the same method,
since all three now instrument the same two moments in a firing's lifecycle (before the call,
after the commit).

### 22.2 Deferred to O5b/O5c

The Rich-based terminal renderer that consumes `run.trace` live during a Run (O5b) and the
optional post-hoc replay reading `recordings.csv`/`provenance.csv` (O5c) are not part of this
slice. `ExecutionTrace.events` returning an immutable snapshot `tuple` is the only API surface
O5b needs to poll or subscribe to; no additional design decision is required before O5b can
be implemented directly against it.

### 22.3 Status

Slice O5a complete. No new open design questions surfaced.

## Round 11 (Milestone O5, Slice O5b): terminal renderer implemented

### 23.1 Pull-based snapshot renderer, not a live subscriber (`src/reed/observability/terminal.py`)

The legacy `EventRenderer` (Section 1) subscribed live to Bus traffic and printed as
messages arrived. `ExecutionTrace` (Slice O5a) has no subscription/callback mechanism --
`.events` is a pull-based, point-in-time snapshot `tuple`. Rather than adding a
publish/subscribe layer to `ExecutionTrace` for this slice, `render_trace_table(trace)` /
`print_trace(trace, console=...)` are pull-based: a caller renders whenever it wants a
picture of the trace so far (after each `run.publish(...)`, at the end of a Run, or on a
timer), and the render reflects whatever is currently in the ring buffer.

This is an explicit, scoped V1 simplification, not a silent narrowing of Section 8's
"reconstructs the same kind of trace-id-correlated, Node-named, state-labeled terminal
output": the output shape is the same (one row per Node firing, node identity, status), only
the delivery mechanism (pull vs. push) differs. Live streaming remains legitimate future
work -- it would mean adding a subscriber list to `ExecutionTrace.record(...)`, not changing
any rendering logic in `terminal.py`.

### 23.2 Row shape: one row per firing, paired by `node_execution_id`

`render_trace_table(...)` groups `TraceEvent`s by `node_execution_id` (Section 13.1's
per-firing identity) so a `"node_started"`/`"node_finished"` pair renders as one row, not
two, with columns `seq` (`execution_seq`), `node` (`node_id`), a truncated
`node_execution_id`, and `status` (`"finished"` once both halves of the pair are present,
`"running"` if only `"node_started"` has been recorded -- e.g. the renderer was called
mid-firing, or the ring buffer dropped the `"node_finished"` half past capacity).

### 23.3 Status

Slice O5b complete. No new open design questions surfaced. O5c (optional post-hoc replay
reading `recordings.csv`/`provenance.csv`) is not started.

## Round 12 (Milestone O5, Slice O5c, optional): post-hoc replay implemented

### 24.1 `render_replay_table`/`print_replay` (`src/reed/observability/replay.py`)

Reads a past Execution's `recordings.csv`/`provenance.csv` (Milestone O3) back from disk and
renders them as one Rich `Table`, interleaved by `execution_seq` -- the same deterministic
observation order every Level 1/2 record already carries (Section 13.1). This is strictly
read-only and never touches a live `Run`/`ExecutionTrace`: it is a separate consumer of the
Level 2 durable stores, not an extension of the O5b live/pull-based renderer's internals
(which stay in `terminal.py`, over `ExecutionTrace`, unchanged).

Requires `storage_root` to have been configured for the Execution being replayed (Milestone
O3's opt-in, Section 20.1) -- `load_recordings(...)`/`load_provenance(...)` raise
`FileNotFoundError` rather than silently returning an empty table when the expected CSV file
does not exist, so "no storage was configured for this run" is never confused with "this run
recorded nothing."

### 24.2 Status

Slice O5c (optional) complete. Milestone O5 (Execution Trace: ring buffer, terminal renderer,
post-hoc replay) is now fully complete. No new open design questions surfaced.

## Round 13 (Milestone O6, Slice O6a): OTel exporter adapter implemented

### 25.1 `opentelemetry-api`/`opentelemetry-sdk` are an optional extra, never core

`pyproject.toml` gained a new `otel` optional-dependency group
(`opentelemetry-api`/`opentelemetry-sdk`), alongside the existing `dev` group. No core Reed
module imports `reed.observability.otel_export` -- a caller who wants OTel export imports it
explicitly, and gets Python's own `ModuleNotFoundError` if the extra was not installed. This
is a direct, mechanical consequence of Section 8's already-decided principle ("OTel is an
exporter target, not a foundation Reed's core sits on top of") and Section 2's guiding
principle, not a new architectural decision -- it did not need a dedicated design slice.

### 25.2 `export_trace_to_spans`/`export_recording_to_metric` (`src/reed/observability/otel_export.py`)

`export_trace_to_spans(trace, *, tracer)` translates complete `"node_started"`/
`"node_finished"` `TraceEvent` pairs (Slice O5a) into OTel spans, named after `node_id` and
carrying `execution_id`/`flow_id`/`node_execution_id`/`execution_seq` as span attributes --
using each event's own recorded `timestamp` for the span's start/end time, not the
wall-clock time export happens to run at (a replayed/deferred export must not misreport when
a Node actually ran). An incomplete pair (only `"node_started"` observed -- e.g. the ring
buffer dropped the other half past capacity) produces no span, mirroring `terminal.py`'s
"running" status rather than fabricating an end time.

`export_recording_to_metric(recording, *, meter)` is strictly kind-gated per
`docs/observability_non_goals.md` Section 4 ("do not infer OTel export mappings from Python
types"): `"gauge"` maps to `meter.create_gauge(...).set(...)`, `"counter"` and
`"updown_counter"` map to `meter.create_counter(...)`/`meter.create_up_down_counter(...)`
with `.add(...)`. A lazy-mode `Recording` (`kind=None`, Section 19) is never exported as a
metric -- there is no `Instrument` behind it to determine which OTel instrument kind it would
even be, so the function returns `False` and records nothing, rather than guessing from
`type(recording.value)`.

Both functions take an already-configured `Tracer`/`Meter` as a parameter; this module owns
no `TracerProvider`/`MeterProvider` construction or global OTel configuration -- provider
setup and export destination (console, OTLP collector, in-memory for tests, ...) are the
caller's concern.

### 25.3 Status

Slice O6a complete. No new open design questions surfaced.

## Round 14 (Milestone O6, Slice O6b): `reed describe` implemented

### 26.1 `describe_flow`/`describe_instruments_manifest` (`src/reed/observability/describe.py`)

`describe_flow(flow)` builds a Rich table of every `FlowNode` in a `Flow` and its declared
Instruments, reading `Flow.flow_nodes`/`FlowNode.instruments` directly -- **no execution
required**, matching the harness row's own framing: a Node's declared Instruments are part
of its own definition (Milestone O2's `flow.add(node, instruments=[...])`), not something
that only exists once something has run. A Node declared with no Instruments still appears
as a row with blank instrument columns, so `describe` always reports every Node in the Flow.

`describe_instruments_manifest(path)` is the same report sourced from a past Run's
`instruments.json` (Milestone O3, Slice O3e) instead of a live `Flow` object -- for
introspecting a Flow whose source is not importable right now, only its manifest.

Lazy-mode Recordings (`kind=None`, Section 19) are, by construction, undeclared -- there is
nothing for `describe` to introspect about them without an actual `recordings.csv` to read.
That is explicitly `reed query`'s job (Slice O6c), not `describe`'s -- `describe` answers
"what can this Flow observe", `query` answers "what did a past Run actually observe."

### 26.2 Status

Slice O6b complete. No new open design questions surfaced. This slice implements the
Python-level introspection functions the harness row names; no `argv`-parsing `reed`
executable/console-script entry point was added in this slice (out of scope for O6b as
written -- the harness row describes the `reed describe <flow>` capability, not a specific
CLI-wiring requirement, and no existing CLI entry point exists in this repository to extend).

## Round 15 (Milestone O6, Slice O6c): `reed query` implemented

### 27.1 `query_recordings`/`recordings_glob_pattern` (`src/reed/observability/query.py`)

Implements and documents the canonical cross-Execution aggregation pattern Section 16.4/17.1
named: a glob over `<storage_root>/runs/*/recordings.csv`, filtered by the `flow_id` column
(recordings.csv is partitioned by `execution_id`, never by `flow_id`, so filtering by
`flow_id` is always a column filter across many files). The module docstring gives the
canonical DuckDB and Polars query strings verbatim, and `query_recordings(...)` is a pure-
Python reference implementation of the same pattern with no DuckDB/Polars dependency --
suitable for small local exploration and this repository's own tests, not a replacement for
either tool at real Run volume.

### 27.2 Flow-shape drift (Section 17.2) is documented, not solved

Per the harness row's own instruction ("document it as a user judgment call, not solve it"),
`query.py`'s module docstring restates Section 17.2's caveat verbatim in context:
aggregating many Executions under one `flow_id` assumes those Executions ran a structurally
comparable Flow, which is not automatically guaranteed by `flow_id` stability alone (Section
18.4's known accepted limitations). `query_recordings(...)` performs no detection or
warning for this -- it is out of scope by design, not an oversight.

### 27.3 Status

Slice O6c complete. No new open design questions surfaced.
