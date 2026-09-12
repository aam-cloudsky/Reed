# Refactor Agent Protocol

This document defines how an AI agent must execute the Reed architectural refactor.

It is an operational protocol for the refactoring agent.

It does not introduce new architecture.

The agent must use the existing architectural documents as the source of truth.



## Refactor Navigation Map

Do not load every refactor document indiscriminately.

Use this document as the operational entry point and load only the
architectural context required by the current slice.

```text
refactor_agent_protocol.md
        │
        ├── What is the current state?
        │       └── refactor_state.md
        │
        ├── What are the global implementation rules?
        │       └── refactor_guide.md
        │
        ├── What must always remain true?
        │       └── architectural_invariants.md
        │
        ├── What must NOT be changed?
        │       └── non-goals.md
        │
        ├── What should be implemented next?
        │       └── refactor_priority_order.md
        │
        └── What architectural decision governs this slice?
                │
                ├── lifecycle / ownership
                │       └── architectural_decision.md
                │
                ├── domain values / artifacts / records
                │       └── parcel_boundary_decision.md
                │
                ├── context / memory / last output
                │       └── node_context_decision.md
                │
                ├── Flow.add / FlowNode / TriggerPolicy / on_output
                │       └── flow_composition_implementation_basis.md
                │
                └── migration mechanics / current implementation
                        └── implementation_refactor_assessment.md
```

## Context Loading Rule

Always read:

1. refactor_agent_protocol.md;
2. refactor_state.md;
3. refactor_guide.md;
4. architectural_invariants.md;
5. non-goals.md.

Then read only the architectural documents relevant to the current slice.

Use refactor_priority_order.md to determine dependencies and ordering.

Use implementation_refactor_assessment.md when understanding how the
current implementation maps to the target architecture.

Do not preload unrelated architectural documents merely because they exist.

The objective is:

```text
minimum sufficient context
not
maximum available context
```

## Slice-To-Documentation Map

A router, not a summary. Read the cell's target, not this table, for the
actual rule. Invariant numbers refer to `architectural_invariants.md`.

| Concept | Primary source | Supporting source | Key invariants | Likely test area |
|---|---|---|---|---|
| `NodeDescriptionBuilder` | `parcel_boundary_decision.md`, `node_context_decision.md` | `flow_composition_implementation_basis.md` (Validation Rules) | 12, 24-26 | `test_current_regression_node_description.py`; target: signature/context/self-flow tests |
| `NodeDescription` / `NodeDefinition` | `architectural_decision.md` (Node Definition) | `implementation_refactor_assessment.md` #2 | 1, 5 | `test_current_regression_node_description.py` |
| `ArtifactDescriptor` | `parcel_boundary_decision.md` | `implementation_refactor_assessment.md` #11 | 7-11 | target: duplicate-producer, self-flow, parallel-branching tests |
| `NodeContext` | `node_context_decision.md` | `flow_composition_implementation_basis.md` (NodeContext Boundary) | 12-17 | target: `test_node_context_*` |
| `NodeMemory` | `node_context_decision.md` (Memory) | `non-goals.md` (Outpost Is Not NodeMemory) | 14-17 | target: `test_run_instances_isolate_node_memory` |
| `ArtifactRecord` | `parcel_boundary_decision.md` (Parcel As Internal Envelope) | `non-goals.md` (ArtifactRecord Is Not A Blind Parcel Rename) | 7-9 | `test_current_regression_artifacts_repository.py` |
| `ArtifactProvenance` / `ArtifactVersion` | `architecture.md` (Shared-State Synchronization) | `parcel_boundary_decision.md` | 7-9 | `test_current_regression_artifacts_repository.py` (version/provenance tests) |
| `DependencyRegistry` | `parcel_boundary_decision.md` (Unique Producer Responsibility) | `architecture.md` (Dependency Management) | 10-11 | `test_current_regression_artifacts_repository.py`; target: duplicate-producer test |
| `FlowNode` | `flow_composition_implementation_basis.md` (FlowNode) | `architectural_decision.md` (Flow-Local Node Reference) | 1-3 | target: `test_flow_add_registers_callable_and_returns_flownode` |
| `TriggerPolicy` | `flow_composition_implementation_basis.md` (TriggerPolicy) | `architecture.md` (Incremental Propagation) | 18-20 | target: `test_flow_add_uses_keyword_only_trigger_policy_and_on_output`, `test_stateful_node_runtime_firings_are_serialized` |
| `Flow.add(...)` | `flow_composition_implementation_basis.md` (`Flow.add(...)`) | `architectural_decision.md` (Target API Shape) | 1, 3 | target: `test_flow_add_*` |
| `Flow` | `architectural_decision.md` (Flow Composition) | `implementation_refactor_assessment.md` #1 | 4, 6 | `test_current_regression_flow_runtime.py` |
| `Run` | `architectural_decision.md` (Run) | `implementation_refactor_assessment.md` #1 | 4-6, 16 | target: `test_run_instances_isolate_node_memory` |
| `NodeRuntime` | `architectural_decision.md` (Node Runtime) | `implementation_refactor_assessment.md` #6-7 | 2-3, 14, 16-17 | target: memory/serialization tests |
| `NodeExecution` | `architectural_decision.md` (Node Execution) | `flow_composition_implementation_basis.md` (Callback Timing/Failure) | 21-23 | target: `test_on_output_*`, `test_callback_failure_*` |
| `ArtifactRepository` | `architecture.md` (Single Source of Truth) | `implementation_refactor_assessment.md` #9 | 7-9 | target tests using `run.repository.get(...)` |
| Outpost migration | `non-goals.md` (Outpost Is Not NodeMemory) | `implementation_refactor_assessment.md` #7 | 14 | none yet (internal) |
| Public API compatibility | `refactor_state.md` (Known Compatibility Layer) | `non-goals.md` (Compatibility Removal) | -- | `tests/test_package.py`, `tests/test_current_regression_flow_runtime.py` |

## Blast-Radius Control

Every slice plan (see the template below) must declare its expected change
surface before production code is touched. After implementation, compare the
actual `git diff` against that declaration.

```text
unexpected change != automatically wrong
unexpected change -> requires explanation before proceeding
```

A materially larger-than-expected diff must be explained, and reviewed,
before another slice begins. Stop rather than continuing to the next slice on
an unexplained diff.

## Core Rule

The agent must be investigative before being constructive.

Do not start by editing production code.

Every refactor step must begin with:

```text
read -> inspect -> research -> plan -> implement -> verify -> report
```

The agent must work in small slices.

One slice means one coherent architectural step with a clear definition of done.

## Required Reading Before Any Production Change

Before implementing any slice, the agent must read:

1. `docs/refactor_state.md`;
2. `docs/refactor_guide.md`;
3. `docs/architectural_invariants.md`;
4. `docs/non-goals.md`;
5. `docs/refactor_priority_order.md`;
6. the architectural decision documents directly relevant to the slice.

The relevant architectural documents may include:

1. `docs/architectural_decision.md`;
2. `docs/parcel_boundary_decision.md`;
3. `docs/node_context_decision.md`;
4. `docs/flow_composition_implementation_basis.md`;
5. `docs/implementation_refactor_assessment.md`.

The agent must not rely on memory alone when implementing a slice.

## Required Inspection Before Any Production Change

Before implementing any slice, the agent must inspect:

1. the affected production files;
2. the regression tests that protect current behavior;
3. the target architecture tests that describe the intended behavior;
4. the current `git status`;
5. the current branch;
6. the latest state recorded in `docs/refactor_state.md`.

The agent must explicitly identify:

1. which current behavior must remain valid;
2. which target behavior should become implemented;
3. which tests are expected to move from expected failure to passing;
4. which files are in scope;
5. which files are out of scope.

## External Research Rule

External research is not mandatory for every slice.

Research should be performed when:

1. the implementation depends on a Python mechanism whose semantics
   need confirmation;
2. the architectural documents explicitly reference an external pattern
   relevant to the slice;
3. the current implementation exposes a technical uncertainty;
4. implementation alternatives have materially different correctness
   or compatibility consequences.

Do not perform external research merely to search for a "better architecture".

The architecture is already decided.

Research exists to clarify implementation mechanics, not reopen design.

When research is performed, prefer sources in this order:

1. official documentation;
2. official source repositories;
3. mature framework implementations;
4. scientific literature already referenced by Reed (see
   `implementation_refactor_assessment.md`).




## Slice Plan Requirement

The agent must write a slice plan before modifying production code.

The plan must be short, specific, and limited to the current slice.

Use this template:

```markdown
## Slice Plan

### Slice name

### Architectural source

### Current implementation inspected

### Regression tests protecting current behavior

### Target tests expected to move

### External references checked

### Scope

### Non-scope

### Expected Change Surface

Production files expected to change:

Test files expected to change:

Documentation expected to change:

Files explicitly outside the expected change surface:

Target contracts affected:

### Risks

### Definition of done

### Implementation steps
```

The plan is part of the work.

If the plan reveals that the slice is too large, the agent must split it before editing production code.

## Slice Scope Rule

The agent must implement only the current slice.

The agent must not combine independent architectural migrations in one slice.

Examples of separate slices:

1. signature parsing;
2. artifact descriptors;
3. `NodeContext`;
4. `NodeMemory`;
5. `ArtifactRecord`;
6. `FlowNode`;
7. `TriggerPolicy`;
8. `Flow.add(...)`;
9. `Run`;
10. `NodeRuntime`;
11. `NodeExecution`;
12. repository naming;
13. compatibility cleanup.

If a change is useful but outside the slice, report it as future work.

Do not implement it opportunistically.

## Non-Goals Enforcement

The agent must follow `docs/non-goals.md`.

In particular, do not:

1. introduce distributed execution;
2. introduce advanced parallel scheduling;
3. expose repository, bus, run, flow, outpost, or runtime internals through `NodeContext`;
4. turn `on_output` into a graph control mechanism;
5. turn `TriggerPolicy` into a scheduler or callback system;
6. rename `Parcel` blindly to `Artifact`;
7. rename `Outpost` to `NodeMemory`;
8. remove the decorator-based API in the first implementation pass;
9. weaken target architecture tests.

## Test Discipline

Tests are the guardrails for the refactor.

Before changing production code, the agent must identify one of the following:

1. the regression test that protects the behavior being preserved;
2. the target architecture test that should move from expected failure to passing;
3. the missing test that must be added before implementation.

The agent must not make a test pass by weakening its assertion.

The agent must not convert `xfail(strict=True)` into a weaker skip.

The agent must remove `xfail` only when the corresponding behavior is implemented.

The agent must not delete regression tests unless an explicit architectural decision supersedes the behavior and the deletion is reported.

## Required Checks

Use `uv` for project commands.

The expected setup command is:

```bash
uv sync --extra dev
```

The expected verification commands are:

```bash
uv run pytest -q
uv run ruff check src tests
```

For focused checks, use:

```bash
uv run pytest -q <focused-test-path-or-node>
```

Current verified baseline:

```text
uv run pytest -q
24 passed, 15 xfailed
coverage: 86%

uv run ruff check src tests
All checks passed
```

If a configured tool is unavailable, the agent must report it explicitly.

Do not silently skip checks.

## Production Code Rule

The agent may edit production code only after:

1. reading the required documents;
2. inspecting the affected implementation;
3. inspecting relevant tests;
4. checking external references when design patterns are involved;
5. writing the slice plan;
6. confirming that no missing architectural decision blocks the slice.

The agent must not refactor production code merely because a better structure seems possible.

Every production change must be tied to:

1. an architectural document;
2. a test;
3. a slice plan.

## Rename Rule

Do not start with broad renaming.

Use the rule:

```text
First make the boundary real.
Then rename the boundary.
```

A rename is allowed only when:

1. the target concept already exists in code;
2. regression tests protect the old valid behavior;
3. target tests protect the new architectural boundary;
4. the compatibility impact is understood;
5. a compatibility alias can be kept if needed.

## Stop Conditions

The agent must stop and report when:

1. the architecture documents do not answer a required implementation decision;
2. two documents conflict;
3. a type relation is unclear;
4. ownership between `Flow`, `Run`, `FlowNode`, `NodeRuntime`, or `NodeExecution` is unclear;
5. callback ordering is unclear;
6. compatibility requires a bridge whose semantics are unclear;
7. a target test contradicts an architectural document;
8. a slice requires redesigning a distant subsystem;
9. a production change would expand beyond the current slice;
10. checks fail for a reason the agent cannot explain.

When two documents conflict, `refactor_guide.md`'s Authority Order section
says which one prevails for the purpose of continuing work -- but prevailing
does not mean the conflict is resolved. Report it either way.

Stopping is correct behavior in these cases.

Do not invent architecture to keep moving.

## Reporting Requirement

After every slice, the agent must report:

1. what changed;
2. which architectural decision was implemented;
3. which files changed;
4. which tests were run;
5. which tests passed;
6. which target tests moved from expected failure to passing;
7. which expected failures remain;
8. whether compatibility changed;
9. whether static checks passed;
10. whether `docs/refactor_state.md` was updated;
11. any ambiguity or future work.

The report must distinguish:

```text
existing behavior preserved
target behavior implemented
target behavior still pending
```

## Refactor State Update

After a slice, the agent must update `docs/refactor_state.md` when:

1. target tests move from expected failure to passing;
2. the current slice changes;
3. a slice is completed;
4. a new architectural question is discovered;
5. the baseline changes;
6. compatibility status changes;
7. a known conflict is resolved or newly discovered.

The state file is the operational checkpoint for the next agent.

Do not leave it stale after meaningful progress.

## Agent Mindset

The agent should behave like a careful senior engineer.

The goal is not to produce a large diff.

The goal is to move Reed toward the documented architecture through small, verified steps.

The correct behavior is:

```text
understand first
plan narrowly
change carefully
verify completely
report honestly
```

## Test Integrity Rule

Tests are verification oracles, not implementation recipes.

Never introduce:

- test-specific branches;
- hard-coded fixture behavior;
- special cases whose only purpose is satisfying known assertions;
- architectural shortcuts merely because the visible tests pass.

Implement the architectural rule, not the observed test case.

Passing tests are necessary but not sufficient evidence of correctness.

## One-Slice Termination Rule

Completing one slice does not authorize starting the next slice.

After verification, state update, and reporting, stop.

The next slice requires a new explicit task or instruction.