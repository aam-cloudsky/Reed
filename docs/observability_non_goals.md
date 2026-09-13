# Reed Observability — Non-Goals

Status: companion to `docs/observability_design.md` and `docs/observability_goals.md`. This
document exists so the negative decisions — things this design deliberately does not do,
and paths it explicitly rejected after consideration — are as visible and durable as the
positive ones in `observability_goals.md`. An item here was considered and rejected for a
reason; if that reason stops applying, revisit it explicitly rather than silently drifting
back toward it.

## 1. Scope excluded by Issue #7 itself

- A LangSmith-like UI.
- MCP integration for the observability data.
- Automated trace analysis.

These may become separate future issues; they are not part of this design.

## 2. Reed does not adopt OTel's data models wholesale

- `Recording` is **not** "the OpenTelemetry Metric data model." It adopts an
  OTel-*compatible* measurement vocabulary (`Instrument` with `name`/`kind`/`unit`/
  `description`, `Recording` with `value`), not OTel's own Instrument/Measurement/stream
  machinery. Do not implement against the literal OTel Metrics SDK data types and call it
  equivalent to this design — it isn't, and the earlier draft's claim to the contrary was an
  explicit correction made mid-design (see `observability_design.md` Section 11.2, round 4).
- Reed does **not** copy OTel's full Instrument-kind taxonomy. `Histogram` is deliberately
  excluded from V1: Reed persists every raw observation, so a histogram can always be
  computed downstream from raw `gauge`/`counter` data — do not add `Histogram` support
  without a concrete use case that raw-observation replay cannot satisfy.
- Reed does **not** expose OTel/Grafana vocabulary on `ctx`. There is no `ctx.metrics`, no
  `ctx.otel`, no `ctx.grafana`. If a future contributor is tempted to add one of these to
  make some integration more convenient, that is the coupling this design explicitly
  rejected — the fix belongs in an exporter, not on `ctx`.
- Reed does **not** adopt W3C PROV-O's RDF/OWL machinery. Provenance is modeled
  conceptually (entities/activities, `generated`/`used` events) because that shape is
  useful, not because Reed needs a semantic-web dependency. Do not introduce an RDF store,
  an OWL reasoner, or a SPARQL endpoint on the strength of "PROV is our prior art."
- Reed does **not** adopt Stable-Baselines3's typed-wrapper polymorphism (`Video`, `Image`,
  `Figure`, `HParam`). A `Recording.value` is scalar-only; a compound or non-scalar fact is
  the caller's problem to flatten (Section 3 below), not Reed's problem to dispatch on type.

## 3. Reed does not allow structure to leak into `Recording.value`

- `value` is **scalar only**: `str | int | float | bool`. Do not add mappings, dataclasses,
  lists, or nested JSON as an accepted `value` type, no matter how convenient it looks at a
  single call site — this is what keeps `recordings.csv` trivially tabular and directly
  usable by pandas/Polars/DuckDB/a spreadsheet without a parsing step for `value` itself.
- Do not auto-flatten arrays or vectors. A 3D velocity is three explicit `ctx.record()`
  calls with dot-segmented names (`velocity.x`, `velocity.y`, `velocity.z`), never a single
  call with a tuple/list that Reed silently expands into multiple rows. Implicit expansion
  is exactly the kind of magic this design rejected in favor of predictability.
- `attributes` is the one field allowed to be "structured" (a small flat mapping of
  scalars), and even there: do not let it become an escape hatch for arbitrary nested data.
  It exists for labels/tags, mirroring OTel Metric attributes — not for smuggling a
  `Recording.value`-shaped object past the scalar-only rule.

## 4. Reed does not infer OTel export mappings from Python types

- Do not write an exporter that promotes a `Recording` to an OTel metric because its
  `value` happens to be numeric. The mapping from an `Instrument` to an OTel signal is
  explicit and opt-in, driven by `Instrument.kind` — never inferred from `type(value)`.
- Do not let any `attributes` key get promoted to a metric label without an explicit
  allow-list/cardinality guard in the metrics exporter specifically. High-cardinality
  attributes (a `request_id`, a raw sensor float) are fine as recording data; they are not
  fine as metric labels, and the exporter — not the storage layer — is where that line is
  drawn.

## 5. Reed does not promise absolute, unconditional durability

- Do not describe the local record as "never lossy" without qualification. The actual,
  defensible contract is a **durability boundary**: recordings are guaranteed durable once
  their `NodeExecution` exits (success, exception, or cancellation) — not from the moment
  `ctx.record()` is called. A hard process crash before that boundary can lose the in-flight
  batch, and that is stated plainly rather than hidden behind an unqualified guarantee.
- Do not "fix" this by adding an `fsync` per `ctx.record()` call to close the gap. That
  destroys the hot-path latency the synchronous, non-blocking call is designed to protect,
  and is explicitly not the trade this design makes. If a future safety-critical mode truly
  needs per-record durability, that is a separate, explicitly opt-in mode with an explicit
  cost (e.g. `durability="immediate"`) — not the default, and not designed here.

## 6. `ctx.record()` is application data only — runtime lifecycle stays out of it

- Do not record exceptions or cancellations through `ctx.record()` (no reserved
  `__exception__`/`__cancelled__` names). `NodeExecutionFailed`/`NodeExecutionCancelled` are
  runtime lifecycle facts, already known to `NodeRuntime` independently of anything the
  application chose to record — mixing the two would mean a user can no longer treat
  `recordings.csv` as strictly "what my code explicitly recorded."

## 7. Physical storage is not partitioned by Node, by Instrument, or by Flow

- Do not implement "one CSV per Node" or "one CSV per Instrument" as an architectural
  invariant. Both were proposed during this design and both were rejected for the same
  reason: a Flow with many Nodes/Instruments turns into hundreds or thousands of small
  files per Execution, which is worse for the filesystem, for glob-based tooling, and for
  compaction than one flat, filterable table. `Instrument` (and `Node`) are **logical**
  units of a series, not physical partitioning requirements.
- Do not persist a single `recordings.csv`/`provenance.csv` shared across multiple
  Executions of the same Flow. This reopens the cross-process concurrent-writer problem
  the per-Execution boundary exists to avoid, and gives the file unbounded growth with no
  natural rotation point. Cross-Execution analysis is a query-time concern (glob + DuckDB/
  Polars), not a shared-file concern.
- Do not build a Reed-owned database or long-running service to answer cross-run queries.
  DuckDB/Polars globbing flat files already does this; adding a persistent Reed service is
  scope this design does not take on.

## 8. Node naming is not given an independent uniqueness rule

- Do not add a validation that rejects two Nodes sharing a `function.__name__` (this was
  proposed mid-design and explicitly retracted — see `observability_design.md` Section
  16.5). `node_id` is identity; `node_name` is a display label and is allowed to collide,
  in the same Flow or across different Flows. The only invariant that should ever cause a
  composition failure is the existing one: within a Flow, each Artifact type has exactly
  one producer.
- Do not add an explicit `name=` parameter to `flow.add(...)` to solve name collisions. The
  scope-corrected rule above already removes the need for it; adding a parallel identity
  parameter would be new API surface for a problem that no longer exists once `node_id` is
  used correctly everywhere.

## 9. Reed does not reintroduce the legacy Bus/Depot/Outpost machinery

- The pre-Issue-4 terminal-rendering experience is worth resurrecting, but as a consumer of
  the new `execution_id`/`node_execution_id`/trace-edge model (Level 1, Section 4 of
  `observability_design.md`) — not by reviving `DEPOT_REGISTRY`/`DEPOT_GET`/`DEPOT_SET`
  topics, `Outpost` naming, or any other piece of the Bus-based tracing that Issue #4
  deliberately removed. Nothing about this design should be read as walking that removal
  back.

## 10. Explicitly unresolved — do not silently freeze a default

- `kind="event"` for non-metric Instruments/recordings was proposed and then withdrawn
  pending research (`observability_design.md` Section 16.2/17.5). Do not ship an
  implementation that quietly reintroduces `"event"` as a `kind` value, or that quietly
  drops support for non-metric facts, without first resolving this explicitly. Both are
  live possibilities and neither has been decided.
- `flow_id`/`node_id` stability across separate process runs of the same Flow is now
  resolved (Milestone O1, Slice O1a; `observability_design.md` Section 18: both are
  deterministically derived from source-level identity — module/qualname for `node_id`,
  a hash of the registered `node_id`s for `flow_id` — never a random or user-supplied
  value). This item is no longer open; the caution below no longer applies to it, but is
  kept here as a historical note of the kind of shortcut that was correctly rejected.
