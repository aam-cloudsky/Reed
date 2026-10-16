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
11. A Node cannot consume and produce the same artifact type, except through a
    `Sampled` input (`Annotated[T, Sampled]`, issue #29). That input is a unit
    delay: it reads the value committed before the firing (the node's previous
    output, or a later `feed()`) and never triggers the node. A triggering
    self-input is rejected at `Flow.add(...)`.

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

## Superstep Execution (issue #31)

34. A `(FlowNode, instance)` pair fires at most once per `Session.push()`. An arrival at
    a node that already ran in the current `push()` is recorded and takes effect in the
    next `push()`. Along a feedback loop, this is an implicit unit delay.
35. A `FlowNode` runs only after every producer of its inputs (triggering, sampled or
    collective) that may still fire in the current `push()` has fired or has been found
    not eligible. When no node is ready, a loop that waits on nothing outside itself is
    released at one node, chosen by: waiting on the loop only through `Sampled` inputs,
    then first reached by the change front, then registration order.
36. Workers of one superstep read the state committed before the superstep. Their
    outputs are committed together at the barrier that closes it. If any worker raises,
    nothing from that superstep is committed (values, versions, `last_output`,
    provenance), and the exception propagates.
37. Iteration order during a `push()` is a function of the `Flow`'s composition and the
    inputs: registration order for nodes, fan-out order for instances. It never depends
    on `id()`-based hashing.
38. `Session.push()` calls on one `Session` are serialized across threads; a call from
    inside a running `push()` on the same thread raises `RuntimeError`.
39. A `Collective[T]` input is triggering. Its arrival is the set of
    instances of `T` as a whole: everything committed at one barrier, in one
    `feed_instances()` call, or removed by `remove_instance()` counts as one change.
