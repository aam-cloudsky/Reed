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

### Milestone 1 — Typed Composition Foundation

Composition-time correctness: signature parsing, artifact identity, and the `Flow.add(...)` surface. No `Run`/execution changes yet.

| Slice | Priorities | Delivers | Target tests it should move |
|---|---|---|---|
| 1A (current, NOT STARTED) | 1 | Typed domain signature parsing; `NodeContext` detected and excluded from input ports; `NodeContext[MemoryType, OutputType]` validated against the return type; self-flow rejected at signature level. | `test_node_signature_uses_domain_types_not_artifact_records`, `test_node_context_is_injected_and_not_registered_as_input_port`, `test_node_context_output_type_must_match_return_type`, `test_self_flow_signature_is_rejected` |
| 1B | 2, 3 | `NodeDescription`/`NodeDefinition` store artifact descriptors instead of Parcel-centered metadata; `ArtifactDescriptor` type introduced. | (supports 1A/1E; no test moves alone) |
| 1C | 4, 5 | `NodeContext` becomes a real generic class; `NodeMemory` storage boundary introduced under the run-local path. | (prerequisite for 1A's validation to check a real class; supports Milestone 2) |
| 1D | 6, 7 | `ArtifactRecord` introduced as the internal wrapper; `ArtifactProvenance`/`ArtifactVersion` carry forward `Parcel`'s existing version/provenance behavior. | regression: `tests/test_current_regression_artifacts_repository.py` must stay green |
| 1E | 8 | `DependencyRegistry` migrated to `FlowNode`/artifact-type vocabulary; unique-producer and self-flow validation enforced at Flow-composition time. | `test_duplicate_output_domain_type_is_rejected_in_one_flow`, `test_parallel_safe_branching_uses_distinct_output_artifact_types` |
| 1F | 9 | `FlowNode` created as the object returned by `Flow.add(...)`. | `test_flow_add_registers_callable_and_returns_flownode` (partial) |
| 1G | 10 | `PropagationPolicy` renamed/relocated to `TriggerPolicy`, owned by `FlowNode`. | `test_flow_add_uses_keyword_only_trigger_policy_and_on_output` (partial) |
| 1H | 11 (the `Flow.add(...)` surface only, not the full builder/execution split) | `Flow.add(...)` with keyword-only `trigger_policy`/`on_output`; rejects positional configuration ambiguity. | `test_flow_add_registers_callable_and_returns_flownode`, `test_flow_add_uses_keyword_only_trigger_policy_and_on_output`, `test_flow_add_rejects_positional_configuration_ambiguity` |

### Milestone 2 — Run And Execution Boundary

Execution-time correctness: `Run` isolation, `NodeRuntime`, commit/callback ordering. Depends on Milestone 1.

| Slice | Priorities | Delivers | Target tests it should move |
|---|---|---|---|
| 2A | 11 (remainder), 12 | `Flow` becomes a pure composition/builder object; `Flow.run()` creates a `Run`. | (prerequisite; no test moves alone) |
| 2B | 13 | `Node` migrated to `NodeRuntime`; automatic wrap/unwrap at the execution boundary; `ctx.memory` and `ctx.last_output` wired to `Run x NodeRuntime`. | `test_run_instances_isolate_node_memory`, `test_last_output_exposes_latest_committed_domain_value` |
| 2C | 14 | `NodeExecution` splits commit from `on_output` dispatch; async callbacks supported; callback failure isolated from commit; stateful firings serialized. | `test_on_output_runs_after_commit_and_receives_domain_value`, `test_async_on_output_is_supported_after_commit`, `test_callback_failure_does_not_undo_committed_output`, `test_stateful_node_runtime_firings_are_serialized` |
| 2D | 15 | `Depot` renamed to `ArtifactRepository` (storage vocabulary only; bus protocol renames stay in priority 16). | supports `run.repository.get(...)` usage in the Milestone 2 tests above |

Priorities 16-24 (message renames, `Outpost`, `OutpostBuilder`, schema, validity vocabulary, `Logistics`, transport, public decorators, public exports) remain cross-cutting vocabulary work, intentionally left unscheduled until Milestones 1 and 2 are complete.

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
