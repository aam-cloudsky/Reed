# Reed Observability — Implementation State

Status: live operational checkpoint for the observability build (Issue #7), analogous to
`refactor_state.md` from Reed's prior architectural refactor. This document starts nearly
empty on purpose — no implementation slice has begun yet. It exists so the next agent (or
the next session) reads current, ground-truth state here first, rather than re-deriving it
from `observability_design.md` or guessing from `git log`.

Update this file at the end of every slice, per `observability_agent_protocol.md`'s
"Observability-State Update" section: when a slice completes, when a new open question is
discovered, when one of the two flagged open items is resolved, or when a known
architectural question is resolved or newly discovered. Do not leave it stale after
meaningful progress.

## Current slice

**O6b — NOT STARTED.**

Milestones O1-O5 and Slice O6a (OTel exporter adapter) are complete (continuous execution
authorized). Next: O6b, `reed describe <flow>`. See `docs/observability_harness.md` for the
full milestone/slice table.

## Baseline verification

Run before Milestone O1 (2026-09-13): `uv run pytest -q -o addopts=''` → 145 passed;
`uv run ruff check src tests` → all checks passed (ruff was not installed in the venv;
`uv sync --extra dev` installed it, `ruff==0.16.7`). Re-run after O1 (2026-09-13):
`uv run pytest -q -o addopts=''` → 156 passed (145 baseline + 11 new O1 tests);
`uv run ruff check src tests` → all checks passed.
Re-run after O2 (2026-09-13): 167 passed (156 + 11 new O2 tests); ruff clean.
Re-run after O3 (2026-09-13): 172 passed (167 + 5 new O3 tests); ruff clean.
Re-run after O4 (2026-09-13): 177 passed (172 + 6 new O4 tests); ruff clean (one
forward-ref lint error fixed: `ArtifactRecord` type hint needed a `TYPE_CHECKING` import).
Re-run after O5a (2026-09-13): 182 passed (177 + 5 new O5a tests); ruff clean.
Re-run after O5b (2026-09-13): 186 passed (182 + 4 new O5b tests); ruff clean.
Re-run after O5c (2026-09-13): 190 passed (186 + 4 new O5c tests); ruff clean.
Re-run after O6a (2026-09-13): 195 passed (190 + 5 new O6a tests); ruff clean
(opentelemetry-api/-sdk installed via new `otel` optional-dependency extra).

## Completed slices

### O1a — Resolve `flow_id`/`node_id` cross-run stability (2026-09-13)
- observability_design.md section(s) implemented: written back as new Section 18 (Round 6).
- Files changed: `docs/observability_design.md` (+Section 18), `docs/observability_goals.md`
  (§3, §10), `docs/observability_non_goals.md` (§10).
- Tests: none (design decision only, no production code in this slice).
- Deviations from the slice plan (if any): none.
- New open questions discovered (if any): none — narrowed Section 17.2 to "does
  registration-order-only change deserve special-casing," recorded in Section 18.4 and in
  this file's open-questions log below.
- Follow-up filed as future work (if any): none.

### O1b — `Run.execution_id` / `Run.flow_id` (2026-09-13)
- observability_design.md section(s) implemented: Section 18 (via `Flow.flow_id`).
- Files changed: `src/reed/execution/run.py`.
- Tests: `tests/test_observability_o1_identity.py::test_execution_id_is_distinct_per_run`,
  `::test_run_flow_id_passes_through_to_flow`; full suite 156 passed; ruff clean.
- Deviations from the slice plan (if any): none.
- New open questions discovered (if any): none.
- Follow-up filed as future work (if any): none.

### O1c — `FlowNode.node_id` / `FlowNode.node_name` (2026-09-13)
- observability_design.md section(s) implemented: Section 18, Section 16.5.
- Files changed: `src/reed/composition/flow/flow_node.py`, and
  `src/reed/composition/flow/flow_composition.py` (`Flow.flow_id`, which depends on
  `FlowNode.node_id`; bundled into the same commit as O1b/O1c/O1d/O1e/O1f — see the note
  below).
- Tests: `test_node_id_is_deterministic_module_qualname_not_object_identity`,
  `test_node_name_is_display_only_and_allowed_to_collide`,
  `test_flow_id_is_deterministic_across_separate_instances`,
  `test_flow_id_changes_when_composition_changes`, `test_flow_id_is_a_short_hex_string`.
- Deviations from the slice plan (if any): none.
- New open questions discovered (if any): none.
- Follow-up filed as future work (if any): none.

### O1d — `node_execution_id` minted per firing (2026-09-13)
- observability_design.md section(s) implemented: Section 18.5.
- Files changed: `src/reed/execution/run.py` (`Run._begin_node_execution`), new
  `src/reed/observability/identity.py` (`NodeExecutionIdentity`).
- Tests: `test_firing_attaches_identity_bundle_observed_from_inside_node` (node_execution_id
  distinctness).
- Deviations from the slice plan (if any): no separate `NodeExecution` object exists yet
  (`Run.publish`/`Run._fire` still call the node function directly) — `node_execution_id` is
  minted by `Run._begin_node_execution` instead of a `NodeExecution.__init__`, matching how
  the rest of the execution pipeline is currently structured. Recorded as a deviation, not a
  silent architecture change: introducing a `NodeExecution` object remains available to a
  later slice if firing-scoped state grows enough to need one.
- New open questions discovered (if any): none.
- Follow-up filed as future work (if any): revisit whether a distinct `NodeExecution` object
  is warranted once Milestone O3/O4 need more firing-scoped state than `NodeExecutionIdentity`
  alone provides.

### O1e — `execution_seq` (2026-09-13)
- observability_design.md section(s) implemented: Section 13.1.
- Files changed: `src/reed/execution/run.py` (`Run._execution_seq_counter`).
- Tests: `test_firing_attaches_identity_bundle_observed_from_inside_node` (execution_seq
  increments by exactly 1 per firing, scoped to one Run).
- Deviations from the slice plan (if any): none.
- New open questions discovered (if any): none.
- Follow-up filed as future work (if any): none.

### O1f — `NodeContext.identity` bundle (2026-09-13)
- observability_design.md section(s) implemented: Section 5 (identity bundle), Section
  16.5's back-reference constraint (architectural_invariants.md #26).
- Files changed: `src/reed/composition/node/node_context.py` (`identity` slot/property,
  optional, defaults to `None`), `src/reed/execution/node_runtime.py`
  (`NodeRuntime.build_context`), `src/reed/execution/run.py`
  (`Run._build_call_kwargs` calls `_begin_node_execution` then `build_context`).
- Tests: `test_firing_attaches_identity_bundle_to_injected_context`,
  `test_firing_attaches_identity_bundle_observed_from_inside_node`,
  `test_node_context_without_identity_defaults_to_none`,
  `test_identity_bundle_has_no_back_reference_to_execution_infrastructure`.
- Deviations from the slice plan (if any): `NodeRuntime.context` (the existing, regression-
  protected property) was deliberately left unchanged rather than given an `identity=`
  parameter, because it is a property (called without parentheses at every existing call
  site) and properties cannot take arguments. A new method, `NodeRuntime.build_context(identity)`,
  was added instead, used only by `Run._build_call_kwargs`'s real firing path. This keeps the
  existing regression-protected `.context` property's behavior completely unchanged (it
  still returns a `NodeContext` with `identity=None`).
- New open questions discovered (if any): none.
- Follow-up filed as future work (if any): none.

**Note on commit granularity:** O1b through O1f were implemented and committed together
(one commit) rather than as five separate commits. They are five rows in
`observability_harness.md`'s table and are documented as five separate entries above for
traceability, but they are small, tightly interdependent changes to the same few files
(`Run`, `FlowNode`, `Flow`, `NodeContext`, `NodeRuntime`) that were designed, implemented,
and tested together as one coherent unit of work, with one shared test file
(`tests/test_observability_o1_identity.py`) exercising all of them. O1a (a documentation-only
design decision) is its own separate commit, matching the harness's requirement that it land
in `observability_design.md` before O1b proceeds.

Log format, one entry per completed slice:

```
### <Slice ID> — <name> (<date>)
- observability_design.md section(s) implemented:
- Files changed:
- Tests: <what ran, what moved from failing to passing>
- Deviations from the slice plan (if any):
- New open questions discovered (if any):
- Follow-up filed as future work (if any):
```

## Open questions log

Tracks the three items already known plus any discovered during implementation. Do not
resolve an item here silently — resolution happens in `observability_design.md` as a new
round/section, and only then is it marked resolved here.

1. **`flow_id`/`node_id` cross-run stability** (`observability_design.md` §17.1) — status:
   **RESOLVED** (2026-09-13, Slice O1a; see Section 18). No longer open.
2. **`kind="event"` fate** (`observability_design.md` §16.2/§17.5) — status:
   **RESOLVED** (2026-09-13, Slice O2e; see Section 19: non-metric facts are lazy-mode
   Recordings with `kind=None`). No longer open.
3. **Whether registration-order changes alone should force a new `flow_id`**
   (`observability_design.md` §18.4, narrowing the original §17.2 question) — status:
   **open**, non-blocking for O1-O5; affects O6c's documentation only.

### O2a-O2d — Instrument declaration, ctx.record() (declared + lazy mode) (2026-09-13)
- observability_design.md section(s) implemented: Sections 16.2, 16.3 (goals §2.1-2.3).
- Files changed: `src/reed/observability/instrument.py` (new), `src/reed/observability/recording.py`
  (new), `src/reed/composition/flow/flow_node.py` (`instruments` field),
  `src/reed/composition/flow/flow_composition.py` (`Flow.add(..., instruments=...)`),
  `src/reed/composition/node/node_context.py` (`NodeContext.record`, `_recorder` slot),
  `src/reed/execution/node_runtime.py` (`accept_recording`, `_resolve_instrument`,
  `.recordings`, `build_context(identity, recorder)`), `src/reed/execution/run.py`
  (`_build_call_kwargs` builds a bound recorder via `functools.partial`).
- Tests: `tests/test_observability_o2_instrument_recording.py` (9 tests); full suite 165
  passed at this point; ruff clean.
- Deviations from the slice plan (if any): `tests/test_slice_1c_flow_node.py::test_flow_node_has_no_dedicated_identity_field`
  asserted `FlowNode`'s exact field set; updated to include `instruments`, since that
  assertion's actual invariant (no user-supplied *identity* field) is unaffected by adding an
  observability declaration field. Recordings are in-memory only (`NodeRuntime.recordings`)
  -- no durable store yet (Milestone O3).
- New open questions discovered (if any): none.
- Follow-up filed as future work (if any): none.

### O2e — Resolve `kind="event"` (2026-09-13)
- observability_design.md section(s) implemented: written back as new Section 19 (Round 7).
- Files changed: `docs/observability_design.md` (+Section 19), `docs/observability_goals.md`
  (§10), `docs/observability_non_goals.md` (§10), plus two confirming tests appended to
  `tests/test_observability_o2_instrument_recording.py`.
- Tests: `test_lazy_mode_recording_kind_is_always_none_slice_o2e`,
  `test_declared_mode_recording_kind_is_never_none_slice_o2e`; full suite 167 passed; ruff
  clean.
- Deviations from the slice plan (if any): no production code changed as a *result* of this
  slice -- O2d's lazy-mode implementation already matched the resolved decision before this
  slice formalized it in the design record. This is noted explicitly in Section 19.5, not
  silently passed over.
- New open questions discovered (if any): none.
- Follow-up filed as future work (if any): none.

### O3a-O3e — RecordingStore/ProvenanceStore, CSVStore, manifest.json, instruments.json (2026-09-13)
- observability_design.md section(s) implemented: Section 16.4/17.3, written back as new
  Section 20 (Round 8) covering two implementation decisions: (20.1) durable storage is
  opt-in via `Flow.run(storage_root=...)`, not a default; (20.2) O3c's durability-boundary
  flush wiring is satisfied by `CSVRecordingStore`/`CSVProvenanceStore`'s synchronous
  per-call flush+fsync, with no separate finally-equivalent block needed.
- Files changed: `src/reed/observability/storage.py` (new: `RecordingStore`/`ProvenanceStore`
  protocols, `CSVRecordingStore`, `CSVProvenanceStore`, `write_manifest`,
  `write_instruments_manifest_if_absent`), `src/reed/observability/provenance.py` (new:
  `ProvenanceEvent`, ahead of its O4 emission wiring), `src/reed/execution/run.py`
  (`storage_root` param, `.recording_store`/`.provenance_store` properties),
  `src/reed/composition/flow/flow_composition.py` (`Flow.run(storage_root=...)`),
  `src/reed/execution/node_runtime.py` (`accept_recording` also appends to
  `run.recording_store` when configured).
- Tests: `tests/test_observability_o3_storage.py` (5 tests). Full suite: 172 passed; ruff
  clean.
- Deviations from the slice plan (if any): O3c required no NodeRuntime/Run code at all --
  see design record §20.2 for why the chosen store implementation already satisfies it.
  Storage is opt-in (§20.1), a deliberate narrowing not explicit in the original harness row
  wording, made to avoid every existing `flow.run()` call site silently starting to write
  files to disk.
- New open questions discovered (if any): whether a process-wide default `storage_root`
  is ever wanted (§20.1) -- flagged as future work, not blocking.
- Follow-up filed as future work (if any): batching/deferred-flush as a latency optimization
  if a high-frequency-recording Node ever needs it (§20.2); a process-wide default
  `storage_root` (§20.1).

### O4a-O4c — Provenance event wiring (2026-09-13)
- observability_design.md section(s) implemented: written back as new Section 21 (Round 9):
  (21.1) identity is now minted for every Node firing, not only Nodes that declare a
  `NodeContext` parameter -- a refinement of Section 18/O1f's original scope, required
  because Provenance events need identity for every firing; (21.2) `generated`/`used`
  `ProvenanceEvent`s wired at the two points the design already named (after commit; before
  the node function runs, for already-committed consumed types).
- Files changed: `src/reed/execution/run.py` (`publish(...)`'s cascade loop now calls
  `_begin_node_execution(...)` unconditionally and passes `identity` into
  `_build_call_kwargs(...)`/`_fire(...)`; new `_artifact_id(...)`,
  `_emit_used_provenance_events(...)`, `_emit_generated_provenance_event(...)`; new
  `TYPE_CHECKING`-guarded `ArtifactRecord` import for the type hint).
- Tests: `tests/test_observability_o4_provenance.py` (6 tests: no-op with no storage_root,
  generated event on first firing, used event when a prior record exists, events carry
  identity fields, context-free Nodes still fire and get identity). Full suite: 177 passed;
  Ruff clean.
- Deviations from the slice plan (if any): none of substance -- O4a's "schema" work had
  already landed in O3a as `ProvenanceEvent`; this slice's actual O4a-scoped work was the
  identity-minting restructuring described in design record §21.1, which the original
  harness row for O4a did not anticipate but was required for O4b/O4c to be meaningful for
  context-free Nodes.
- New open questions discovered (if any): none.
- Follow-up filed as future work (if any): none.

### O5a — Level 1 Execution Trace ring buffer (2026-09-13)
- observability_design.md section(s) implemented: Section 11.1, written back as new Section
  22 (Round 10) covering the `ExecutionTrace`/`TraceEvent` implementation and why it is
  unconditional (no `storage_root` opt-in, unlike Recordings/Provenance).
- Files changed: `src/reed/observability/trace.py` (new: `TraceEvent`, `ExecutionTrace`),
  `src/reed/execution/run.py` (`self._trace` constructed unconditionally in `__init__`,
  `.trace` property, `_record_trace_event(...)` helper called from `_fire(...)` before the
  node function runs and after `.commit(...)` succeeds).
- Tests: `tests/test_observability_o5_trace.py` (5 tests: started/finished pair per firing,
  identity fields carried, trace populated with no storage_root, ring buffer drops oldest
  past capacity, non-positive capacity rejected). Full suite: 182 passed; Ruff clean.
- Deviations from the slice plan (if any): none.
- New open questions discovered (if any): none.
- Follow-up filed as future work (if any): none -- O5b (terminal renderer) and O5c
  (post-hoc replay) are separate slices, not started.

### O5b — Terminal renderer over the Level 1 Execution Trace (2026-09-13)
- observability_design.md section(s) implemented: Section 8/Section 1's terminal-rendering
  goal, written back as new Section 23 (Round 11) covering the pull-based (not live
  push/subscribe) rendering decision and the one-row-per-firing shape.
- Files changed: `src/reed/observability/terminal.py` (new: `render_trace_table(trace)`,
  `print_trace(trace, console=...)`, `_pair_events(...)` helper).
- Tests: `tests/test_observability_o5b_terminal.py` (4 tests: one row per firing, node id and
  "finished" status appear in rendered output, "running" status shown when only
  node_started has been recorded, empty trace renders zero rows). Full suite: 186 passed;
  Ruff clean.
- Deviations from the slice plan (if any): pull-based snapshot rendering rather than a live
  subscriber, since `ExecutionTrace` has no publish/subscribe mechanism (§23.1) -- an
  explicit, scoped simplification, not a silent narrowing of the harness row's wording.
- New open questions discovered (if any): none.
- Follow-up filed as future work (if any): live streaming rendering, if a real need appears
  (§23.1); O5c (post-hoc replay) remains separate and optional.

### O5c — Post-hoc replay of a past Execution (optional) (2026-09-13)
- observability_design.md section(s) implemented: Section 8's "it can show provenance and
  recordings, not only Bus request/reply pairs", written back as new Section 24 (Round 12).
- Files changed: `src/reed/observability/replay.py` (new: `load_recordings(run_dir)`,
  `load_provenance(run_dir)`, `render_replay_table(run_dir)`, `print_replay(run_dir,
  console=...)`).
- Tests: `tests/test_observability_o5c_replay.py` (4 tests: recordings/provenance
  interleaved by execution_seq, raw row read-back, FileNotFoundError when no storage was
  configured, rendered text contains recording/provenance detail). Full suite: 190 passed;
  Ruff clean.
- Deviations from the slice plan (if any): none.
- New open questions discovered (if any): none.
- Follow-up filed as future work (if any): none. **Milestone O5 (Execution Trace) is now
  fully complete.**

### O6a — OTel exporter adapter (2026-09-13)
- observability_design.md section(s) implemented: Section 8's OTel-as-optional-consumer
  principle, written back as new Section 25 (Round 13).
- Files changed: `src/reed/observability/otel_export.py` (new: `export_trace_to_spans(trace,
  tracer=...)`, `export_recording_to_metric(recording, meter=...)`), `pyproject.toml` (new
  `otel` optional-dependency extra: `opentelemetry-api`, `opentelemetry-sdk`).
- Tests: `tests/test_observability_o6a_otel_export.py` (5 tests, `pytest.importorskip`-gated
  on `opentelemetry.sdk.trace`/`opentelemetry.sdk.metrics`: complete started/finished pairs
  become spans with the right attributes/timestamps, incomplete pairs are skipped, gauge and
  counter Recordings become the right OTel metric with the right value, lazy-mode
  `kind=None` Recordings are skipped rather than guessed). Full suite: 195 passed; Ruff
  clean.
- Deviations from the slice plan (if any): none.
- New open questions discovered (if any): none.
- Follow-up filed as future work (if any): none.

## Deviations from the design record

_(none yet — record here if an implementation slice needs to deviate from
`observability_design.md`/`observability_goals.md`, with the reason and where it was
reconciled.)_

## Execution policy decision log

**2026-09-13 — continuous execution authorized.** Human instruction: "The observability
build is now authorized to run continuously across slices. Completing a slice or milestone
is a checkpoint, not a termination condition." This supersedes the former One-Slice
Termination Rule everywhere it was stated (`observability_agent_protocol.md`,
`observability_implementation_plan.md`). The slice discipline (break down → implement →
validate → record → advance) is unchanged; "advance" now means immediately beginning the
next slice rather than stopping. Stop conditions narrowed to: (1) a genuine unresolved
architectural contradiction: (2) an unauthorized destructive/irreversible action; (3) an
unrecoverable repository state; (4) reaching the end of the authorized slice sequence.
Authorized sequence as of this entry: O2a through O6d.

## Notes for the next agent

- Read `docs/observability_agent_protocol.md` first, then this file's "Current slice"
  section, before touching any production code.
- Continuous execution is authorized (see decision log above) — do not stop after a slice
  merely because it completed; immediately continue to the next one in the authorized
  sequence unless a genuine Stop Condition is met.
- If this file and `docs/observability_harness.md` disagree on what the current slice is,
  stop and report — do not guess which one is stale.
