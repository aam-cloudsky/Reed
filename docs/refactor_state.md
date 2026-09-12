# Refactor State

This document tracks the current execution state of the Reed architectural refactor.

It is a live operational checkpoint, not an architectural decision document.

Related documents:

1. `architectural_decision.md`;
2. `parcel_boundary_decision.md`;
3. `node_context_decision.md`;
4. `flow_composition_implementation_basis.md`;
5. `implementation_refactor_assessment.md`;
6. `refactor_priority_order.md`;
7. `refactor_guide.md`;
8. `refactor_agent_protocol.md`;
9. `non-goals.md`;
10. `architectural_invariants.md`.

## Workspace State

- Branch: `4-replace-flow-with-an-explicit-flow-composition-api`
- Last known base commit: `54f20ce87be8574a1bb6df1973797b1e91887aa9`
- Working tree: dirty
- Production code modified: no
- Documentation modified: yes
- Tests modified: yes

Current uncommitted work:

- `docs/implementation_refactor_assessment.md`
- `docs/non-goals.md`
- `docs/refactor_guide.md`
- `docs/refactor_agent_protocol.md`
- `docs/refactor_priority_order.md`
- `docs/refactor_state.md`
- `tests/test_current_regression_artifacts_repository.py`
- `tests/test_current_regression_flow_runtime.py`
- `tests/test_current_regression_node_description.py`
- `tests/test_target_architecture_contract.py`

## Baseline Verification

Last verified: 2026-09-12

Configured command:

```bash
uv run pytest -q
```

Result:

```text
24 passed, 15 xfailed
coverage: 86%
```

Development dependencies command:

```bash
uv sync --extra dev
```

Result:

```text
pytest, pytest-cov, coverage, and ruff installed successfully
```

Regression test command:

```bash
uv run pytest -q -o addopts='' \
    tests/test_package.py \
    tests/test_current_regression_node_description.py \
    tests/test_current_regression_flow_runtime.py \
    tests/test_current_regression_artifacts_repository.py
```

Result:

```text
24 passed
```

Target architecture contract command:

```bash
uv run pytest -q -o addopts='' tests/test_target_architecture_contract.py
```

Result:

```text
15 xfailed
```

Static check command:

```bash
uv run ruff check src tests
```

Result:

```text
All checks passed
```

## Current Slice

Milestone: 1 -- Typed Composition Foundation
Slice ID: 1A (see `docs/refactor_priority_order.md`, Milestones And Slices)

Name:

```text
NodeDescriptionBuilder / typed signature parsing
```

Status:

```text
NOT STARTED
```

Goal:

1. parse domain artifact parameters;
2. detect injected `NodeContext`;
3. reject `NodeContext` as an `InputPort`;
4. validate `NodeContext[MemoryType, OutputType]` against the return type;
5. derive artifact descriptors from domain types;
6. preserve current valid regression behavior until an explicit compatibility migration supersedes it.

Target tests expected to move during this slice:

1. `test_node_signature_uses_domain_types_not_artifact_records`;
2. `test_node_context_is_injected_and_not_registered_as_input_port`;
3. `test_node_context_output_type_must_match_return_type`;
4. `test_self_flow_signature_is_rejected`.

Definition of done:

1. the listed target tests pass without weakening assertions;
2. current regression tests still pass;
3. no production behavior outside signature parsing changes unintentionally;
4. no undocumented architectural decision is introduced;
5. ambiguity is reported if discovered.

## Completed Slices

| Slice | Commit | Tests changed | Result |
|---|---|---|---|
| None | - | - | - |

## Remaining Target Contracts

| Contract | Test | Status |
|---|---|---|
| `Flow.add(...)` returns a `FlowNode` | `test_flow_add_registers_callable_and_returns_flownode` | xfail |
| `TriggerPolicy` is stored on `FlowNode` | `test_flow_add_uses_keyword_only_trigger_policy_and_on_output` | xfail |
| `on_output` is stored on `FlowNode` | `test_flow_add_uses_keyword_only_trigger_policy_and_on_output` | xfail |
| `Flow.add(...)` rejects positional configuration ambiguity | `test_flow_add_rejects_positional_configuration_ambiguity` | xfail |
| Node signatures use domain types rather than artifact records | `test_node_signature_uses_domain_types_not_artifact_records` | xfail |
| `NodeContext` is injected and excluded from input ports | `test_node_context_is_injected_and_not_registered_as_input_port` | xfail |
| `NodeContext[MemoryType, OutputType]` must match the return type | `test_node_context_output_type_must_match_return_type` | xfail |
| Duplicate output domain type is rejected in one Flow | `test_duplicate_output_domain_type_is_rejected_in_one_flow` | xfail |
| Self-flow signatures are rejected | `test_self_flow_signature_is_rejected` | xfail |
| Distinct output artifact types allow safe branching | `test_parallel_safe_branching_uses_distinct_output_artifact_types` | xfail |
| Run instances isolate node memory | `test_run_instances_isolate_node_memory` | xfail |
| `ctx.last_output` exposes the latest committed domain value | `test_last_output_exposes_latest_committed_domain_value` | xfail |
| `on_output` runs after commit and receives the domain value | `test_on_output_runs_after_commit_and_receives_domain_value` | xfail |
| async `on_output` is supported after commit | `test_async_on_output_is_supported_after_commit` | xfail |
| callback failure does not undo committed output | `test_callback_failure_does_not_undo_committed_output` | xfail |
| stateful `NodeRuntime` firings are serialized | `test_stateful_node_runtime_firings_are_serialized` | xfail |

## Known Compatibility Layer

The following existing APIs and behaviors remain supported during the early refactor:

1. `@flow`;
2. `@input`;
3. `@node`;
4. `@output`;
5. Parcel-based node signatures;
6. current `FlowFactory` creation behavior;
7. current synchronous decorator-based flow execution.

Rules:

1. existing Parcel-based regression tests must remain green until an explicit architectural migration supersedes them;
2. compatibility aliases may be introduced when useful;
3. compatibility aliases must not hide the new architectural boundaries;
4. old decorators must not be removed in the first implementation pass.

## Known Conflicts Between Current Implementation And Target Architecture

| Area | Current implementation | Target architecture | Handling |
|---|---|---|---|
| Node boundary | User functions consume and produce `Parcel` subclasses. | User functions consume and produce domain values. | Preserve regression tests; target tests remain xfail until wrapping/unwrapping exists. |
| Artifact identity | Parcel subclass currently acts as dependency identity. | Domain type is the semantic artifact identity. | Introduce artifact descriptors before broad renaming. |
| Flow API | Flow is created through `@flow` and `FlowFactory`. | `Flow` is an explicit composition object with `Flow.add(...)`. | Introduce new API alongside compatibility path. |
| Flow-local participation | No explicit `FlowNode`. | `Flow.add(...)` returns `FlowNode`. | Add `FlowNode` before moving policy and callbacks. |
| Trigger policy ownership | `PropagationPolicy` lives on `NodeDefinition`. | `TriggerPolicy` belongs to `FlowNode`. | Move ownership after `FlowNode` exists. |
| Context injection | No `NodeContext` exists. | `NodeContext[MemoryType, OutputType]` is injected and excluded from input ports. | Implement in signature parsing slice. |
| Local memory | No explicit `NodeMemory` public boundary exists. | `NodeMemory` belongs to `Run x NodeRuntime`. | Introduce after `NodeContext` exists. |
| Runtime ownership | Current `Node` owns execution and `Outpost`. | `NodeRuntime` owns run-local execution for a `FlowNode`. | Migrate after `Run` and `FlowNode` exist. |
| Repository name | `Depot` stores current Parcels. | `ArtifactRepository` stores artifact records. | Rename only after `ArtifactRecord` is real. |
| Outpost role | `Outpost` is a broad synchronization component. | It should become internal to `NodeRuntime` or an adapter. | Do not rename to `NodeMemory`; postpone until ownership is clear. |

## Open Architectural Questions

None currently.

When an open question is added, it must include:

1. the blocking slice;
2. the missing decision;
3. why implementation depends on it;
4. alternatives discovered;
5. affected tests;
6. affected classes.

## Next Recommended Slice

After Slice 1A (current) completes:

```text
Slice 1B -- NodeDescription / NodeDefinition + ArtifactDescriptor
(docs/refactor_priority_order.md, Priorities 2-3)
```

This is a recommendation, not an authorization. Starting Slice 1B still
requires a new explicit task (see the One-Slice Termination Rule in
`refactor_agent_protocol.md`).

## Refactor State Log

| Date | Change |
|---|---|
| 2026-09-12 | Baseline test safety net created: 24 passing regression tests and 15 expected target-architecture failures. |
| 2026-09-12 | `refactor_state.md` expanded into the live operational checkpoint for the refactor. |
| 2026-09-12 | Development environment verified with `uv`: `uv run pytest -q` reports 24 passed, 15 xfailed, 86% coverage; `uv run ruff check src tests` passes. |
| 2026-09-12 | `refactor_agent_protocol.md` added as the operational protocol for AI agents executing the refactor. |
| 2026-09-12 | Refactor documentation harness audited and restructured: `architectural_invariants.md` added to required reading; `refactor_priority_order.md`'s single "first implementation slice" split into Milestone 1 / Milestone 2 with lettered slices; authority order made explicit in `refactor_guide.md`. Baseline re-verified in this session: `uv run pytest -q -o addopts=''` reports 24 passed, 15 xfailed; `uv run ruff check src tests` passes. Coverage percentage not re-measured this session (sandbox could not write `.coverage` in the mounted working tree); this does not affect pass/fail counts. |
