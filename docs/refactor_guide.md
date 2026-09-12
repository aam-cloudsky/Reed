# Reed Architectural Refactor — Implementation Guide

## Purpose

This document defines the execution protocol for the Reed architectural refactor.

The architectural design has already been established.

The objective of the refactor is to migrate the current implementation toward the documented target architecture while preserving existing valid behavior and avoiding undocumented architectural decisions.

This is an **implementation task**, not an architecture redesign task.

---

# 1. Source of Truth

Before implementing any refactor slice, read the relevant architectural documents.

The architectural decision documents define **what Reed should become**.

The implementation assessment and priority documents define **how the migration should proceed**.

`docs/non-goals.md` defines what must **not** be introduced during this refactor.

When implementation convenience conflicts with an architectural decision, the architectural decision wins.

When the current implementation conflicts with the documented target architecture, migrate toward the documented architecture rather than preserving the accidental implementation structure.

When the documents do not determine the answer, do not invent one.

Stop and report the ambiguity.

## Authority Order

When sources disagree, resolve the disagreement by rank, not by convenience.
From highest to lowest authority:

1. **Accepted architectural decision documents** -- `architectural_decision.md`,
   `parcel_boundary_decision.md`, `node_context_decision.md`,
   `flow_composition_implementation_basis.md`. These define what Reed becomes.
2. **`architectural_invariants.md`** -- a compact restatement of the decisions
   above. It carries the same authority as the decision it restates. If an
   invariant appears to say something a decision document does not support,
   treat this as a documentation bug in the invariant, not a license to
   reinterpret the decision.
3. **`non-goals.md`** -- explicit scope boundaries derived from the decisions
   above. Non-goals may narrow how a decision is implemented in this refactor;
   they cannot justify violating a decision.
4. **`refactor_guide.md`** (this document) -- the implementation policy for
   migrating toward the decisions above. It enacts them; it does not add
   architecture.
5. **`refactor_priority_order.md` and `implementation_refactor_assessment.md`**
   -- advisory planning and code-mapping material. Useful for sequencing and
   rationale, but non-binding where they conflict with 1-4.
6. **Target architecture contract tests**
   (`tests/test_target_architecture_contract.py`) -- codify the intended
   future API and behavior. Authoritative as a concrete example of the decided
   architecture, but subordinate to it: a target test that appears to
   contradict an architectural decision is a drift to report, not a rule to
   follow silently.
7. **Regression tests** (`tests/test_current_regression_*.py`) -- protect
   current valid behavior. They may be superseded by an explicit architectural
   decision, but never by implementation convenience.
8. **Legacy/current implementation** (`src/`) -- the lowest authority. It is
   the migration's starting point, not a constraint on the target.

A lower-ranked source never silently overrides a higher-ranked one. If two
sources at different ranks appear to disagree, treat the higher rank as
correct and **report the disagreement** rather than resolving it quietly. If
two sources at the *same* rank disagree -- for example two accepted decision
documents -- this is a genuine architectural conflict: stop and report it; do
not choose between them.

---

# 2. Fundamental Rule

> Implement the decided architecture. Do not redesign it.

The refactor must not silently introduce architectural decisions.

If implementation requires choosing between alternatives that materially affect:

- public API;
- ownership;
- lifecycle;
- identity;
- state scope;
- execution semantics;
- artifact semantics;
- dependency semantics;
- trigger semantics;
- concurrency semantics;

and the answer is not established by the architectural documents:

**STOP.**

Report:

1. the decision that is missing;
2. why implementation depends on it;
3. the alternatives discovered;
4. the affected components.

Do not choose an alternative merely to continue working.

---

# 3. Change Classification

Every production change must be classified before implementation.

Use one of the following categories:

- signature parsing;
- artifact boundary;
- context injection;
- flow composition;
- run and execution ownership;
- repository boundary;
- vocabulary migration;
- compatibility preservation.

If a proposed production change does not fit one of these categories, stop and explain why it belongs in this refactor.

This rule prevents unrelated cleanup from entering the refactor under the appearance of architectural work.

---

# 4. Architectural Direction

The target architecture follows the explicit lifecycle:

`NodeDefinition -> Flow Composition -> Run Context -> NodeRuntime -> NodeExecution`

Maintain the distinction between these concepts.

In particular:

- `NodeDefinition` describes reusable computation.
- `Flow` describes composition and topology.
- `FlowNode` represents participation of a node definition inside a Flow.
- `Run` owns execution-specific state.
- `NodeRuntime` represents the runtime participation of a node inside a Run.
- `NodeExecution` represents an individual firing/execution.

Do not collapse these concepts for implementation convenience.

---

# 5. State Boundaries

Maintain explicit ownership boundaries.

Shared state belongs to the `Run`.

Node-local persistent state belongs to:

`Run × NodeRuntime`

Node memory must not accidentally become:

- global state;
- Flow state;
- NodeDefinition state;
- module state.

Different Runs must remain isolated.

`last_output` is not Node memory.

Keep these concepts separate.

---

# 6. Artifact Boundary

User node functions operate on domain values.

Reed internally manages execution artifacts.

Therefore:

`Domain Value != ArtifactRecord`

The public node API should receive domain objects rather than internal artifact containers.

Reed is responsible for wrapping and unwrapping values at the execution boundary.

Maintain the distinction between:

`Artifact Value != Artifact Version != Artifact Provenance`

Artifact identity must also remain distinct from artifact version.

Do not expose internal artifact machinery merely to simplify implementation.

---

# 7. Dependency and Producer Semantics

Artifact types represent semantic dataflow identities.

Each artifact has a unique producer within the relevant Flow.

Invalid graph structures must be detected explicitly.

In particular, preserve validation around:

- duplicate producers;
- incompatible artifact relationships;
- invalid self-flow;
- incompatible `NodeContext` typing.

Do not weaken validation to make migration easier.

---

# 8. Trigger Semantics

Dirty state does not mean immediate execution.

Maintain the distinction:

`State Change -> Dirty/Validity Information -> TriggerPolicy -> Execution Decision`

`TriggerPolicy` determines whether execution should occur.

Do not embed trigger decisions implicitly into artifact storage, callbacks, or unrelated synchronization mechanisms.

---

# 9. NodeContext

`NodeContext` is an explicitly injected execution context.

It is not an input artifact.

It must therefore be excluded from normal input-port discovery.

Its intended public responsibilities are intentionally narrow:

- `ctx.memory`
- `ctx.last_output`

Do not turn `NodeContext` into a service locator.

Do not expose arbitrary Reed internals through it.

Typing rules documented for `NodeContext` must be enforced.

`NodeContext[MemoryType, OutputType]` must be validated against the function return type.

This is valid:

```text
ctx: NodeContext[Memory, Estimate]
return: Estimate
```

This must fail before execution:

```text
ctx: NodeContext[Memory, Other]
return: Estimate
```

---

# 10. on_output

`on_output` is observational.

The intended ordering is:

`Node execution -> output validation -> artifact commit -> on_output`

Therefore:

- callbacks observe committed output;
- callbacks receive the domain-level output;
- callbacks do not control propagation;
- callbacks do not determine routing;
- callback failure does not roll back a successful artifact commit.

Keep commit semantics and callback semantics separate.

---

# 11. Tests Are the Refactor Guardrails

The repository contains two important categories of tests.

## Regression tests

These describe current valid behavior that must not regress unintentionally.

They should remain green throughout the refactor unless an architectural decision explicitly supersedes that behavior.

## Target architecture contract tests

These describe the intended architecture.

Initially, some are expected to fail or be marked as expected failures because the corresponding architecture has not yet been implemented.

During the refactor, these tests should progressively become passing tests.

When implementing a target behavior, remove the corresponding `xfail` only after the behavior is implemented.

Do not convert `xfail(strict=True)` into a weaker skip.

Do not make tests pass by weakening their assertions.

Do not delete tests because implementation is difficult.

Do not modify tests merely to accommodate accidental implementation behavior.

If a test conflicts with an architectural document, report the conflict.

The architectural document is the source of truth.

Before changing production code, identify which test should change from expected failure to passing, or which regression test protects the change.

If no test corresponds to the slice, add or adjust the test first.

---

# 12. Incremental Refactor Strategy

Do not attempt to rewrite Reed in one operation.

Implement the migration through small architectural slices.

The authoritative dependency order, broken into concrete milestones and
slices, lives in `docs/refactor_priority_order.md`. Do not restate or
re-derive that order here -- a second copy of the sequence is a second place
it can go stale. Read it before planning a slice.

Respect dependency ordering.

Do not rename abstractions before their target architectural boundaries exist.

> First make the boundary real. Then rename the boundary.

A rename is allowed only when:

- the target concept already exists in code;
- tests protect the old behavior;
- tests protect the new architectural boundary;
- the old name can be kept as a compatibility alias if needed.

---

# 13. Slice Protocol

For every implementation slice:

## Before changing production code

1. Read the relevant architectural decisions.
2. Inspect the affected implementation.
3. Inspect the relevant regression tests.
4. Inspect the relevant target architecture tests.
5. Identify the smallest coherent implementation change.
6. Confirm that no undocumented architectural decision is required.

Only then modify production code.

## After implementation

Run:

1. relevant focused tests;
2. target architecture tests affected by the slice;
3. complete test suite;
4. configured static analysis;
5. configured type checks.

Do not proceed to another architectural slice while the current slice has unexplained failures.

---

# 14. Commit Discipline

Each commit should represent one coherent architectural step.

Avoid commits such as:

`refactor architecture`

Prefer commits representing concrete transitions, for example:

`add NodeContext signature parsing`

`introduce FlowNode composition metadata`

`add domain value artifact boundary`

`introduce TriggerPolicy`

`add Flow.add composition API`

Before committing:

- tests relevant to the slice must pass;
- existing regression tests must pass;
- failures must be understood;
- the diff must contain no unrelated changes.

Do not bundle several independent architectural migrations into one commit merely because they were implemented in the same session.

---

# 15. Scope Control

Do not expand scope.

While implementing a slice, avoid:

- unrelated cleanup;
- speculative abstractions;
- premature optimization;
- unrelated renaming;
- formatting unrelated files;
- redesigning neighboring systems;
- dependency upgrades without necessity;
- new features unrelated to the architecture migration.

Follow `docs/non-goals.md`.

A discovered improvement may be reported as future work rather than implemented.

---

# 16. Compatibility

Preserve existing behavior when it does not conflict with the target architecture.

Where temporary compatibility layers are appropriate, prefer incremental migration over unnecessary breakage.

Do not remove the decorator-based API in an early slice.

The new `Flow.add(...)` API should be introduced alongside the old API until compatibility removal is explicitly planned.

However, do not preserve accidental legacy behavior when it directly contradicts an explicit architectural decision.

If compatibility requires a significant architectural compromise, report it instead of silently implementing it.

---

# 17. Expected Checks

Expected checks:

```bash
pytest
pytest -q -o addopts=''
ruff check src tests
```

If a configured tool is unavailable, report that explicitly instead of silently skipping it.

If the configured test command fails because an optional test dependency is missing, run the closest equivalent command and report the limitation.

---

# 18. Git Safety

Work only on the designated refactor branch.

Do not:

- force push;
- rewrite unrelated history;
- use destructive Git operations unnecessarily;
- delete tests to obtain a green suite;
- discard user changes;
- modify unrelated work.

Create small checkpoints through commits.

The repository should always have a recent known-good state that can be restored.

---

# 19. Stop Conditions

Stop implementation and report instead of continuing when:

- a type relation is unclear;
- ownership between `Flow`, `Run`, `FlowNode`, `NodeRuntime`, or `NodeExecution` is unclear;
- callback ordering is unclear;
- a rename requires changing behavior;
- compatibility requires keeping two APIs alive and the bridge is unclear;
- a target test contradicts an architectural document;
- an architectural decision is missing;
- architectural documents contradict each other;
- a required change significantly expands scope;
- regression behavior and target architecture conflict unexpectedly;
- tests reveal behavior that cannot be explained;
- implementation requires changing an explicitly documented invariant;
- a slice unexpectedly requires redesigning a distant subsystem;
- the test suite develops unexplained regressions.

Stopping is preferable to inventing architecture.

---

# 20. Definition of Done For A Refactor Slice

A slice is done only when:

- the intended target-architecture test now passes;
- no regression test was weakened;
- no unrelated production behavior changed;
- no undocumented architectural decision was introduced;
- relevant focused tests pass;
- the full test suite passes;
- configured static and type checks pass, or their absence is reported;
- any remaining expected failures still describe unimplemented target behavior.

Do not mark a slice done merely because the local code appears to work manually.

---

# 21. End-of-Slice Report

After every significant slice, report:

## Implemented

What changed.

## Architectural contract satisfied

Which documented architectural behavior is now implemented.

## Tests

Which tests became green and the complete test-suite status.

## Compatibility

Any observable compatibility impact.

## Remaining expected failures

Which target architecture tests remain unimplemented.

## Architectural questions

Any ambiguity or decision requiring human input.

## Next recommended slice

The smallest coherent next step according to the documented migration order.

---

# 22. Definition of Success

The refactor is complete when:

- the documented architectural boundaries exist in implementation;
- target architecture contract tests pass;
- valid regression tests remain green;
- public APIs follow the documented architecture;
- runtime ownership boundaries are explicit;
- domain values are separated from internal artifact representation;
- Flow composition is separated from Run execution state;
- NodeDefinition, FlowNode, NodeRuntime, and NodeExecution have distinct responsibilities;
- no undocumented architectural decisions were introduced merely to finish the migration.

The goal is not to produce the largest possible refactor.

The goal is to reach the documented architecture through a sequence of **small, verifiable, reversible changes**.


## Test Integrity

Tests are correctness oracles, not implementation specifications.

Do not:

- hard-code behavior specifically for known tests;
- introduce test-specific branches;
- special-case test fixtures;
- bypass architectural boundaries merely to satisfy assertions;
- modify target tests to match the implementation.

Implement the architectural rule described by the ADRs.

A passing test suite is necessary but not sufficient for
architectural correctness.