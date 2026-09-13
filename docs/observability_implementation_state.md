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

**O7f — NOT STARTED.**

O7a-O7e and O7h are done. Next: O7f, replay/describe presentation corrections
(same-execution_seq disambiguation; lazy-mode describe_flow distinction). See
`docs/observability_harness.md`'s Milestone O7 table for the full slice list.

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
Re-run after O6b (2026-09-13): 198 passed (195 + 3 new O6b tests); ruff clean.
Re-run after O6c (2026-09-13): 202 passed (198 + 4 new O6c tests); ruff clean.
Re-run after O6d (2026-09-13): 206 passed (202 + 4 new O6d tests); ruff clean. **This
is the final baseline of the authorized slice sequence (O1a-O6d).**

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

### O6b — `reed describe` (2026-09-13)
- observability_design.md section(s) implemented: harness row O6b, written back as new
  Section 26 (Round 14).
- Files changed: `src/reed/observability/describe.py` (new: `describe_flow(flow)`,
  `describe_instruments_manifest(path)`).
- Tests: `tests/test_observability_o6b_describe.py` (3 tests: declared Instruments listed
  with no execution, a Node with no declared Instruments still appears as a blank row,
  manifest-sourced variant reads a past Run's `instruments.json`). Full suite: 198 passed;
  Ruff clean.
- Deviations from the slice plan (if any): implemented as Python-level introspection
  functions only -- no `argv`-parsing `reed` console-script entry point was added, since
  none exists in this repository to extend and the harness row's own wording describes a
  capability (`instruments.json` introspection, no execution required), not a specific
  CLI-wiring requirement. Flagged here explicitly rather than silently narrowed.
- New open questions discovered (if any): whether a real `reed` CLI executable is wanted as
  a separate, later piece of work (not blocking; not part of O6b's own scope).
- Follow-up filed as future work (if any): an actual `argv`/console-script `reed` CLI
  wrapping `describe`/`query`/`graph`, if the project wants a real command-line tool rather
  than importable Python functions.

### O6c — `reed query` (2026-09-13)
- observability_design.md section(s) implemented: Section 16.4/17.2, written back as new
  Section 27 (Round 15) documenting the canonical DuckDB/Polars glob query and providing a
  pure-Python reference implementation.
- Files changed: `src/reed/observability/query.py` (new: `recordings_glob_pattern(root)`,
  `query_recordings(root, flow_id)`).
- Tests: `tests/test_observability_o6c_query.py` (4 tests: aggregates rows across separate
  Executions of the same Flow, filters out rows from a different Flow's Executions, glob
  pattern matches the documented shape, unknown flow_id returns empty). Full suite: 202
  passed; Ruff clean.
- Deviations from the slice plan (if any): none -- implemented exactly as the harness row's
  "documented... not solve it" instruction specifies: Section 17.2's Flow-shape-drift caveat
  is restated in the module docstring, not detected or warned about in code.
- New open questions discovered (if any): none.
- Follow-up filed as future work (if any): none.

### O6d — `reed graph` (2026-09-13)
- observability_design.md section(s) implemented: Section 8's round-4 provenance-graph
  renderer addition, written back as new Section 28 (Round 16).
- Files changed: `src/reed/observability/graph.py` (new: `ProvenanceGraphNode`,
  `build_provenance_graph(run_dir)`, `render_provenance_tree(run_dir)`,
  `render_provenance_dot(run_dir)`).
- Tests: `tests/test_observability_o6d_graph.py` (4 tests: graph grouped by artifact
  version with correct producer, a "used" edge appears once both producer and consumer have
  fired, rendered Rich tree contains the artifact type and producer node, rendered DOT text
  is a valid-looking digraph containing the same names). Full suite: 206 passed; Ruff
  clean.
- Deviations from the slice plan (if any): none.
- New open questions discovered (if any): none.
- Follow-up filed as future work (if any): Mermaid/HTML provenance rendering (harness row's
  other menu options, not implemented -- Rich tree and DOT satisfy the "terminal
  tree"/"standalone page" options already); a real `argv` `reed` CLI console-script entry
  point wrapping `describe`/`query`/`graph` (same open item as O6b).

**Milestone O6 complete. The full authorized slice sequence (O2a through O6d, plus
Milestone O1 completed before the 2026-09-13 continuous-execution authorization) is now
complete. 206 tests passing, Ruff clean, zero regressions across the entire build.**

### O7a-O7b — Audit baseline + Artifact version identity fix (2026-09-13)

**Decision:** Fix `NodeRuntime.wrap(...)` so repeated firings of the same Node produce
monotonically increasing `ArtifactRecord.version` values, instead of every firing reading
`version.number == 1` forever.

**Why:** Independent audit (human-requested, post-O6) of the acceptance example's
`reed graph`/`reed replay` output showed every generation of `TrackedReading` labeled "v1"
across multiple publications. Root-caused to `NodeRuntime.wrap(...)` constructing a *fresh*
`ArtifactProvenance()` (default `pending()` -> `initial()`) on every call, and
`ArtifactRepository.set_artifact_record(...)` overwriting its dict entry without reading
the previous version. No existing regression test asserted "always version 1" as an
intentional invariant (`tests/test_slice_2e_node_execution.py` only asserts a *single*
firing reads `initial()`) -- this was an unguarded gap, not a protected behavior.

**Alternatives considered:**
1. Look up the previous committed record via `self._run.repository.get_artifact_record(domain_type)`
   and continue its version each `wrap()` call.
2. Give `NodeRuntime` one running `ArtifactProvenance`, advanced in place per firing,
   snapshotted (`.copy()`) into each returned `ArtifactRecord`. **Chosen.**

**Advantages of (2) over (1):** No repository read on every firing (keeps `wrap()` a pure,
cheap operation); correct by construction from invariant #24 ("each Artifact type has
exactly one producer within a Flow" -- so one producer-scoped counter is definitionally
the same as one type-scoped counter, without needing to prove it via a repository lookup);
matches the existing pattern already established for `Recording`/Instrument per-NodeRuntime
state (`self._recordings`, `self._lazy_units`).

**Disadvantages/risks:** A raw shared reference to the running `ArtifactProvenance` object
would let a later firing's `.advance()` call mutate an *already-committed* record's version
out from under it -- mitigated by returning `.copy()` (an independent snapshot) from every
`wrap()` call, verified by
`test_earlier_committed_records_keep_their_own_version_after_later_firings`.

**Files changed:** `src/reed/execution/node_runtime.py` (`self._provenance =
ArtifactProvenance()` in `__init__`; `.wrap(...)` advances it in place and returns a
`.copy()`-snapshotted `ArtifactRecord`).

**Tests:** `tests/test_observability_o7b_provenance_version.py` (4 tests, written and
confirmed failing against the pre-fix code first, per protocol: repeated firings increment
version; earlier records are not mutated by later firings; `provenance.csv`'s "generated"
events show distinct versions end-to-end; two different Artifact types version
independently). Full suite: 210 passed (206 + 4 new); Ruff clean.

**Evidence:** `docs/observability_design.md` Section 8 ("causally distinct Artifact
generations"); `docs/observability_invariants.md` #22 ("generation and usage are distinct
provenance events") and #24 ("each Artifact type has exactly one producer within a Flow");
direct reproduction via `examples/observability_example.py`'s own output.

### O7c — Recording durability boundary corrected (2026-09-13)

**Decision:** Batch `Recording`s per NodeExecution in memory; flush+fsync once per firing
(in a `finally` block covering success and exception), not once per `ctx.record()` call.

**Why:** Confirmed contract violation. `observability_non_goals.md` Section 5 explicitly
forbids "adding an fsync per ctx.record() call" to close the durability-boundary gap,
precisely because it "destroys the hot-path latency the synchronous, non-blocking call is
designed to protect" -- yet that is exactly what O3c's `CSVRecordingStore.append(...)` did
(flush+fsync on every single call). The design record's own Round 8/Section 20.2 had
rationalized this as "stronger, not weaker" -- a self-consistency check against the
non-goals document shows that framing does not hold: exceeding a documented guarantee at
the cost of the specific property its own non-goal protects is not "extra safety," it is an
unauthorized trade-off.

**Alternatives considered:**
1. Leave per-call fsync in place (rejected -- directly contradicts non_goals §5's explicit
   prohibition; not a defensible reading of "stronger, not weaker").
2. Batch at the whole-`Run` level, flushing once at Run end (rejected -- widens the
   durability boundary invariant #21 actually promises: "a hard process failure before
   *that boundary* may lose the in-flight batch," where *that boundary* is NodeExecution
   exit specifically, not Run exit).
3. Batch per NodeExecution (`node_execution_id`), flush in a `finally` around the Node body.
   **Chosen** -- the only option that makes "boundary = NodeExecution exit" true in the
   implementation, not merely asserted in a docstring.

**Advantages:** Restores the documented hot-path latency property; keeps the exact boundary
semantics invariants #20/#21 already commit to; empty-batch firings (no `ctx.record()`
calls) perform zero file I/O, not even an empty write.

**Disadvantages/risks:** `CSVRecordingStore.append(...)` (single-row) is retained for direct
callers, but `NodeRuntime` no longer uses it on the hot path -- a future direct caller of
`.append(...)` still pays one fsync per call, which is correct for that (non-hot-path) use
but worth remembering if `NodeRuntime` is ever refactored to call it directly again by
mistake.

**Cancellation:** Not yet a real path to exercise -- `Run._fire(...)`'s Node-body call is
fully synchronous today (Milestone O7 is not adding parallelism, per its own scope); the
`finally`-wrapped flush already covers the one exceptional exit path that exists (the Node
raising), and will cover a future `asyncio.CancelledError` unchanged once async firing
exists, since `CancelledError` propagates through `finally` like any exception. Noted as a
verified-by-construction future-compatibility point, not deferred work.

**Files changed:** `src/reed/observability/storage.py` (new `CSVRecordingStore.append_batch(...)`;
`RecordingStore` Protocol gains `append_batch`; `.append(...)` becomes a thin wrapper),
`src/reed/execution/node_runtime.py` (`self._pending_recordings` buffer; `accept_recording(...)`
buffers instead of writing through; new `.flush_recordings(node_execution_id)`),
`src/reed/execution/run.py` (`_fire(...)`'s inner `try`/`finally` calls
`node_runtime.flush_recordings(...)`).

**Tests:** `tests/test_observability_o7c_durability.py` (4 tests, written and confirmed
against the pre-fix baseline first via `os.fsync` call-counting: multiple `ctx.record()`
calls in one firing fsync once for the Recording batch (plus one for that firing's
"generated" Provenance event, out of this slice's scope); recordings durable after a
successful firing; recordings still flush when the Node raises; a firing with no
`ctx.record()` calls performs zero Recording-related fsyncs (only the Provenance event's
own fsync remains)). Full suite: 214 passed (210 + 4 new); Ruff clean.

**Evidence:** `docs/observability_goals.md` Section 5 (durability boundary contract, quoted
verbatim); `docs/observability_non_goals.md` Section 5 (explicit prohibition, quoted
verbatim); architectural invariants #20, #21, #26.

### O7h — Instrument API self-containment audit (user-prompted mid-O7) (2026-09-13)

**Decision:** `ctx.record("name", value)` is the preferred declared-mode style (no
`Instrument` object needed in the Node body); `ctx.record(instrument_object, value)` remains
supported but is now validated against the FlowNode's declared schema rather than trusted
directly.

**Why:** User-raised concern, while O7 was in progress, that the acceptance example
required `ctx.record(temperature, value)` to reference the same module-level `Instrument`
object also passed to `flow.add(..., instruments=[temperature])` -- coupling the Node body
to a global and duplicating the dependency. Auditing `NodeRuntime._resolve_instrument(...)`
found the string-name path already avoided this coupling, but the Instrument-*object* path
had a real, separate defect: it trusted the passed object's `kind`/`unit` directly, with no
cross-check against what was actually declared -- an undeclared or mismatched ad hoc
Instrument object could silently bypass the FlowNode's declared schema entirely.

**Fix:** validate the object's `.name` against `self._declared_instruments`, and its
`kind`/`unit` against the declared entry; raise `ValueError` on either mismatch.

**Files changed:** `src/reed/execution/node_runtime.py`, `docs/observability_goals.md`
Section 2.3, `examples/observability_example.py` (Node bodies switched to the name-based
style).

**Tests:** `tests/test_observability_o7h_instrument_api.py` (4 tests, confirmed failing
against pre-fix code first). Full suite: 218 passed (214 + 4 new); Ruff clean.

Full rationale, alternatives, and evidence: design record Round 18 (Section 30).

### O7d/O7e — Terminal presentation policy and API (2026-09-13)

**Decision:** `Flow.run(observability=<preset name | PresentationPolicy | None>)`; presets
(`silent`/`errors`/`progress`/`instruments`/`nodes`/`verbose`) compile to a
`PresentationPolicy` dataclass of independent boolean dimensions
(errors/progress/nodes/propagation/instruments/timings). `Run` holds one `Presenter`
(`NullPresenter` for silent), whose hooks are called from the same `_fire`/`publish`/
`accept_recording` points that already emit Trace/Provenance/Recording data -- purely
additive, no new collection mechanism.

**Progress semantics:** indeterminate (spinner + "Processed N nodes" completed-count),
never a fraction -- a reactive graph's true firing-frontier size is not knowable in
advance under `TriggerPolicy.MANUAL`/`ALL_INPUTS_CHANGED`, branching/joins, or Node
failures. This also keeps progress reporting valid unmodified under a future parallel
execution model (concurrent firings each report their own start/finish independently).

**Collection vs. presentation:** `observability=` and `storage_root=` are fully
independent `Flow.run(...)` arguments -- `observability="silent"` with `storage_root=...`
persists byte-identical `recordings.csv`/`provenance.csv` to `observability="verbose"` with
the same `storage_root`, differing only in terminal output.

**Files changed:** `src/reed/observability/presentation.py` (new: `PresentationPolicy`,
`PRESETS`, `resolve_presentation_policy(...)`), `src/reed/observability/presenter.py` (new:
`Presenter`/`NullPresenter`/`TerminalPresenter`, `build_presenter(...)`),
`src/reed/execution/run.py` (`observability=` param threaded through `__init__`; `.presenter`/
`.presentation_policy` properties; `publish(...)`'s cascade now carries `(value, depth)`
pairs, presentation-only bookkeeping; `_fire(...)` calls presenter hooks including timing
and error reporting), `src/reed/execution/node_runtime.py` (`accept_recording(...)` calls
`self._run.presenter.on_recording(...)`), `src/reed/composition/flow/flow_composition.py`
(`Flow.run(..., observability=...)` threads through to `Run(...)`).

**Tests:** `tests/test_observability_o7d_presentation.py` (11 tests): silent produces no
output; errors-only is silent on success and reports on failure; instruments mode has no
propagation arrows; nodes/verbose modes show node lifecycle; progress never renders a
`\d+/\d+` fraction; an invalid preset name raises `ValueError` clearly; presentation choice
does not change the computed domain result across all six presets; a silent terminal does
not disable Recording/Provenance persistence; the zero-argument default is not silent. Full
suite: 229 passed (218 + 11 new); Ruff clean.

Full rationale, alternatives, evidence: design record Round 19 (Section 31).

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
- **As of 2026-09-13, all slices authorized by the continuous-execution instruction (O1a
  through O6d) are complete.** Stop condition 4 of that authorization ("all remaining slices
  through O6d are complete") has been reached -- this is a genuine stopping point, not a
  checkpoint to blow past. Do not invent new slices or extend scope (a real `reed` CLI
  entry point, Mermaid/HTML provenance rendering, a Parquet storage backend, live-streaming
  trace rendering, etc. -- all noted as future work above) without new human authorization
  naming them, the same way O2a-O6d were explicitly named.
- If a human re-authorizes further work, it should name the next slice(s) explicitly (as
  O2a-O6d were named) rather than assuming "continuous execution" extends indefinitely to
  undefined future scope.
- If this file and `docs/observability_harness.md` disagree on what the current slice is,
  stop and report — do not guess which one is stale.
