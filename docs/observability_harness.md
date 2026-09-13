# Reed Observability Harness — Build Session (2026-09-13)

Repo: `/Volumes/Scriptorium/Workspaces/reed_workspace/Reed` (branch
`7-design-opentelemetry-based-execution-tracing-and-provenance`)

Task: build a small, navigable agent harness for implementing Issue #7 (observability),
mirroring the harness Reed already used for its Issue #4 architectural refactor
(`docs/in_evaluation_to_keep/refactor_agent_protocol.md`,
`docs/in_evaluation_to_keep/refactor_guide.md`,
`docs/in_evaluation_to_keep/reed_refactor_harness.md`), but grounded in the observability
design work actually done this cycle rather than reusing that refactor's content.

## What existed already

Five rounds of design review, captured in full in `docs/observability_design.md`
(~1,260 lines), plus two documents distilling it: `docs/observability_goals.md` (target
public API and mechanics) and `docs/observability_non_goals.md` (explicitly rejected paths).
A fourth document, `docs/observability_invariants.md`, already existed as a compact
checklist of properties that must remain true — it was reviewed against the design record
during this session and found accurate and consistent with it. No production code
(`src/`) has been touched for observability yet; this is planning/harness work only, same
posture as the prior refactor's initial harness-building session.

## What this session added

- `docs/observability_refactor_guide.md` — the implementation policy for building
  observability: an Authority Order across the observability documents, a fundamental
  rule ("implement the decided architecture, do not redesign it"), and explicit callouts of
  the two decisions the design record left unresolved (Section 2 of that document), so an
  implementing agent cannot silently freeze a default for either one.
- `docs/observability_agent_protocol.md` — the operational entry point for an implementing
  agent: a navigation map, a context-loading rule, a Slice-To-Documentation routing table,
  a slice-plan template, non-goals enforcement, and stop conditions specific to this
  workstream (in particular: stop if a slice would resolve one of the two open items as an
  unplanned side effect rather than its own dedicated slice).
- `docs/observability_harness.md` (this document) — the milestone/slice decomposition
  below, plus the harness-structure table.

## Harness structure (one responsibility per document)

| Document | Responsibility |
|---|---|
| `observability_agent_protocol.md` | Operational entry point for coding agents — navigation map, context-loading rule, slice-plan template, stop conditions. |
| `observability_harness.md` (this doc) | Live checkpoint — current slice, milestone/slice breakdown, completed slices, open questions. |
| `observability_refactor_guide.md` | Implementation policy — how the build should proceed, plus the authority order when documents disagree. |
| `observability_invariants.md` | Compact list of properties that must remain true throughout. |
| `observability_non_goals.md` | Explicit scope boundaries — what must not be introduced. |
| `observability_goals.md` | Target public API and mechanics — what "done" looks like, distilled for implementers. |
| `observability_design.md` | The full design record (rounds 1-5) — every decision and correction, with reasoning. Read specific sections, not the whole document, per slice. |

## Execution policy

**Continuous execution is authorized (2026-09-13).** Completing a slice or milestone is a
checkpoint, not a stopping point -- the harness's role is to say what is done and what is
next, not to gate progress on a new instruction between slices. See
`observability_agent_protocol.md`'s "Continuous Execution Policy" section for the exact
rule and its stop conditions. "Current slice" below is updated after every slice and read
at the start of the next one; it is a live pointer, not a queue waiting on approval.

## Milestones and slices

Numbered `O1`-`O6` to avoid colliding with the prior refactor's `1A`-`3B+` numbering, since
both harnesses coexist in `docs/` referencing the same codebase.

### Milestone O1 — Identity Foundations ("what correlates with what, and does it survive a
restart?")

Blocking milestone: nothing in O2-O6 can be built correctly until this lands, because
`instrument_id`, cross-Execution querying, and `instruments.json`'s placement all assume
`flow_id`/`node_id` are stable across separate process runs of the same Flow — a property
the design record flags as **not yet designed** (`observability_design.md` §17.1).

| Slice | Delivers |
|---|---|
| O1a | **DONE.** Resolved `flow_id`/`node_id` stability across process runs (design record §17.1) by deterministic derivation from source-level identity — written back as design record §18. |
| O1b | **DONE.** `Run.execution_id` (uuid4, minted in `__init__`) and `Run.flow_id` (passthrough to `Flow.flow_id`). |
| O1c | **DONE.** `FlowNode.node_id` (module + qualname) and `FlowNode.node_name` (`function.__name__`, not required to be unique — §16.5). |
| O1d | **DONE.** `node_execution_id` (uuid4) minted per firing by `Run._begin_node_execution`, since no separate `NodeExecution` object exists yet — see design record §18.5. |
| O1e | **DONE.** `Run._execution_seq_counter`, incremented per `node_execution_id` minted; documented in code as deterministic observation order, never causality (§13.1). |
| O1f | **DONE.** `NodeContext.identity` (`NodeExecutionIdentity`, optional, defaults to `None`) attached only for firings built via `Run._build_call_kwargs` -> `NodeRuntime.build_context(identity)`. |

### Milestone O2 — `Instrument` and `Recording` API ("what can be measured, and how is one
observation recorded?")

Depends on O1 (identity must exist before `instrument_id = (flow_id, node_id, name)` means
anything). Blocked in part by resolving `kind="event"`'s fate (design record §16.2/§17.5) —
that resolution should be its own slice, not folded silently into another one.

| Slice | Delivers |
|---|---|
| O2a | `Instrument` dataclass (`name`, `kind`, `unit`, `description`); `kind` restricted to `"gauge"`/`"counter"`/`"updown_counter"` for now (no `Histogram`). |
| O2b | **DONE.** `Flow.add(..., instruments=[...])`; `FlowNode.instruments: tuple[Instrument, ...]`. |
| O2c | **DONE.** `NodeContext.record(...)` -> a bound `NodeRuntime.accept_recording` recorder; declared mode validated in `NodeRuntime._resolve_instrument`. |
| O2d | **DONE.** Lazy mode in `NodeRuntime._resolve_instrument`/`._lazy_units`; first-observed unit authoritative, later mismatch raises `ValueError`. |
| O2e | **DONE.** Resolved as design record §19: no `Fact` type, no optional `Instrument.kind` -- a non-metric fact is a lazy-mode `Recording` with `kind=None`. |

### Milestone O3 — Local Recording Store ("how is a Recording made durable?")

Depends on O2 (the store's row shape is defined by `Recording`).

| Slice | Delivers |
|---|---|
| O3a | **DONE.** `RecordingStore`/`ProvenanceStore` `Protocol`s; `CSVRecordingStore`/`CSVProvenanceStore` (`src/reed/observability/storage.py`). |
| O3b | **DONE.** `CSVRecordingStore.append`: append-only, one file per Execution, flush+fsync per call. |
| O3c | **DONE (by construction — see design record §20.2).** No separate flush-on-exit wiring needed: `CSVRecordingStore.append`'s synchronous per-call flush+fsync makes every Recording durable before the boundary, not merely at it. |
| O3d | **DONE.** `write_manifest(...)`, written once per `Run.__init__` when `storage_root` is set. |
| O3e | **DONE.** `write_instruments_manifest_if_absent(...)`; verified write-once by `tests/test_observability_o3_storage.py::test_instruments_json_write_once_if_absent`. |

### Milestone O4 — Provenance ("what data came from what?")

Depends on O1 (identity) and on Reed's existing `ArtifactRecord`/`ArtifactRepository`
commit path.

| Slice | Delivers |
|---|---|
| O4a | DONE — `provenance.csv` schema (`ProvenanceEvent`) already existed from O3a; O4a's remaining scope (identity minted for every firing, not only context-declaring Nodes) completed as a prerequisite refinement, design record §21.1. |
| O4b | DONE — `generated` events wired via `Run._emit_generated_provenance_event(...)`, called after `node_runtime.commit(record)` succeeds. Design record §21.2. |
| O4c | DONE — `used` events wired via `Run._emit_used_provenance_events(...)`, called before the node function runs, for each consumed artifact type with an existing committed `ArtifactRecord`. Design record §21.2. |

### Milestone O5 — Execution Trace and Terminal Renderer ("bring back what Issue #4 removed,
on the new foundation")

Depends on O1 (identity) for correlation; independent of O2-O4 for its minimal form (can
render trace/propagation alone), richer once O3/O4 exist for post-hoc replay.

| Slice | Delivers |
|---|---|
| O5a | DONE — `ExecutionTrace`/`TraceEvent` ring buffer (`src/reed/observability/trace.py`), always constructed per `Run`, exposed as `run.trace`. Design record §22.1. |
| O5b | Rich-based terminal renderer consuming the live ring buffer, reconstructing the pre-Issue-4 trace-id-correlated experience (design record §1, §8) without reviving any Bus/Depot/Outpost machinery (`observability_non_goals.md` §9). |
| O5c | Optional: extend the renderer to also read `recordings.csv`/`provenance.csv` for post-hoc replay of a past Execution. |

### Milestone O6 — Exporters and Tooling (deferred / lower priority)

Depends on O2-O4 existing; explicitly not required for Issue #7's core scope
(`observability_non_goals.md` §1 already excludes a LangSmith-like UI, MCP integration, and
automated trace analysis — this milestone is the remaining, smaller tooling that *is* in
scope).

| Slice | Delivers |
|---|---|
| O6a | OTel exporter adapter: translates Reed's Run/NodeExecution/Trigger events and `gauge`/`counter`/`updown_counter` Instruments into OTel spans/metrics; `kind`-gated, never inferred from `type(value)` (`observability_non_goals.md` §4). |
| O6b | `reed describe <flow>` — introspects `instruments.json`, no execution required. |
| O6c | `reed query <flow_id>` — a documented DuckDB/Polars glob pattern over `.reed/runs/*/recordings.csv` (design record §16.4/§17.2's Flow-shape-drift caveat applies: document it as a user judgment call, not solve it). |
| O6d | `reed graph <execution_id>` — a provenance-graph renderer (terminal tree, Mermaid/DOT, or standalone HTML) consuming `provenance.csv` (design record §8, round 4). |

## Current slice

**O5b — NOT STARTED.** Milestones O1-O4 and Slice O5a (Level 1 Execution Trace ring buffer)
are complete -- 182 tests passing, Ruff clean. `run.trace` is populated unconditionally for
every firing (design record §22.1). The next slice is O5b: a Rich-based terminal renderer
consuming the live ring buffer, reconstructing the pre-Issue-4 trace-id-correlated experience
(design record §1, §8) without reviving any Bus/Depot/Outpost machinery
(`observability_non_goals.md` §9).

## Open questions requiring decision (tracked, not yet resolved)

1. How `flow_id`/`node_id` are made stable across separate process runs of the same Flow
   (design record §17.1) — blocks O1b/O1c.
2. What happens to non-metric, non-Instrument facts now that `kind="event"` has been
   withdrawn (design record §16.2/§17.5) — blocks O2e.
3. Whether/when a code change to a Flow should force a new `flow_id` (design record §17.2)
   — affects O6c's documentation, not blocking for O1-O5.

## Context-loading strategy

For one slice: `observability_agent_protocol.md` → this document's current-slice section →
`observability_refactor_guide.md` → `observability_invariants.md` →
`observability_non_goals.md` → `observability_goals.md` → the specific
`observability_design.md` section(s) the Slice-To-Documentation Map names for that slice.
Never read all of `observability_design.md` for one slice.

## Baseline verification

Not yet run for this workstream — no production code has changed. The prior refactor's own
baseline (`uv run pytest -q -o addopts=''`, `uv run ruff check src tests`) remains the
starting point; re-verify it before O1a begins, since observability work lands on top of
whatever state Issue #4's merged PR (#17) left the branch in.
