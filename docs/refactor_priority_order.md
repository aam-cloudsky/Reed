# Refactor Priority Order

This document defines the recommended order for refactoring Reed classes from the most blocking concepts to the least blocking ones.

It should be read together with:

1. `architectural_decision.md`;
2. `parcel_boundary_decision.md`;
3. `node_context_decision.md`;
4. `flow_composition_implementation_basis.md`;
5. `implementation_refactor_assessment.md`;
6. `architectural_invariants.md`;
7. `non-goals.md`.

The previous public API order is not enough for implementation planning.

For implementation, Reed should start with the concepts that affect every other layer:

```text
typed signature -> artifact descriptors -> flow graph -> flow-local node -> run-local execution
```

The guiding principle is:

```text
Refactor the most blocking semantic boundary first.
Then refactor the classes that depend on that boundary.
```

## Priority 1: `NodeDescriptionBuilder`

Current file:

```text
src/reed/composition/node/node_builder.py
```

`NodeDescriptionBuilder` is the most blocking class because it defines how a typed Python function becomes a Reed node contract.

Every major decision depends on this layer:

1. domain types instead of Parcel types;
2. automatic wrapping and unwrapping;
3. `NodeContext` injection;
4. `ctx.last_output` typing;
5. self-flow validation;
6. input and output artifact descriptors;
7. later Flow graph inference.

Current problem:

```text
It currently treats Parcel subclasses as dataflow inputs and outputs.
It does not know about domain artifact types.
It does not know about NodeContext injection.
```

Target:

```text
NodeDescriptionBuilder
    reads typed domain signatures
    separates dataflow parameters from injected context
    validates NodeContext[MemoryType, OutputType]
    validates self-flow
    derives artifact input and output descriptors
```

Recommended work:

1. introduce `DataflowParameter`;
2. introduce `InjectedContextParameter`;
3. parse `NodeContext[MemoryType, OutputType]`;
4. exclude `NodeContext` from input ports;
5. validate `NodeContext` output type against return type;
6. reject multiple contexts;
7. reject missing annotations;
8. reject self-flow signatures;
9. derive consumed and produced domain artifact types.

Why first:

```text
If signature parsing is wrong, every later class receives the wrong contract.
```

## Priority 2: `NodeDescription` / `NodeDefinition`

Current file:

```text
src/reed/composition/node/node_definition.py
```

`NodeDescription` and `NodeDefinition` are blocking because they store the result of signature parsing.

If this model remains Parcel-centered, the rest of the refactor will keep depending on the old boundary.

Current problem:

```text
NodeDefinition currently stores propagation_policy.
NodeDescription currently describes consumed and produced Parcel types.
```

Target:

```text
NodeDefinition
    reusable typed callable definition
    owns no flow-local policy
    owns no callback
    owns no execution state

NodeDescription
    stores domain artifact input descriptors
    stores domain artifact output descriptor
    stores optional NodeContext descriptor
```

Recommended work:

1. replace Parcel-centered consumed/produced metadata with artifact descriptors;
2. store context metadata separately from dataflow inputs;
3. move `propagation_policy` out of `NodeDefinition`;
4. keep function and kind information;
5. preserve reusability.

Why second:

```text
The builder needs a corrected data model to store the new contract.
```

## Priority 3: Create Artifact Descriptor Types

Current file:

```text
new class or type model
```

Artifact descriptors are more blocking than `Flow.add(...)` because the Flow should register artifact relationships, not raw Python annotations or Parcel subclasses.

Current problem:

```text
Reed does not yet have an explicit descriptor for domain artifact identity.
```

Target:

```text
ArtifactDescriptor
    domain_type
    role
    parameter_name or output name
```

Possible related names:

```text
ArtifactInput
ArtifactOutput
ArtifactRole
```

Recommended work:

1. create a type that represents a domain artifact identity;
2. distinguish input artifact descriptors from output artifact descriptors;
3. avoid exposing internal `ArtifactRecord` here;
4. use descriptors in `NodeDescription`;
5. use descriptors later in `FlowNode`, dependency graph, repository, and runtime.

Why third:

```text
Artifact identity is the central type-level graph unit. Without it, Flow composition cannot be clean.
```

## Priority 4: Create `NodeContext`

Current file:

```text
new class
```

`NodeContext` is blocking because `NodeDescriptionBuilder` must detect it, validate it, and exclude it from dataflow inputs.

Current problem:

```text
User code has no controlled access to node-local memory or last output.
```

Target:

```python
NodeContext[MemoryType, OutputType]
```

Initial capabilities:

```text
ctx.memory
ctx.last_output
```

Recommended work:

1. create generic `NodeContext[MemoryType, OutputType]`;
2. expose `memory`;
3. expose `last_output`;
4. keep metadata internal;
5. make context creation internal to Reed;
6. make the type available to the signature parser.

Why fourth:

```text
The signature parser cannot enforce NodeContext rules until the public type exists.
```

## Priority 5: Create `NodeMemory`

Current file:

```text
new class or internal protocol
```

`NodeMemory` is blocking for state-aware node execution, but less blocking than the signature and artifact contract.

Current problem:

```text
Reed has local runtime fields, but no explicit user-facing memory boundary.
```

Target:

```text
NodeMemory belongs to Run x NodeRuntime.
```

Recommended work:

1. instantiate memory from `MemoryType`;
2. store memory under the run-local node execution path;
3. expose memory through `ctx.memory`;
4. keep it separate from `ctx.last_output`;
5. keep it separate from artifact records.

Why fifth:

```text
Memory is necessary for NodeContext execution, but the signature model can be designed before persistence details.
```

## Priority 6: Create `ArtifactRecord`

Current file:

```text
new class or staged successor to src/reed/synchronization/parcel/parcel.py
```

`ArtifactRecord` is blocking for automatic wrapping and unwrapping.

Current problem:

```text
Parcel currently mixes public user boundary and internal versioned artifact record semantics.
```

Target:

```text
ArtifactRecord[DomainType]
    domain value
    artifact version
    provenance
    dependency versions
```

Recommended work:

1. introduce `ArtifactRecord` as the internal wrapper for domain values;
2. preserve the version and provenance mechanisms from `Parcel`;
3. avoid using `Artifact` alone for the record object;
4. keep compatibility with `Parcel` only as a staged migration path if needed.

Why sixth:

```text
The execution path cannot stop passing Parcels to user functions until Reed has an internal record for wrapped domain values.
```

## Priority 7: `ParcelProvenance` / `ParcelVersion`

Current file:

```text
src/reed/synchronization/parcel/provenance.py
```

These classes are less blocking than `ArtifactRecord`, but should move soon after it.

Current problem:

```text
The names still refer to Parcel, while the target concept is artifact record provenance.
```

Target:

```text
ArtifactProvenance
ArtifactVersion
```

Recommended work:

1. preserve current versioning behavior;
2. preserve current provenance behavior;
3. rename after `ArtifactRecord` exists;
4. update dependency mappings from Parcel type to domain artifact type.

Why seventh:

```text
Version and provenance are used by records, repository, validity, and callbacks.
```

## Priority 8: `DependencyRegistry`

Current file:

```text
src/reed/synchronization/validity/dependency_registry.py
```

`DependencyRegistry` is blocking because it already encodes the unique producer rule.

Current strength:

```text
It already enforces one producer per Parcel type.
```

Current problem:

```text
It speaks in module and Parcel vocabulary instead of FlowNode and domain artifact type vocabulary.
```

Target:

```text
ArtifactDependencyGraph
    producers by artifact type
    consumers by artifact type
    upstream FlowNodes
    downstream FlowNodes
```

Recommended work:

1. preserve unique producer validation;
2. migrate producer keys to `FlowNode`;
3. migrate artifact keys to domain artifact types or artifact descriptors;
4. add self-flow validation;
5. move validation earlier into Flow composition when possible.

Why eighth:

```text
Flow composition and trigger decisions depend on a correct artifact dependency graph.
```

## Priority 9: Create `FlowNode`

Current file:

```text
new class
```

`FlowNode` depends on corrected node descriptions and artifact descriptors.

Current problem:

```text
There is no explicit object for a NodeDefinition participating in one Flow.
```

Target:

```text
FlowNode
    flow-local node participation
    owns trigger_policy
    owns on_output
    owns flow-local identity
    points to NodeDefinition
    exposes produced and consumed artifact descriptors
```

Recommended work:

1. create `FlowNode`;
2. store `NodeDefinition`;
3. store flow-local identity;
4. store consumed and produced artifact descriptors;
5. store `TriggerPolicy`;
6. store optional `on_output`;
7. return it from `Flow.add(...)`.

Why ninth:

```text
FlowNode is the composition seam, but it should be built on the corrected typed artifact contract.
```

## Priority 10: `PropagationPolicy` -> `TriggerPolicy`

Current file:

```text
src/reed/composition/node/propagation_policy.py
```

This is a blocking vocabulary correction for execution eligibility.

Current problem:

```text
The current name describes propagation, but the behavior decides whether a node should run.
```

Target:

```python
class TriggerPolicy(Enum):
    ANY_INPUT_CHANGED = auto()
    ALL_INPUTS_CHANGED = auto()
    MANUAL = auto()
```

Recommended work:

1. introduce `TriggerPolicy`;
2. map old values to new values;
3. place the policy on `FlowNode`;
4. later update execution logic to read from `FlowNode`.

Why tenth:

```text
TriggerPolicy depends on FlowNode ownership and artifact input vocabulary.
```

## Priority 11: `Flow`

Current file:

```text
src/reed/composition/flow/flow.py
```

`Flow` is the public composition boundary, but its clean implementation depends on the previous contract work.

Current problem:

```text
Flow currently mixes composition, lazy materialization, and execution entry behavior.
```

Target:

```text
Flow
    explicit composition object
    owns FlowNode registrations
    validates topology
    creates Run through run()
```

Recommended work:

1. introduce `Flow.add(...)`;
2. make configuration keyword-only;
3. return `FlowNode`;
4. validate duplicate producers;
5. validate self-flow;
6. keep old behavior temporarily if needed;
7. move execution-specific state toward `Run`.

Why eleventh:

```text
Flow should be refactored after the node contract and artifact graph vocabulary are ready.
```

## Priority 12: Create `Run`

Current file:

```text
new class or expanded execution package
```

`Run` is blocking for execution isolation.

Current problem:

```text
Flow currently owns or creates execution state directly.
```

Target:

```text
Run
    one concrete execution of a Flow
    owns NodeRuntime instances
    owns run-local services
    owns run-local artifact records
```

Recommended work:

1. create `Run`;
2. make `Flow.run()` create it;
3. move materialized execution state from `Flow` to `Run`;
4. use `Run` as the owner of `NodeRuntime` instances;
5. preserve compatibility while old call behavior is migrated.

Why twelfth:

```text
NodeRuntime, NodeMemory, last_output, and callbacks need a concrete execution owner.
```

## Priority 13: `Node` -> `NodeRuntime`

Current file:

```text
src/reed/composition/node/node.py
```

The current `Node` class behaves more like a runtime instance than a reusable node concept.

Current problem:

```text
Node currently owns flow_id, logistics, Outpost, output result, status handling, execution, and cleanup.
```

Target:

```text
NodeRuntime
    run-local executable instance of a FlowNode
```

Recommended work:

1. treat current `Node` as the migration base for `NodeRuntime`;
2. make it receive a `FlowNode`;
3. build function arguments from descriptors;
4. unwrap artifact records into domain values;
5. inject `NodeContext` when declared;
6. wrap returned domain values into artifact records;
7. track `last_output` after successful commit;
8. dispatch `on_output` after commit.

Why thirteenth:

```text
NodeRuntime depends on FlowNode, Run, NodeContext, NodeMemory, and ArtifactRecord.
```

## Priority 14: Create `NodeExecution`

Current file:

```text
new class
```

`NodeExecution` represents one firing or attempt of a `NodeRuntime`.

Current problem:

```text
Execution phases are currently embedded inside Node.process() and _write_function_result().
```

Target:

```text
NodeExecution
├── build arguments
├── execute function
├── wrap output
├── commit artifact record
├── update memory / last_output
└── dispatch on_output
```

Recommended work:

1. introduce a small execution result object;
2. distinguish computation failure from commit failure and callback failure;
3. prepare future retry semantics;
4. keep first implementation simple.

Why fourteenth:

```text
NodeExecution depends on NodeRuntime and the commit/callback boundary.
```

## Priority 15: `Depot` -> `ArtifactRepository`

Current file:

```text
src/reed/synchronization/depot.py
```

`Depot` is cross-cutting, so it should not be first.

Current problem:

```text
Depot stores one latest Parcel per Parcel type and emits validity updates through the bus.
```

Target:

```text
ArtifactRepository
    authoritative store of committed artifact records
```

Recommended work:

1. introduce `ArtifactRepository`;
2. migrate storage methods to artifact record vocabulary;
3. keep bus protocol compatibility during migration;
4. rename messages later.

Why fifteenth:

```text
Repository should store ArtifactRecords after ArtifactRecord and Run are defined.
```

## Priority 16: `DepotMessages`

Current file:

```text
src/reed/synchronization/depot_messages.py
```

Current problem:

```text
Message names are tied to Depot and Parcel vocabulary.
```

Target:

```text
ArtifactRepositoryGet
ArtifactRepositoryCommit
ArtifactRepositoryUpdate
ArtifactRepositoryRegistration
```

Recommended work:

1. rename messages after `ArtifactRepository` exists;
2. preserve message semantics;
3. avoid changing bus behavior in the same step unless necessary.

Why sixteenth:

```text
Protocol renames are cross-cutting and should happen after repository naming stabilizes.
```

## Priority 17: `Outpost`

Current file:

```text
src/reed/synchronization/outpost.py
```

`Outpost` is cross-cutting and should be refactored after `NodeRuntime` and `ArtifactRepository` are explicit.

Current problem:

```text
Outpost is a broad synchronization component with generated fields, local artifact cache, mutation guards, repository communication, status management, and transaction behavior.
```

Target options:

```text
Option A: absorb into NodeRuntime internals.
Option B: rename to RepositoryAdapter or ArtifactPortAdapter.
```

Recommended work:

1. do not rename it to `NodeMemory`;
2. do not expose it through `NodeContext`;
3. first make `NodeRuntime` explicit;
4. then decide whether Outpost remains as an internal adapter or disappears into NodeRuntime;
5. preserve its transaction and mutation-gate ideas.

Why seventeenth:

```text
Outpost depends on repository, artifact records, runtime ownership, and execution commit semantics.
```

## Priority 18: `OutpostBuilder`

Current file:

```text
src/reed/synchronization/outpost_builder.py
```

Current problem:

```text
OutpostBuilder generates dataclasses from Parcel-based consumed and produced fields.
```

Target:

```text
Runtime adapter or NodeRuntime internal builder based on artifact descriptors.
```

Recommended work:

1. update only after artifact descriptors exist;
2. generate from artifact input/output descriptors instead of Parcel subclasses;
3. preserve the schema-generation idea only if still useful.

Why eighteenth:

```text
The builder depends on the final role of Outpost.
```

## Priority 19: `SchemaBuilder` / `Schema`

Current file:

```text
src/reed/activation/schema.py
```

Current problem:

```text
SchemaBuilder compiles dataclass fields into Parcel role descriptors.
```

Target:

```text
ArtifactSchema
ArtifactDescriptor
ArtifactRole
```

Recommended work:

1. preserve structural schema compilation;
2. change from Parcel subclass inspection to artifact descriptor inspection;
3. keep role-based grouping if it remains useful;
4. rename after the artifact boundary is implemented.

Why nineteenth:

```text
Schema migration depends on ArtifactRecord, ArtifactDescriptor, and the final role of Outpost.
```

## Priority 20: `Sentinel`, `Status`, `DirtyFlags`, `ValidityTransition`

Current files:

```text
src/reed/synchronization/validity/sentinel.py
src/reed/activation/status/status.py
src/reed/activation/status/status_manager.py
src/reed/activation/status/dirty_flags.py
src/reed/synchronization/validity/validity_transition.py
```

Current problem:

```text
Validity and dirty state are useful, but the vocabulary is still tied to Parcel and module concepts.
```

Target:

```text
Artifact validity
Artifact change status
TriggerPolicy evaluation
```

Recommended work:

1. keep the dirty/clean idea as Reed's coarse delta model;
2. rename around artifact types;
3. connect status changes to `TriggerPolicy`;
4. avoid mixing validity state with callback dispatch.

Why twentieth:

```text
Status behavior depends on artifact graph, repository, and trigger policy.
```

## Priority 21: `Logistics`

Current file:

```text
src/reed/synchronization/logistics.py
```

Current problem:

```text
Logistics owns or wires Bus, Depot, and Outpost creation.
```

Target:

```text
RunServices
ExecutionServices
```

Recommended work:

1. postpone rename;
2. clarify whether it belongs to Run creation;
3. decide whether it should own ArtifactRepository and Bus for one Run;
4. avoid exposing it publicly.

Why twenty-first:

```text
Service wiring should move after Run, ArtifactRepository, and NodeRuntime are explicit.
```

## Priority 22: Transportation Layer

Current files:

```text
src/reed/transportation/bus.py
src/reed/transportation/broker.py
src/reed/transportation/hub.py
src/reed/transportation/port.py
src/reed/transportation/protocol/message_context.py
```

Current strength:

```text
The transport layer already has useful concepts: Bus, Port, MessageContext, trace IDs, split-phase handling, and deferred actions.
```

Current problem:

```text
It may become too visible if higher-level concepts are not explicit enough.
```

Target:

```text
Internal infrastructure used by Run, ArtifactRepository, and NodeRuntime.
```

Recommended work:

1. do not refactor first;
2. keep it internal;
3. preserve split-phase execution;
4. only rename if it blocks the new architecture.

Why twenty-second:

```text
The transport layer is infrastructure. It depends on higher-level ownership decisions.
```

## Priority 23: Public Decorators

Current file:

```text
src/reed/api/decorator.py
```

Current problem:

```text
@flow is no longer the main architectural direction.
@node can remain useful.
@input and @output may need reevaluation after Flow.add(...) and typed artifacts exist.
```

Target:

```text
@node remains optional.
Flow.add(...) becomes the main composition API.
@flow moves to compatibility path or is deprecated later.
```

Recommended work:

1. keep `@node` during the transition;
2. avoid removing `@flow` in the first implementation pass;
3. expose `Flow`, `NodeContext`, and `TriggerPolicy` publicly;
4. update examples after behavior works.

Why twenty-third:

```text
Public decorators should change after the new public API exists.
```

## Priority 24: Public Package Exports

Current file:

```text
src/reed/__init__.py
```

Current problem:

```text
The public exports still expose old vocabulary such as Parcel.
```

Target:

```text
Flow
node
NodeContext
TriggerPolicy
ArtifactRecord only if needed for advanced use
```

Recommended work:

1. update exports after the new classes exist;
2. avoid exposing internal repository or runtime classes;
3. keep compatibility exports temporarily if needed.

Why twenty-fourth:

```text
Exports should change after implementation, not before.
```

## Blocking Order Summary

Recommended class-level order from most blocking to least blocking:

```text
1. NodeDescriptionBuilder
2. NodeDescription / NodeDefinition
3. Artifact descriptor types
4. NodeContext
5. NodeMemory
6. ArtifactRecord
7. ArtifactProvenance / ArtifactVersion
8. DependencyRegistry
9. FlowNode
10. PropagationPolicy -> TriggerPolicy
11. Flow
12. Run
13. Node -> NodeRuntime
14. NodeExecution
15. Depot -> ArtifactRepository
16. DepotMessages
17. Outpost
18. OutpostBuilder
19. SchemaBuilder / Schema
20. Sentinel / Status / DirtyFlags / ValidityTransition
21. Logistics
22. Transportation layer
23. Public decorators
24. Public package exports
```

## Milestones And Slices

Priorities 1 through 24 above define the *dependency* order: what must exist
before what. They do not define *slice size*. A single autonomous
implementation task should receive one slice, not one milestone.

The grouping below decomposes the blocking priorities (1-15, the ones the
target architecture contract tests actually exercise) into milestones and
slices sized for one controlled agent task each. Priorities 16-24 remain
cross-cutting cleanup and are intentionally left ungrouped until the
milestones below are complete.

This decomposition follows directly from the dependency notes already given
for each priority above ("why first", "why second", ...). It does not change
that ordering or introduce new architecture; it only says where to cut it
into agent-sized pieces.

### Milestone 1 -- Typed Composition Foundation

Composition-time correctness: signature parsing, artifact identity, and the
`Flow.add(...)` surface. No `Run`/execution changes yet.

| Slice | Priorities | Delivers | Target tests it should move |
|---|---|---|---|
| 1A | 1 | Typed domain signature parsing; `NodeContext` detected and excluded from input ports; `NodeContext[MemoryType, OutputType]` validated against the return type; self-flow rejected at signature level. | `test_node_signature_uses_domain_types_not_artifact_records`, `test_node_context_is_injected_and_not_registered_as_input_port`, `test_node_context_output_type_must_match_return_type`, `test_self_flow_signature_is_rejected` |
| 1B | 2, 3 | `NodeDescription`/`NodeDefinition` store artifact descriptors instead of Parcel-centered metadata; `ArtifactDescriptor` type introduced. | (supports 1A/1E; no test moves alone) |
| 1C | 4, 5 | `NodeContext` becomes a real generic class; `NodeMemory` storage boundary introduced under the run-local path. | (prerequisite for 1A's validation to check a real class; supports Milestone 2) |
| 1D | 6, 7 | `ArtifactRecord` introduced as the internal wrapper; `ArtifactProvenance`/`ArtifactVersion` carry forward `Parcel`'s existing version/provenance behavior. | regression: `tests/test_current_regression_artifacts_repository.py` must stay green |
| 1E | 8 | `DependencyRegistry` migrated to `FlowNode`/artifact-type vocabulary; unique-producer and self-flow validation enforced at Flow-composition time. | `test_duplicate_output_domain_type_is_rejected_in_one_flow`, `test_parallel_safe_branching_uses_distinct_output_artifact_types` |
| 1F | 9 | `FlowNode` created as the object returned by `Flow.add(...)`. | `test_flow_add_registers_callable_and_returns_flownode` (partial) |
| 1G | 10 | `PropagationPolicy` renamed/relocated to `TriggerPolicy`, owned by `FlowNode`. | `test_flow_add_uses_keyword_only_trigger_policy_and_on_output` (partial) |
| 1H | 11 (the `Flow.add(...)` surface only, not the full builder/execution split) | `Flow.add(...)` with keyword-only `trigger_policy`/`on_output`; rejects positional configuration ambiguity. | `test_flow_add_registers_callable_and_returns_flownode`, `test_flow_add_uses_keyword_only_trigger_policy_and_on_output`, `test_flow_add_rejects_positional_configuration_ambiguity` |

### Milestone 2 -- Run And Execution Boundary

Execution-time correctness: `Run` isolation, `NodeRuntime`, commit/callback
ordering. Depends on Milestone 1.

| Slice | Priorities | Delivers | Target tests it should move |
|---|---|---|---|
| 2A | 11 (remainder), 12 | `Flow` becomes a pure composition/builder object; `Flow.run()` creates a `Run`. | (prerequisite; no test moves alone) |
| 2B | 13 | `Node` migrated to `NodeRuntime`; automatic wrap/unwrap at the execution boundary; `ctx.memory` and `ctx.last_output` wired to `Run x NodeRuntime`. | `test_run_instances_isolate_node_memory`, `test_last_output_exposes_latest_committed_domain_value` |
| 2C | 14 | `NodeExecution` splits commit from `on_output` dispatch; async callbacks supported; callback failure isolated from commit; stateful firings serialized. | `test_on_output_runs_after_commit_and_receives_domain_value`, `test_async_on_output_is_supported_after_commit`, `test_callback_failure_does_not_undo_committed_output`, `test_stateful_node_runtime_firings_are_serialized` |
| 2D | 15 | `Depot` renamed to `ArtifactRepository` (storage vocabulary only; bus protocol renames stay in priority 16). | supports `run.repository.get(...)` usage in the Milestone 2 tests above |

Priorities 16-24 (message renames, `Outpost`, `OutpostBuilder`, schema,
validity vocabulary, `Logistics`, transport, public decorators, public
exports) remain cross-cutting vocabulary work. Do not schedule them as slices
until Milestones 1 and 2 are complete and their own dependencies (noted in
each priority's "why" above) are satisfied.

### How To Use This Table

Each row is sized to be one slice plan (see `refactor_agent_protocol.md`). A
slice must not span rows. If implementing a row reveals it is still too
large, split it further along its own internal dependencies rather than
merging it with a neighboring row.

`docs/refactor_state.md` records which slice is current. Update it whenever a
slice completes.

