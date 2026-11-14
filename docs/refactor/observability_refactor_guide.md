# Reed Observability — Implementation Guide

## Purpose

This document defines the execution protocol for building Reed's observability system
(Issue #7): `Instrument`/`Recording`, the Execution Trace/Provenance/Recordings model, and
their local, offline persistence.

The architectural design has already been established, across five rounds of review, in
`docs/refactor/observability_design.md`. The objective of this work is to **implement the decided
architecture** — not to redesign it, and not to re-litigate decisions that document already
made and revised.

This is an **implementation task**, not an architecture-design task. Where this document and
the design record disagree, the design record wins; report the disagreement rather than
silently picking a side.

---

# 1. Source of Truth

Before implementing any slice, read the relevant observability documents.

`docs/refactor/observability_design.md` is the full design record — every round of revision, every
correction, every rejected alternative, in the order they happened. It is long by design:
it is the *history* of how the decision was reached, not just the decision itself.

`docs/refactor/observability_goals.md` distills that record into the target public API and
mechanics — read this first for "what to build."

`docs/refactor/observability_non_goals.md` defines what must **not** be introduced while building
this — read this first for "what to avoid."

`docs/refactor/observability_invariants.md` is the compact, checkable list of properties that must
remain true throughout implementation.

When implementation convenience conflicts with a decision recorded in
`observability_design.md`, the design record wins. When the documents do not determine the
answer — and two open items are already flagged as unresolved (Section 2 below) — do not
invent one. Stop and report the ambiguity.

## Authority Order

When sources disagree, resolve the disagreement by rank, not by convenience. From highest
to lowest authority:

1. **`docs/refactor/observability_design.md`** — the full design record (rounds 1-5). This is the
   accepted architectural decision, including every correction made along the way. Where a
   later round supersedes an earlier one, the later round governs (the document says so
   explicitly at each such point — e.g. Section 16 supersedes 11.2/12.3/12.5/14).
2. **`docs/refactor/observability_invariants.md`** — a compact restatement of the decisions above.
   It carries the same authority as the decisions it restates. If an invariant appears to
   say something the design record does not support, treat this as a documentation bug in
   the invariant, not a license to reinterpret the decision.
3. **`docs/refactor/observability_non_goals.md`** — explicit scope boundaries derived from the
   design record. Non-goals may narrow how a decision is implemented; they cannot justify
   violating a decision.
4. **`docs/refactor/observability_goals.md`** — the target public API and mechanics, distilled for
   implementers. Authoritative as a concrete summary, but subordinate to the design record:
   if `observability_goals.md` and `observability_design.md` disagree, that is a drift to
   fix in `observability_goals.md`, not a license to implement the goals doc's version.
5. **This document (`observability_refactor_guide.md`)** — the implementation policy for
   building the decisions above. It enacts them; it does not add architecture.
6. **`docs/refactor/observability_harness.md`** — advisory planning and milestone/slice
   decomposition. Useful for sequencing, non-binding where it conflicts with 1-5.
7. **Target architecture contract tests** (once written, e.g.
   `tests/test_observability_contract.py`) — codify the intended future API and behavior.
   Authoritative as a concrete example of the decided architecture, but subordinate to it.
8. **Regression tests** — protect current valid behavior (e.g. that `NodeContext` stays
   minimal outside the narrow identity-bundle addition Section 5 of the design record
   permits). May be superseded by an explicit design-record decision, never by convenience.
9. **Legacy/current implementation** (`src/`) — the lowest authority. Reed's current
   codebase has zero existing tracing/identity infrastructure (`observability_design.md`
   Section 2) — it is the starting point, not a constraint on the target.

A lower-ranked source never silently overrides a higher-ranked one. If two sources at
different ranks disagree, treat the higher rank as correct and **report the disagreement**
rather than resolving it quietly.

---

# 2. Known Unresolved Decisions — Do Not Silently Freeze a Default

Two items are explicitly flagged as unresolved in `observability_design.md` Section 17 and
`observability_non_goals.md` Section 10. Implementation must not proceed past the point
where either one becomes load-bearing without first resolving it explicitly and recording
the resolution back into `observability_design.md`:

1. **`flow_id`/`node_id` stability across separate process runs of the same Flow**
   (`observability_design.md` Section 17.1). This blocks Milestone O1 below and, through
   it, everything downstream — `instrument_id`, cross-Execution querying, and
   `instruments.json`'s placement under `.reed/flows/<flow_id>/` all assume it. Do not
   implement `flow_id`/`node_id` as fresh-per-process UUIDs and treat this as "close enough."
2. **`kind="event"` for non-metric Instruments/recordings** (`observability_design.md`
   Section 16.2/17.5). Every example in the design record using
   `ctx.record(name="reason", value="conflict avoidance")` needs a concrete home once
   `Instrument.kind` is restricted to `gauge`/`counter`/`updown_counter`. This blocks
   Milestone O2 below.

If a slice's implementation would require silently deciding either of these, stop and
report it as the missing decision — do not choose an answer merely to keep moving.

---

# 3. Fundamental Rule

> Implement the decided architecture. Do not redesign it.

If implementation requires choosing between alternatives that materially affect: identity
derivation, storage layout, the `ctx.record()` public signature, durability semantics, the
Instrument/Recording data model, or Node/Flow identity — and the answer is not established
by `observability_design.md`/`observability_goals.md` — **STOP**. Report:

1. the decision that is missing;
2. why implementation depends on it;
3. the alternatives discovered;
4. the affected components.

Do not choose an alternative merely to continue working.

---

# 4. Change Classification

Every production change must be classified before implementation. Use one of:

- identity/id generation (`execution_id`, `flow_id`, `node_id`, `node_execution_id`,
  `instrument_id`, `execution_seq`, `record_id`);
- `NodeContext` identity-bundle exposure;
- `Instrument`/`Recording` API surface;
- local storage (`RecordingStore`/`ProvenanceStore`, CSV writer, `manifest.json`);
- durability/flush lifecycle wiring in `NodeRuntime`;
- provenance event emission (`generated`/`used`) from the artifact-repository commit path;
- Execution Trace (Level 1) ring buffer and terminal renderer;
- exporter/tooling (OTel adapter, `reed describe`/`reed query`/`reed graph`).

If a proposed change does not fit one of these categories, stop and explain why it belongs
in this workstream. This prevents unrelated cleanup from entering under the appearance of
observability work.

---

# 5. Architectural Direction

The target model (`observability_design.md` Section 16.1):

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

Do not collapse these concepts for implementation convenience. In particular:
`execution_seq` must never be documented, in code comments or in a docstring, as
representing causality — that framing was explicitly retracted (`observability_design.md`
Section 13.1, round 4).

---

# 6. Identity Boundaries

`node_id` is identity; `node_name` is a display label. Do not add a validation rejecting
duplicate `function.__name__` within a Flow — this was proposed mid-design and explicitly
retracted (`observability_design.md` Section 16.5). The only invariant that should cause a
composition failure is the pre-existing one: within a Flow, each Artifact type has exactly
one producer.

`NodeContext` gains a small, read-only identity bundle (Section 5 of the design record) —
this is a deliberate, narrow exception to architectural invariant #26, not a general
license to add more to `NodeContext`. It must not gain a reference back to `Run`/`Flow`/
`NodeRuntime`, only string/UUID identity values for correlation.

---

# 7. `ctx.record()` Boundary

`ctx.record()` contains only information explicitly recorded by application code. Do not
inject `NodeExecutionFailed`/`NodeExecutionCancelled` or any other runtime-lifecycle fact
into it via a reserved name — this was proposed and explicitly retracted
(`observability_design.md` Section 13.2, round 4). Runtime lifecycle stays in the Execution
Trace (Level 1).

`value` is scalar-only (`str | int | float | bool`). Do not accept mappings, dataclasses,
or nested structures. Do not auto-flatten arrays/vectors into multiple rows.

---

# 8. Durability Boundary

Do not implement or describe the local record as "never lossy." The explicit, defensible
contract (`observability_design.md` Section 13.2, round 4):

> Recordings accepted during a `NodeExecution` are guaranteed to be durably flushed when
> that `NodeExecution` exits — normally, exceptionally, or through cancellation. A hard
> process crash before that durability boundary may lose the current in-flight batch.

Flush must happen in a `finally`-equivalent block wrapping the Node body — covering
success, exception, and cancellation paths — not only the happy path. Do not add an
`fsync` per `ctx.record()` call to try to close the gap; that is explicitly rejected
(`observability_non_goals.md` Section 5).

---

# 9. Storage Boundaries

- One physical `recordings.csv` and one `provenance.csv` **per Execution**
  (`.reed/runs/<execution_id>/`). Do not partition physically by Node or by Instrument —
  both were proposed and rejected (`observability_non_goals.md` Section 7).
- Do not persist a single `recordings.csv` shared across multiple Executions of the same
  Flow. Cross-Execution analysis is a query-time concern (DuckDB/Polars globbing), not a
  shared-file concern.
- `instruments.json` lives once per `flow_id` under `.reed/flows/<flow_id>/`, derived from
  Flow composition — treat it as write-once-if-absent or generated on demand, not rewritten
  by every ordinary run (`observability_design.md` Section 17.3 flags the concurrency risk
  of getting this wrong).
- `RecordingStore`/`ProvenanceStore` are logical interfaces; CSV is the V1 implementation.
  Do not couple `ctx.record()`'s public signature to CSV specifically.

---

# 10. Tests Are the Guardrails

The same regime as Reed's prior refactor applies here:

- **Regression tests** protect current valid behavior (e.g. `NodeContext`'s narrow
  surface outside the permitted identity-bundle addition) and must remain green unless an
  explicit design-record decision supersedes them.
- **Target architecture contract tests** (to be written, mirroring
  `tests/test_target_architecture_contract.py`'s pattern) describe the intended
  `Instrument`/`Recording`/storage/durability behavior. Some should start as expected
  failures and progressively become passing as slices land. Do not weaken assertions or
  convert `xfail(strict=True)` into a weaker skip to make a slice look done.
- If a test conflicts with `observability_design.md`, the design record wins — report the
  conflict.

---

# 11. Incremental Strategy

Do not attempt to build this in one pass. The authoritative milestone/slice breakdown lives
in `docs/refactor/observability_harness.md` — do not restate or re-derive it here.

> First make the identity boundary real (Milestone O1). Then build on it.

Do not build `Instrument`/`ctx.record()` (O2) before `flow_id`/`node_id` stability is
resolved (O1) — `instrument_id` depends on both being stable. Do not build the durable
store (O3) before `Instrument`/`Recording` exist (O2) — the store's schema is defined by
the Recording shape. Do not build provenance emission (O4) or the terminal renderer (O5)
speculatively ahead of the identity/API foundation they both correlate against.

---

# 12. Slice Protocol, Commit Discipline, Scope Control, Checks, Stop Conditions

These follow the same discipline established for Reed's architectural refactor
(`docs/in_evaluation_to_keep/refactor_guide.md` Sections 11-19), adapted to this
workstream's documents instead of the Flow/Run refactor's. In summary:

- Read the relevant design-record sections and inspect affected implementation/tests
  before touching production code.
- One commit = one coherent step (e.g. "add execution_id/flow_id/node_id to Run/FlowNode",
  not "add observability").
- Do not expand scope beyond the current slice's category (Section 4 above).
- Expected checks: `uv run pytest -q`, `uv run ruff check src tests` (adjust to Reed's
  actual configured commands at implementation time; report if a configured tool is
  unavailable rather than silently skipping it).
- Stop and report when: a type/ownership relation is unclear; a design-record section
  appears to contradict another; a slice would require resolving one of the two open items
  in Section 2 above as a side effect; or checks fail for a reason that cannot be explained.

---

# 13. Definition of Success

Observability is complete (for the scope this design covers — Issue #7 explicitly excludes
a LangSmith-like UI, MCP integration, and automated trace analysis) when:

- `Instrument`/`ctx.record()` exist per `observability_goals.md` Section 2, with both
  declared and lazy paths working and the conflict rules enforced;
- `flow_id`/`node_id` are stable across separate process runs of the same Flow (Section 2
  above resolved, not deferred);
- the durability boundary (Section 8 above) is implemented and covers all three
  `NodeExecution` exit paths;
- `recordings.csv`/`provenance.csv`/`manifest.json` exist per Execution, crash-safe,
  matching `observability_goals.md` Section 6;
- provenance is emitted as normalized `generated`/`used` events;
- the Execution Trace (Level 1) ring buffer and a terminal renderer exist, replacing the
  pre-Issue-4 Bus-based tracing experience without reviving any of its machinery
  (`observability_non_goals.md` Section 9);
- `kind="event"`'s resolution (Section 2 above) has been made and implemented, not left
  silently unresolved;
- no undocumented architectural decision was introduced merely to finish the work.

The goal is not the largest possible implementation. The goal is to reach the documented
design through small, verifiable, reversible slices — the same principle Reed's
architectural refactor already proved out.
