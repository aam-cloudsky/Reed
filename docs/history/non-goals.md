# Reed Refactor — Non-Goals

This document defines explicit non-goals for the current Reed architectural refactor.

These constraints exist to prevent scope expansion during implementation.

Unless another architectural decision explicitly overrides this document, the refactor MUST NOT introduce the following changes.

## Distributed Execution

The current refactor does not introduce distributed execution.

Do not redesign Node, Flow, Run, Repository, Transport, or synchronization mechanisms around distributed workers, remote execution, clusters, or network-transparent nodes.

## Advanced Parallel Scheduling

Parallel execution is not part of the current architectural refactor.

The architecture may preserve boundaries that enable future parallelism, but the current work must not introduce a new scheduler or execution model merely to support it.

Stateful `NodeRuntime` firings must remain serialized: one state-aware `NodeRuntime` must not execute more than one firing at the same time.

## NodeContext Scope

`NodeContext` must remain a narrow capability boundary.

For the current refactor, it may expose only:

- `ctx.memory`;
- `ctx.last_output`.

It must not become:

- an `InputPort`;
- a service locator;
- a proxy to `Run`;
- a proxy to `Flow`;
- a proxy to `Repository`;
- a proxy to `Bus`;
- a proxy to `Outpost` or `NodeRuntime`.

## Complex Callback Semantics

`on_output` is observational.

Callbacks must not:

- control graph routing;
- determine propagation;
- modify commit semantics;
- replace `TriggerPolicy`;
- become part of dependency resolution.

Callback failure must not undo an already successful commit.

## TriggerPolicy Scope

`TriggerPolicy` must not become a scheduler, callback system, retry policy, or routing mechanism.

For the current refactor, `TriggerPolicy` only decides whether a `FlowNode` becomes eligible to execute after input artifact changes.

Keep this boundary explicit:

```text
TriggerPolicy != on_output
```

## Repository Exposure

Public node code must not directly depend on Reed's internal artifact repository.

`NodeContext` must not expose the repository as a general-purpose API.

## Execution Infrastructure Exposure

Do not expose internal execution machinery through the public node API merely because it is convenient during implementation.

In particular, do not add trace IDs, execution IDs, transport primitives, repository internals, or synchronization internals to `NodeContext` unless separately specified by an architectural decision.

## Multiple Registrations of the Same Node Definition

Do not introduce arbitrary multiple registrations of the same `NodeDefinition` within a `Flow` until node participation identity semantics are explicitly designed.

Do not invent identity rules as part of this refactor.

## Checkpoint / Restore

Persistent execution checkpoints, Run restoration, and recovery from serialized execution state are outside the scope of this refactor.

## Manual Topology Connection (`Flow.connect(...)`)

Early exploratory material (`architectural_decision.md`'s alternate example, and
`docs/roadmap.md`'s description of issue #4) shows a `flow.connect(source, target)`
step alongside `flow.add(...)`.

That exploratory shape is superseded. The accepted decision
(`flow_composition_implementation_basis.md`, `parcel_boundary_decision.md`) infers
topology from artifact-type dependencies between `Flow.add(...)` registrations.
Two nodes are connected because one produces the artifact type the other
consumes, not because `.connect(...)` was called.

Do not introduce `Flow.connect(...)` as a required composition step.

## Broad Renaming

Do not perform repository-wide renaming merely for vocabulary consistency.

Renaming must follow the architectural migration order.

In particular:

> First make the boundary real. Then rename the boundary.

Names such as `Depot`, `Outpost`, and `Parcel` must only be replaced when the corresponding target abstraction has become architecturally explicit.

## ArtifactRecord Is Not A Blind Parcel Rename

Do not replace every `Parcel` occurrence with `Artifact`.

The target distinction is:

```text
Domain type == artifact semantic identity
ArtifactRecord == Reed-managed versioned record
```

`Artifact` may be a concept, descriptor, or identity.

The internal wrapper must remain distinct from the user-facing domain value.

## Outpost Is Not NodeMemory

Do not rename `Outpost` to `NodeMemory` or `LocalState`.

`Outpost` is currently a broad internal synchronization component.

`NodeMemory` must be introduced as a separate concept owned by `NodeRuntime`.

`Outpost` may later be absorbed into `NodeRuntime` or renamed to an internal adapter, but that requires a separate implementation step.

## Compatibility Removal (superseded)

This non-goal applied only to the first implementation pass (Milestones
1-2): do not remove the decorator-based API before the new architecture
existed and was proven. That constraint has since been explicitly and
deliberately superseded: once the new architecture (Flow/Run/NodeContext/
TriggerPolicy) passed its acceptance example, its end-to-end tests, and
completed Milestone 3, Reed's owner made an explicit decision that the
previous decorator/Parcel/`bind(...)`/callable-Flow programming model
would not be maintained as a compatibility layer, and it has been
removed accordingly (see docs/refactor_state.md's legacy-removal entries
for that decision and its execution). This section is retained as a
historical record of the earlier constraint, not as a statement of
current policy: the decorator-based API, `Parcel`, and the legacy
callable-Flow execution path no longer exist in this codebase.

## Target Tests

Do not make target-architecture tests pass by weakening their assertions.

Target tests marked as expected failures describe documented future behavior.

They should pass only when the corresponding architecture is implemented.

## Unrelated Cleanup

Do not perform unrelated cleanup while touching files.

Avoid:

- unrelated formatting changes;
- opportunistic abstractions;
- unrelated API redesign;
- broad module reorganizations;
- speculative optimizations;
- dependency upgrades unrelated to the refactor.

A file being touched by the refactor is not permission to redesign everything inside it.

## New Architectural Decisions

Implementation must not silently introduce architectural decisions.

If progress requires a decision not covered by the existing architectural documents:

**STOP and report the missing decision.**

Do not choose an architecture merely to continue implementation.

---

The purpose of these non-goals is not to prevent future evolution of Reed.

They define what this refactor is **not responsible for solving now**.

## Speculative Abstractions

Do not introduce an abstraction solely because a future architecture
might need it.

New abstractions must correspond to either:

1. a boundary explicitly established by an architectural decision; or
2. a concrete requirement of the current slice.

Do not introduce factories, managers, protocols, strategies, adapters,
or generic helper layers for hypothetical future requirements.