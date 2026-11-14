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

**Question this milestone answers: what is the computation?**

Composition-time correctness only: signature parsing, artifact identity, and
the `Flow.add(...)` surface. No `Run`, no `NodeRuntime`, no execution.

| Slice | Priorities | Delivers | Regression protection | Target tests it can flip |
|---|---|---|---|---|
| 1A | 1; part of 4 | Typed domain signature parsing (`NodeDescriptionBuilder`); self-flow rejected at signature level; **and** the minimal `NodeContext[MemoryType, OutputType]` representation needed for the parser to detect it -- a real, importable generic class with no runtime behavior (no `ctx.memory`, no `ctx.last_output`, no Run/NodeRuntime wiring). See "1A / 1C dependency" below for why the shell has to move here. | `tests/test_current_regression_node_description.py` must stay green (old Parcel-based path untouched). | None yet -- see "Why no target test moves before 1F" below. Agent should add a focused unit-level test for the new signature-parsing/context-detection behavior itself, per `refactor_guide.md` #11. |
| 1B | 2, 3 | `NodeDescription`/`NodeDefinition` store artifact descriptors instead of Parcel-centered metadata; `ArtifactDescriptor` type (`domain_type` + role + parameter/output name) introduced. | Same regression file as 1A. | None yet (prerequisite for 1C-1F). |
| 1C | 9 | `FlowNode` created: holds the `NodeDefinition`, the consumed/produced `ArtifactDescriptor`s, and fields for `trigger_policy`/`on_output` (typed against the *existing* `PropagationPolicy` enum for now -- see "FlowNode / DependencyRegistry ordering" below for why this is not a forward dependency). | -- | None yet (nothing can reach `FlowNode` publicly until 1F). |
| 1D | 8 | `DependencyRegistry` migrated to `FlowNode`/artifact-type vocabulary (producers/consumers keyed by `FlowNode` and domain artifact type); unique-producer validation preserved; self-flow validation added at the Flow-composition level. | `tests/test_current_regression_artifacts_repository.py::test_dependency_registry_*` (old `Role`/Parcel-keyed API) must stay green -- keep the old entry points working alongside the new ones rather than replacing them in place. | None yet. |
| 1E | 10 | `PropagationPolicy` renamed to `TriggerPolicy` (enum values renamed to the `*_INPUT*_CHANGED` / `MANUAL` shape already used elsewhere in the docs and in the test suite) and ownership relocated from `NodeDefinition` to `FlowNode`. | -- | None yet. |
| 1F | remainder of 11 | `Flow.add(...)`: creates a `FlowNode` from a callable, runs `DependencyRegistry` validation (duplicate producer, self-flow), stores `trigger_policy`/`on_output` as keyword-only arguments, rejects positional configuration ambiguity. This is a wiring slice over already-built collaborators (1A-1E), not a new architectural transformation. | All of the above regression suites still green. | **All nine** Milestone-1 target tests: `test_flow_add_registers_callable_and_returns_flownode`, `test_flow_add_uses_keyword_only_trigger_policy_and_on_output`, `test_flow_add_rejects_positional_configuration_ambiguity`, `test_node_signature_uses_domain_types_not_artifact_records`, `test_node_context_is_injected_and_not_registered_as_input_port`, `test_node_context_output_type_must_match_return_type`, `test_duplicate_output_domain_type_is_rejected_in_one_flow`, `test_self_flow_signature_is_rejected`, `test_parallel_safe_branching_uses_distinct_output_artifact_types`. |

#### Why no target test moves before 1F

Every Milestone-1 target test calls `flow.add(...)` -- there is no test in
`tests/test_target_architecture_contract.py` that exercises
`NodeDescriptionBuilder`, `FlowNode`, or `DependencyRegistry` directly. That
means 1A-1E deliver real, verifiable mechanism, but none of them can be
*observed* as done through a pre-existing target test; only 1F can. This is
expected, not a sign that 1A-1E should be merged into 1F: each still has its
own bounded change surface, its own regression protection, and its own
definition of done, and 1F itself stays a thin wiring slice specifically
*because* the substantive work already happened in 1A-1E. Treat "many
pre-existing tests flip in one slice" and "large diff" as different things --
1F should have the smaller diff of the six.

#### The 1A / 1C dependency (resolved)

The original decomposition put minimal typed `NodeContext` recognition in 1A
and the "real generic class" in 1C -- but a signature parser cannot recognize
`NodeContext[MemoryType, OutputType]` in a function annotation unless
`NodeContext` already exists as an importable generic type to check
`typing.get_origin(annotation) is NodeContext` against. Priority 4's own
"Recommended work" already anticipated this ("make the type available to the
signature parser"). The fix: 1A now includes the minimal structural
`NodeContext` shell (the class exists, is generic over `MemoryType`/
`OutputType`, and is detectable/inspectable), while the *behavior* --
`ctx.memory` and `ctx.last_output` actually backed by Run-local storage --
moves entirely into Milestone 2 (slice 2D), because `NodeMemory` is defined
(`architectural_invariants.md` #14) as scoped to `Run x NodeRuntime`, which
does not exist until Milestone 2. Putting `NodeMemory`'s storage boundary in
Milestone 1 (the original 1C) was never implementable -- it depended on an
abstraction (`Run`, `NodeRuntime`) two milestones away. It is now placed
correctly.

#### FlowNode / DependencyRegistry ordering (resolved)

The original decomposition asked `DependencyRegistry` to migrate to
`FlowNode` vocabulary (Priority 8) *before* `FlowNode` existed (Priority 9).
Priority 8's own text confirms the dependency runs the other way ("migrate
producer keys to `FlowNode`"): you cannot key a registry by an object that
does not exist yet. `FlowNode` now comes first (1C), `DependencyRegistry`
second (1D). `TriggerPolicy` (1E) comes after `FlowNode` too, but this is
*not* a forward dependency: `FlowNode`'s trigger-policy field can be (and
should be) typed against the current, already-existing `PropagationPolicy`
enum in 1C, and 1E only renames that enum and relocates its ownership --
nothing in 1C references a type that doesn't exist yet.

#### ArtifactRecord placement (also corrected, not separately requested)

The original 1D introduced `ArtifactRecord`/`ArtifactProvenance`/
`ArtifactVersion` in Milestone 1 with no consumer: nothing wraps or unwraps
through it until `NodeRuntime`'s execution boundary exists. That is exactly
the kind of premature abstraction `non-goals.md`'s "Speculative Abstractions"
rule warns against ("a concrete requirement of the current slice"), and it
was also a real dependency problem, not just a style issue. `ArtifactRecord`
now moves to Milestone 2, slice 2C, where it is introduced and used in the
same slice.

### Milestone 2 -- Run And Execution Boundary

**Question this milestone answers: how is one composition executed?**

Depends on Milestone 1 (1A-1F). Introduces `Run`, `NodeRuntime`,
`NodeExecution`, and the domain-value/`ArtifactRecord` boundary.

| Slice | Priorities | Delivers | Verification |
|---|---|---|---|
| 2A | part of 11, 12 | `Flow` becomes a pure composition/builder object (no execution-entry mixing); `Flow.run()` creates a `Run`. `Run` gets a `.repository` accessor from this point on, backed by whatever the current storage class is called internally (still `Depot` until Milestone 3, slice 3A -- see below). | No target test moves alone; `tests/test_current_regression_flow_runtime.py` (the old `@flow` path) must stay green throughout. |
| 2B | part of 13 | `Node` migrated to `NodeRuntime`: run-local ownership of one `FlowNode`'s execution state, created and held by `Run`. | No target test moves alone. |
| 2C | 6, 7, part of 13 | `ArtifactRecord` introduced as the internal wrapper (value + version + provenance, carrying forward `Parcel`'s existing version/provenance mechanics -- `ArtifactProvenance`/`ArtifactVersion`); wired into `NodeRuntime`'s execution path so user functions receive/return domain values while Reed wraps/unwraps `ArtifactRecord`s at the boundary. | `tests/test_current_regression_artifacts_repository.py` (Parcel version/provenance tests) must stay green. |
| 2D | 5, part of 4, part of 13 | `NodeMemory` storage boundary, scoped to `Run x NodeRuntime`; `ctx.memory` and `ctx.last_output` on the `NodeContext` shell (from 1A) wired to real per-run, per-runtime storage. | No target test moves alone (see 2E; `ctx.last_output` needs a commit to report). |
| 2E | 14, part of 13 | `NodeExecution`: the firing pipeline -- build arguments, execute the user function, wrap the output, commit the `ArtifactRecord`, update memory/`last_output`. | `test_run_instances_isolate_node_memory`, `test_last_output_exposes_latest_committed_domain_value` |
| 2F | part of 14 | `on_output` dispatch strictly after commit; async callback support; callback failure isolated from (does not undo) the committed output; `run.callback_failures` observable. | `test_on_output_runs_after_commit_and_receives_domain_value`, `test_async_on_output_is_supported_after_commit`, `test_callback_failure_does_not_undo_committed_output` |
| 2G | part of 13, part of 14 | Stateful `NodeRuntime` firings serialized (at most one firing in flight per state-aware `NodeRuntime`). | `test_stateful_node_runtime_firings_are_serialized` |

Priority 13 ("`Node` -> `NodeRuntime`") and Priority 14 ("Create
`NodeExecution`") each span several of these slices -- see "Priority-to-Slice
Traceability" below for the explicit breakdown. That is expected: both
priorities describe a whole execution pipeline, and the seams above ("and"
clauses in the original wording) are exactly where it splits into
independently verifiable slices.

`run.repository`, used by the 2F target tests, is Run's own accessor
(introduced in 2A) -- it does not require the `Depot` -> `ArtifactRepository`
class rename (Priority 15, Milestone 3) to already be done. Milestone 2 can
and should pass its tests while the underlying storage class is still
internally called `Depot`.

### Milestone 3 -- Infrastructure Alignment

**Question this milestone answers: how does Reed's internal infrastructure
support that execution model?**

Depends on Milestone 2 (specifically 2C, so `ArtifactRecord` exists before
the store that holds it is renamed). Purely cross-cutting vocabulary and
internal-infrastructure work; no target test depends on this milestone
except indirectly (none of the fifteen target tests name `Depot`,
`ArtifactRepository`, `Outpost`, or any Priority-16-24 concept directly).

| Slice | Priorities | Delivers |
|---|---|---|
| 3A | 15 | `Depot` renamed to `ArtifactRepository` (class and storage-method vocabulary only); `Run.repository` now genuinely typed/named `ArtifactRepository` instead of pointing at a `Depot` instance under an aliased attribute name. |
| 3B+ | 16-24 | `DepotMessages` -> repository message renames; `Outpost` and `OutpostBuilder`; `SchemaBuilder`/`Schema`; `Sentinel`/`Status`/`DirtyFlags`/`ValidityTransition`; `Logistics`; the transportation layer; public decorators; public package exports. Left undecomposed for now -- each already has "why" reasoning in the Priority list above (Priorities 16-24), and should be broken into its own lettered slices only once Milestone 3 actually begins, so this document does not over-plan work that is still several milestones away. |

This milestone did not exist in the previous decomposition. `ArtifactRepository`
was originally placed in Milestone 2; see "ArtifactRepository placement" in
the Milestone-2 discussion above and in the top-level task report for why it
moved.

### Priority-To-Slice Traceability

Priorities 1-24 remain the authoritative *dependency* order (unchanged by
this refinement -- nothing above reorders priorities 1-24 relative to each
other; it only decides which milestone/slice each one's work lands in, and
splits a few of them across slices where their own description already
described more than one transformation).

| Priority | Slice(s) |
|---|---|
| 1 | 1A |
| 2 | 1B |
| 3 | 1B |
| 4 | split: minimal structural shell -> 1A; real `ctx.memory`/`ctx.last_output` behavior -> 2D |
| 5 | 2D |
| 6 | 2C |
| 7 | 2C |
| 8 | 1D |
| 9 | 1C |
| 10 | 1E |
| 11 | split: `Flow.add(...)` surface -> 1F; remainder (pure builder / execution-entry separation) -> 2A |
| 12 | 2A |
| 13 | split: runtime ownership -> 2B; wrap/unwrap boundary -> 2C; context/memory wiring -> 2D; firing pipeline -> 2E; `on_output` dispatch -> 2F; serialization -> 2G |
| 14 | split: build/execute/commit -> 2E; failure classification and callback dispatch -> 2F; interacts with serialization -> 2G |
| 15 | 3A |
| 16 | 3B+ (undecomposed) |
| 17 | 3B+ (undecomposed) |
| 18 | 3B+ (undecomposed) |
| 19 | 3B+ (undecomposed) |
| 20 | 3B+ (undecomposed) |
| 21 | 3B+ (undecomposed) |
| 22 | 3B+ (undecomposed) |
| 23 | 3B+ (undecomposed) |
| 24 | 3B+ (undecomposed) |

### How To Use This Table

Each row is sized to be one slice plan (see `refactor_agent_protocol.md`). A
slice must not span rows. If implementing a row reveals it is still too
large, split it further along its own internal dependencies rather than
merging it with a neighboring row.

`docs/refactor_state.md` records which slice is current. Update it whenever a
slice completes.

