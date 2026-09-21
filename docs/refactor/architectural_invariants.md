# Reed Architectural Invariants

These invariants must remain true throughout the refactor.

They summarize established architectural decisions.
They do not introduce new architecture.

## Lifecycle

1. `NodeDefinition != FlowNode`
2. `FlowNode != NodeRuntime`
3. `NodeRuntime != NodeExecution`
4. `Flow != Run`
5. `NodeDefinition` owns no Run-specific state.
6. `Flow` owns no Run-specific execution state.

## Artifact Model

7. `Domain Value != ArtifactRecord`
8. Domain type defines artifact semantic identity.
9. Artifact identity != artifact version.
10. One artifact type has one producer per Flow.
11. A Node cannot consume and produce the same artifact type.

## Context and State

12. `NodeContext != InputPort`
13. `NodeContext` exposes only `memory` and `last_output`.
14. `NodeMemory` belongs to `Run × NodeRuntime`.
15. `NodeMemory != last_output`.
16. Different Runs must not share NodeMemory.
17. Stateful NodeRuntime firings are serialized.

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