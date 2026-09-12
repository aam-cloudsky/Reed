# Reed Refactor Harness — Build Session (2026-09-12)

Repo: `/Volumes/Scriptorium/Workspaces/reed_workspace/Reed` (branch `4-replace-flow-with-an-explicit-flow-composition-api`)

Task: build a small, navigable agent harness on top of Reed's existing refactor documentation, per a detailed 14-phase spec. No production code (`src/`) was touched — documentation and repo-root routing files only.

## What existed already

A prior agent session had already drafted the core harness docs (uncommitted, in `docs/`): `refactor_agent_protocol.md`, `refactor_state.md`, `refactor_guide.md`, `architectural_invariants.md`, `non-goals.md`, `refactor_priority_order.md`, `implementation_refactor_assessment.md`, plus the ADRs (`architectural_decision.md`, `parcel_boundary_decision.md`, `node_context_decision.md`, `flow_composition_implementation_basis.md`) and the test split (`tests/test_current_regression_*.py`, `tests/test_target_architecture_contract.py`, 24 passed / 15 xfailed baseline). This session audited that material and closed the gaps rather than rebuilding from scratch.

## What this session changed (docs only)

- `docs/refactor_agent_protocol.md` — added `architectural_invariants.md` into the navigation map, context-loading rule, and required-reading list (it was drafted but never actually referenced — an agent following the protocol literally would never open it); added a Slice-to-Documentation routing table; turned an orphaned, unfenced paragraph into a proper "Blast-Radius Control" section; added an "Expected Change Surface" field to the slice-plan template; added a research source-preference order; fixed a genuine pre-existing unclosed markdown code fence that was swallowing everything from the nav-map through "Core Rule" into one literal code block.
- `docs/refactor_guide.md` — added an explicit 8-level "Authority Order" (which source wins when documents disagree); removed a second, drifting copy of the priority list (kept the canonical one in `refactor_priority_order.md` only).
- `docs/refactor_priority_order.md` — replaced a single monolithic "first implementation slice" (10 bundled concepts — really a whole milestone) with **Milestone 1 (slices 1A-1H)** and **Milestone 2 (slices 2A-2D)**, each row mapped to the specific target test(s) it should move.
- `docs/refactor_state.md` — cross-referenced the current slice as **Slice 1A**, added a "Next Recommended Slice" section (→ 1B), added `architectural_invariants.md` to related docs, logged today's re-verification.
- `docs/non-goals.md` — flagged `Flow.connect(...)` (present in early exploratory material) as superseded by the accepted type-inferred-topology decision.
- `docs/roadmap.md` — fixed a broken relative link (`reed_architecture.md` → `architecture.md`, 3 occurrences).
- New `CLAUDE.md` and `AGENTS.md` at repo root — small routing files: what Reed is, the folder map, and "read `docs/refactor_agent_protocol.md` before touching `src/`."

## Harness structure (one responsibility per document)

| Document | Responsibility |
|---|---|
| `refactor_agent_protocol.md` | Operational entry point for coding agents — navigation map, context-loading rule, slice-plan template, stop conditions. |
| `refactor_state.md` | Live checkpoint — current slice, baseline, completed slices, open questions. |
| `refactor_guide.md` | Migration policy — how the refactor should proceed, plus the authority order when documents disagree. |
| `architectural_invariants.md` | Compact list of properties that must remain true throughout. |
| `non-goals.md` | Explicit scope boundaries — what must not be introduced. |
| `refactor_priority_order.md` | Dependency order, plus the Milestone/Slice breakdown sized for one agent task each. |
| `architectural_decision.md`, `parcel_boundary_decision.md`, `node_context_decision.md`, `flow_composition_implementation_basis.md` | Accepted architectural decisions (ADRs) — what Reed becomes. |
| `implementation_refactor_assessment.md` | Mapping from current implementation to target architecture, with external-pattern rationale. |
| `architecture.md` | Conceptual overview of Reed's current four-layer architecture. |
| `roadmap.md` | Longer-range project roadmap (GitHub issues #1-#10); not the refactor-execution harness. |
| `CLAUDE.md` / `AGENTS.md` (repo root) | Thin routing files pointing any coding agent at `refactor_agent_protocol.md` before touching `src/`. |

## Milestones and slices (docs/refactor_priority_order.md)

**As of 2026-09-12 this decomposition was refined** — see "Slice decomposition
refined (2026-09-12)" below for the full rationale. The tables here reflect
the current, corrected state; the superseded 1A-1H / 2A-2D version is no
longer accurate and is not reproduced.

### Milestone 1 — Typed Composition Foundation ("what is the computation?")

Composition-time correctness only: signature parsing, artifact identity, and
the `Flow.add(...)` surface. No `Run`, no `NodeRuntime`, no execution.

| Slice | Priorities | Delivers |
|---|---|---|
| 1A (current, NOT STARTED) | 1; part of 4 | Typed domain signature parsing; self-flow rejected at signature level; minimal structural `NodeContext[MemoryType, OutputType]` shell (importable, generic, no runtime behavior yet). |
| 1B | 2, 3 | `NodeDescription`/`NodeDefinition` store artifact descriptors; `ArtifactDescriptor` type introduced. |
| 1C | 9 | `FlowNode` created (holds `NodeDefinition`, descriptors, trigger-policy/on_output fields). |
| 1D | 8 | `DependencyRegistry` migrated to `FlowNode`/artifact-type vocabulary; self-flow validation added at Flow-composition level. |
| 1E | 10 | `PropagationPolicy` renamed to `TriggerPolicy`; ownership relocated to `FlowNode`. |
| 1F | remainder of 11 | `Flow.add(...)` wiring over 1A-1E: creates `FlowNode`, validates via `DependencyRegistry`, keyword-only `trigger_policy`/`on_output`. **All nine** Milestone-1 target tests flip here (every one calls `flow.add(...)`) — none flip earlier. |

### Milestone 2 — Run And Execution Boundary ("how is one composition executed?")

Depends on Milestone 1 (1A-1F). Introduces `Run`, `NodeRuntime`,
`NodeExecution`, and the domain-value/`ArtifactRecord` boundary.

| Slice | Priorities | Delivers |
|---|---|---|
| 2A | part of 11, 12 | `Flow` becomes a pure builder; `Flow.run()` creates a `Run`; `Run.repository` accessor added (still backed by `Depot` internally). |
| 2B | part of 13 | `Node` migrated to `NodeRuntime` (run-local ownership). |
| 2C | 6, 7, part of 13 | `ArtifactRecord`/`ArtifactProvenance`/`ArtifactVersion` introduced and wired into the wrap/unwrap boundary in the same slice. |
| 2D | 5, part of 4, part of 13 | `NodeMemory` storage boundary; `ctx.memory`/`ctx.last_output` (from the 1A shell) wired to real per-run, per-runtime storage. |
| 2E | 14, part of 13 | `NodeExecution` firing pipeline (build args, execute, wrap, commit, update memory). Target tests: `test_run_instances_isolate_node_memory`, `test_last_output_exposes_latest_committed_domain_value`. |
| 2F | part of 14 | `on_output` dispatch after commit; async support; callback-failure isolation. Target tests: `test_on_output_runs_after_commit_and_receives_domain_value`, `test_async_on_output_is_supported_after_commit`, `test_callback_failure_does_not_undo_committed_output`. |
| 2G | part of 13, part of 14 | Stateful `NodeRuntime` firings serialized. Target test: `test_stateful_node_runtime_firings_are_serialized`. |

### Milestone 3 — Infrastructure Alignment ("how does Reed's internal infrastructure support that execution model?")

Depends on Milestone 2 (specifically 2C). New in this refinement — see below
for why `ArtifactRepository` moved here.

| Slice | Priorities | Delivers |
|---|---|---|
| 3A | 15 | `Depot` renamed to `ArtifactRepository`. |
| 3B+ | 16-24 | Remaining cross-cutting vocabulary work (message renames, `Outpost`, schema, validity vocabulary, `Logistics`, transport, public decorators/exports). Left undecomposed until Milestone 3 begins.

## Redundancies removed

- `refactor_guide.md` carried its own drifting 16-item copy of the priority list — removed in favor of the single canonical sequence in `refactor_priority_order.md`.

## Gaps filled

- `architectural_invariants.md` existed but was never wired into the protocol's navigation map, context-loading rule, or required-reading list — fixed in four places.
- `refactor_priority_order.md`'s "first implementation slice" bundled 10 blocking concepts into one slice — really a whole milestone, and inconsistent with `refactor_state.md`'s own narrower current slice. Replaced with Milestone 1 (1A-1H) and Milestone 2 (2A-2D) above.
- No explicit authority order existed for when documents disagree — added an 8-level ranking to `refactor_guide.md` (ADRs → invariants → non-goals → guide → priority/assessment → target tests → regression tests → legacy code).
- The "blast-radius" / expected-change-surface idea existed as an orphaned, unfenced paragraph — turned into a proper section and added as a field in the slice-plan template.
- Found and fixed a genuine pre-existing markdown bug: an unclosed code fence in `refactor_agent_protocol.md` was silently swallowing the whole middle of the document into one literal code block.

## Contradictions found

- `Flow.connect(...)` appears in early exploratory material (`architectural_decision.md`'s alternate example, `docs/roadmap.md`) but is superseded by the accepted type-inferred-topology decision — flagged in `non-goals.md` so a future agent doesn't implement it.
- `TriggerPolicy.ON_ANY_INPUT_CHANGED` (in one doc's example) vs. `TriggerPolicy.ANY_INPUT_CHANGED` (priority order + the actual test file) — a naming typo, not an architectural disagreement, corrected for internal consistency.
- No genuine unresolved architectural conflicts were found between the four ADRs themselves.

## Architectural questions requiring decision

None open, per `refactor_state.md`'s own tracker and this session's review.

## Context-loading strategy

For one slice: `refactor_agent_protocol.md` → `refactor_state.md` → `refactor_guide.md` → `architectural_invariants.md` → `non-goals.md` → the relevant row in `refactor_priority_order.md`'s Milestones And Slices table → the one or two ADRs the routing table names for that slice → the relevant tests/code. Never load all four ADRs for one slice.

## First recommended slice (not implemented)

Slice 1A — typed signature parsing, `NodeContext` detection/exclusion, output-type validation, self-flow rejection at the signature level. See `docs/refactor_priority_order.md` → Milestones And Slices → Milestone 1.

## Baseline verification

```text
uv run pytest -q -o addopts=''
24 passed, 15 xfailed

uv run ruff check src tests
All checks passed

git diff --stat -- src/
(empty)
```

Coverage percentage not re-measured this session (sandbox could not write `.coverage` in the mounted working tree); this does not affect pass/fail counts.

Production files changed: **NO**.

## Slice decomposition refined (2026-09-12)

A follow-up, scoped task ("Refine the Reed Refactor Slice Decomposition")
fixed four real dependency/sizing problems in the tables above, discovered
by re-reading `tests/test_target_architecture_contract.py` and the priority
"why" text closely rather than assuming the original grouping was load-bearing.
No new architecture was introduced; this was reordering, splitting, and
relocation of already-decided work.

**Issue 1 — NodeContext shell-before-parsing dependency.** The signature
parser cannot detect `NodeContext[MemoryType, OutputType]` in an annotation
unless `NodeContext` already exists as an importable generic type to check
`typing.get_origin(...)` against. Fix: the minimal structural `NodeContext`
shell (no runtime behavior) moved into 1A itself; the real behavior
(`ctx.memory`, `ctx.last_output`) stays in Milestone 2 (2D), because
`NodeMemory` is scoped to `Run x NodeRuntime`, which doesn't exist until then.

**Issue 2 — FlowNode / DependencyRegistry ordering.** The original order asked
`DependencyRegistry` to migrate to `FlowNode` vocabulary before `FlowNode`
existed. Priority 8's own text confirms the dependency runs the other way.
Fix: `FlowNode` (1C) now precedes `DependencyRegistry`'s migration (1D).

**Issue 3 — Milestone 2 was one oversized slice bundle.** The original four
rows (2A-2D) each bundled multiple "and"-clause transformations with no
single verifiable seam. Fix: split into seven slices (2A-2G) along those
seams, each with its own delivers-and-verifies boundary; confirmed that all
six Milestone-2 target tests gate on 2E/2F/2G, not earlier slices, mirroring
the same pattern found in Milestone 1.

**Issue 4 — ArtifactRepository (and ArtifactRecord) placement.** `ArtifactRecord`
was originally introduced in Milestone 1 with no consumer (nothing wraps or
unwraps through it until the execution boundary exists) — a real dependency
problem, not just style, and exactly what `non-goals.md`'s speculative-abstractions
rule warns against. `Depot` -> `ArtifactRepository` (originally in Milestone 2)
had the same issue relative to Milestone 3's own cross-cutting vocabulary work.
Fix: `ArtifactRecord` moved to Milestone 2 (2C), introduced and consumed in the
same slice; `ArtifactRepository` moved to a new Milestone 3 ("Infrastructure
Alignment"), which also picks up Priorities 16-24 as `3B+` (still undecomposed
by design, since that work is several milestones away).

Net effect: Milestone 1 is now 1A-1F (was 1A-1H); Milestone 2 is now 2A-2G
(was 2A-2D); a new Milestone 3 (3A, 3B+) now holds `ArtifactRepository` and
the remaining vocabulary work. Priorities 1-24 remain unchanged as the
dependency order — only their milestone/slice placement moved, and a full
Priority-to-Slice traceability table was added to `refactor_priority_order.md`
to keep that mapping explicit. `refactor_state.md`'s current-slice record was
also corrected: "target tests expected to move during slice 1A" changed from
four tests to none, since every Milestone-1 target test gates on 1F
(`Flow.add(...)`); the current slice remains 1A, NOT STARTED.

Baseline re-verified after this refinement: `uv run pytest -q -o addopts=''`
-> 24 passed, 15 xfailed; `uv run ruff check src tests` -> all checks passed;
`git diff --stat -- src/` -> empty. Only `docs/refactor_priority_order.md` and
`docs/refactor_state.md` changed.

**Ready to authorize Slice 1A: YES.** All four issues are resolved with no
open architectural question; the harness's slice-to-test mapping is now
accurate; the current slice (1A) is unambiguous and correctly scoped.
