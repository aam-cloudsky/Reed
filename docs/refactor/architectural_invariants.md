# Reed Architectural Invariants

These invariants must remain true throughout the refactor.

They summarize established architectural decisions.
They do not introduce new architecture.

Numbering is stable and append-only: existing SliceContracts reference invariants by
number (`required_invariants: [...]`), so an existing item's number is never reused for
a different meaning, even when the item's wording is updated for a rename (e.g. `Run`
became `Session` in issue #22; the invariant numbers did not change).

## Lifecycle

1. `NodeDefinition != FlowNode`
2. `FlowNode != NodeSession` (was `NodeRuntime`, renamed in issue #22)
3. `NodeSession != NodeExecution`
4. `Flow != Session` (was `Run`, renamed in issue #22)
5. `NodeDefinition` owns no Session-specific state.
6. `Flow` owns no Session-specific execution state.

## Artifact Model

7. `Domain Value != ArtifactRecord`
8. Domain type defines artifact semantic identity.
9. Artifact identity != artifact version.
10. One artifact type has one *declared* producer per Flow (`DuplicateArtifactProducerError`).
    This governs `Flow.add(...)`-registered `FlowNode`s only — see invariant 30 for
    `Session.feed()`'s deliberate exemption.
11. A Node cannot consume and produce the same artifact type.

## Context and State

12. `NodeContext != InputPort`
13. `NodeContext` exposes only `memory` and `last_output`.
14. `NodeMemory` belongs to `Session × NodeSession × InstanceKey` (updated at
    Slice MI-F, docs/refactor/multi_instance_execution_plan.md, R4 decision --
    per-instance is the resolved scope; the pre-multi-instance meaning, `Session
    × NodeSession` alone, is preserved exactly under `InstanceKey.singleton()`,
    so this is a wording update, not a behavior change, for every existing
    single-instance flow).
15. `NodeMemory != last_output`.
16. Different Sessions must not share NodeMemory.
17. Stateful NodeSession firings are serialized.

## Execution

18. Dirty state does not imply immediate execution.
19. `TriggerPolicy` decides execution eligibility.
20. `TriggerPolicy != on_output`.
21. `on_output` executes only after successful commit.
22. `on_output` receives domain values.
23. `on_output` failure does not undo a committed artifact.

## Public Boundary

24. User Nodes consume and produce domain values.
25. Reed owns wrapping and unwrapping of internal artifact records.
26. Internal runtime infrastructure must not leak through `NodeContext`.

## Versioning, Origin, and Feed/Push/Snapshot (issue #22)

27. `ArtifactRecord` is mutated in place on each commit (`ArtifactRecord.advance()`);
    the same object persists in the repository for a type's whole lifetime, it is not
    replaced by a new object per commit. (This reverses the pre-#22 invariant that a
    committed `ArtifactRecord` is never mutated after the fact; see
    `docs/refactor/session_snapshot_decision.md` §7 for why this was verified safe.)
28. An artifact's next version is always derived from that type's *current*
    `ArtifactRecord` in the repository (`.next()` if one exists, else
    `ArtifactVersion.initial()`) — never from a private, per-node or per-type running
    counter. This applies uniformly to both a node firing and `Session.feed()`.
29. `ArtifactOrigin` has exactly two values, `NODE` and `EXTERNAL`. Every commit path
    sets it explicitly and there is no default; a committed record's origin is never
    unset or a third "pending" value.
30. `Session.feed()` does not participate in the declared `Flow`/`ArtifactDependencyGraph`
    and is exempt from invariant 10: it may commit a value for a domain type that
    already has a declared producer node, without raising
    `DuplicateArtifactProducerError`.
31. `Session.feed()` never evaluates eligibility or fires a node. Only `Session.push()`
    does.
32. `Session.push()` returns `None`.
33. `Session.snapshot()` returns the full current repository state as plain domain
    values only (never `ArtifactRecord`), reflecting the moment it is called; it
    retains no history of earlier snapshots or pushes.
