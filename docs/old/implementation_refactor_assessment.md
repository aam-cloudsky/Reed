# Implementation Refactor Assessment

This document evaluates Reed's current implementation against the architectural decisions established in issues #1, #2, #3, and #4.

It is not an implementation patch.

It is a critical refactoring assessment intended to guide the task list for the next implementation phase.

The goal is to identify which current mechanisms should be preserved, renamed, separated, integrated, or redesigned so that the code reflects Reed's conceptual architecture.

## Evaluation Method

This assessment compares Reed's current code with implementation patterns found in established systems and official repositories.

The most relevant references are:

1. LangGraph's `StateGraph`, which separates graph building from graph execution, supports per-node policies, validates graph structure, and uses typed schemas.
2. Dagster's asset and graph asset decorators, which separate asset identity, materialization, hooks, automation conditions, and resource access.
3. Prefect's task model, which stores task options such as retries, hooks, result persistence, caching, and state hooks as explicit task configuration.
4. Apache Beam's `DoFn` parameter mechanism, which distinguishes normal data parameters from framework-injected parameters such as state, timers, timestamp, and window.
5. Apache Flink's stateful operator model, which distinguishes stateless processing from stateful processing and motivates explicit framework-managed local memory.

The scientific references behind the conceptual direction are:

1. Derek G. Murray et al., "Naiad: A Timely Dataflow System", DOI: `10.1145/2517349.2522738`.
2. Paris Carbone et al., "Apache Flink: Stream and Batch Processing in a Single Engine", DOI: `10.1109/ICDE.2015.7066051`.
3. Tyler Akidau et al., "The Dataflow Model: A Practical Approach to Balancing Correctness, Latency, and Cost in Massive-Scale, Unbounded, Out-of-Order Data Processing", DOI: `10.14778/2824032.2824076`.
4. Tyler Akidau et al., "MillWheel: Fault-Tolerant Stream Processing at Internet Scale", DOI: `10.14778/2536222.2536229`.
5. Yadu Babuji et al., "Parsl: Pervasive Parallel Programming in Python", DOI: `10.1145/3307681.3325400`.

Repository and documentation sources inspected:

1. LangGraph `StateGraph` source: `https://github.com/langchain-ai/langgraph/blob/main/libs/langgraph/langgraph/graph/state.py`.
2. LangGraph Graph API documentation: `https://docs.langchain.com/oss/python/langgraph/graph-api`.
3. Dagster asset decorator source: `https://github.com/dagster-io/dagster/blob/master/python_modules/dagster/dagster/_core/definitions/decorators/asset_decorator.py`.
4. Dagster asset sensors documentation: `https://docs.dagster.io/guides/automate/asset-sensors`.
5. Dagster assets API documentation: `https://docs.dagster.io/api/dagster/assets`.
6. Prefect task source: `https://github.com/PrefectHQ/prefect/blob/main/src/prefect/tasks.py`.
7. Prefect state-change hooks documentation: `https://docs.prefect.io/v3/how-to-guides/workflows/state-change-hooks`.
8. Apache Beam `DoFn` source: `https://github.com/apache/beam/blob/master/sdks/python/apache_beam/transforms/core.py`.
9. Apache Beam programming guide: `https://beam.apache.org/documentation/programming-guide/`.
10. Apache Flink stateful stream processing documentation: `https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/stateful-stream-processing/`.

## Current Reed Implementation Summary

The current implementation has several strong ideas already present:

1. `NodeDescriptionBuilder` inspects typed Python functions.
2. `NodeDefinition` stores a declarative description of a user function.
3. `FlowDefinition` collects node definitions from a decorated class.
4. `DependencyRegistry` already enforces the unique producer rule for Parcel types.
5. `Depot` stores the latest published Parcel by type.
6. `Outpost` maintains a local view of consumed and produced Parcels.
7. `Outpost` already has mutation gates and a transaction boundary.
8. `Node` reacts to status changes and executes the user function.
9. `PropagationPolicy` already represents a simple trigger decision.
10. Provenance and versions already exist on `Parcel`.

The main problem is not that Reed lacks architectural ideas.

The main problem is that several ideas are currently mixed inside names and classes that do not expose the intended boundaries clearly.

## Highest Priority Refactoring Theme

The core refactoring theme should be:

```text
make architectural boundaries explicit in code
```

The target boundaries are:

```text
DomainType != ArtifactRecord
Artifact identity != Artifact version
NodeDefinition != FlowNode
Flow != Run
NodeRuntime != NodeExecution
NodeMemory != last output
TriggerPolicy != on_output
NodeContext != InputPort
```

These boundaries should become visible through:

1. class names;
2. type aliases;
3. constructor arguments;
4. validation functions;
5. tests;
6. module layout.

## 1. Flow Builder And Executable Flow Are Currently Blurred

### Current Reed Mechanism

`Flow` currently owns materialization and execution behavior.

It is created from a `FlowDefinition` collected through `@flow`, and it lazily creates `Node` instances when called.

Conceptually, this mixes:

```text
FlowDefinition
Flow composition
Run execution
Node runtime creation
```

### External Pattern

LangGraph's `StateGraph` is explicitly a builder. Its source documents that the builder cannot be used directly for execution and must be compiled before execution methods such as `invoke` or `stream` become available.

The important pattern is:

```text
builder graph -> compiled/executable graph
```

### Problem In Reed

Reed's current `Flow` is both:

1. a composition object;
2. an execution entry point;
3. a lazy materializer of runtime nodes.

This makes it harder to reason about whether a field belongs to Flow composition or to one concrete execution.

### Recommendation

Introduce a clearer split:

```text
Flow
    composition builder / validated graph

Run
    one concrete execution of a Flow
```

`Flow.run()` should create a `Run`.

The `Run` should own concrete execution state and runtime instances.

Recommended target:

```python
flow = Flow()
flow.add(node_a)
flow.add(node_b)

run = flow.run()
```

This also gives Reed a natural place for future features:

```text
Run
├── NodeRuntime instances
├── artifact records for this execution
├── run status
├── trace/session information
└── execution scheduler
```

## 2. `Flow.add(...)` Should Create A Flow-Local Node Participation

### Current Reed Mechanism

`NodeDefinition` is reusable, but the current materialized `Node` is created directly when `Flow` materializes.

There is no explicit public object representing "this node definition participating in this specific Flow".

### External Pattern

LangGraph stores node specifications inside the graph builder and keeps per-node configuration such as retry policy, cache policy, error handler, timeout, and trace policy.

Prefect's task object also stores task-level options such as retries, cache settings, result persistence, timeout, and hooks. Its `with_options(...)` method creates a new configured task instance while preserving the underlying function.

### Problem In Reed

Without an explicit `FlowNode`, Reed has no clean place to attach:

1. `trigger_policy`;
2. `on_output`;
3. flow-local identity;
4. future display name;
5. future per-node scheduling configuration.

Attaching these directly to `NodeDefinition` would be wrong because `NodeDefinition` is reusable.

Attaching them directly to `NodeRuntime` would be too late because they are composition-time configuration.

### Recommendation

Introduce:

```text
FlowNode
```

as the result of:

```python
flow_node = flow.add(
    node_function,
    trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED,
    on_output=callback,
)
```

`FlowNode` should store:

1. the `NodeDefinition`;
2. the flow-local identity;
3. the resolved consumed artifact types;
4. the resolved produced artifact type;
5. the `TriggerPolicy`;
6. the optional `on_output` callback;
7. eventually an explicit name if multiple registrations become supported.

This produces the chain:

```text
NodeDefinition -> FlowNode -> NodeRuntime -> NodeExecution
```

## 3. Prefer Keyword-Only Node Configuration

### Current Reed Mechanism

Node configuration is mostly implicit.

`PropagationPolicy` is stored in `NodeDefinition`, and status changes invoke processing through `_on_status_changed`.

Callbacks exist internally as status-change callbacks through `Outpost.set_on_status_changed(...)`, but there is no user-facing `on_output` callback at Flow composition time.

### External Pattern

LangGraph's `add_node(...)` accepts per-node policies through named arguments such as `retry_policy`, `cache_policy`, `timeout`, and `trace_policy`.

Dagster uses named decorator parameters such as `hooks`, `automation_condition`, `backfill_policy`, `metadata`, and `resource_defs`.

Prefect uses named task options such as `retries`, `timeout_seconds`, `on_completion`, `on_failure`, and `cache_policy`.

### Problem In Reed

Allowing multiple positional forms would make the API ambiguous:

```python
flow.add(my_node, callback, trigger_policy)
flow.add(my_node, trigger_policy, callback)
```

That style does not fit Reed's strong typing direction.

### Recommendation

Use keyword-only configuration:

```python
flow.add(
    my_node,
    trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED,
    on_output=on_result,
)
```

This is easier to read, easier to type-check, easier to extend, and easier to validate.

The accepted forms should be:

```python
flow.add(my_node)
flow.add(my_node, on_output=callback)
flow.add(my_node, trigger_policy=policy)
flow.add(my_node, trigger_policy=policy, on_output=callback)
```

## 4. Rename `PropagationPolicy` To `TriggerPolicy`

### Current Reed Mechanism

`PropagationPolicy` currently has:

```python
ANY_DEPENDENCY_CHANGED
ALL_DEPENDENCIES_CHANGED
MANUAL
```

and `Node._should_run(...)` uses it to decide whether a Node should execute after dependency status changes.

### Problem In Reed

The name `PropagationPolicy` describes how change moves through the graph, but the code uses it to decide whether a Node runs.

That is closer to:

```text
trigger policy
```

than:

```text
propagation policy
```

### Recommendation

Rename conceptually to:

```text
TriggerPolicy
```

The policy should live on `FlowNode`, not on `NodeDefinition`.

Reason:

```text
the same NodeDefinition may have different trigger policies in different Flows
```

Recommended initial enum:

```python
class TriggerPolicy(Enum):
    ANY_INPUT_CHANGED = auto()
    ALL_INPUTS_CHANGED = auto()
    MANUAL = auto()
```

This renames dependency vocabulary to artifact/input vocabulary, matching the new API.

## 5. Separate Output Observation From Triggering

### Current Reed Mechanism

The existing status-change callback in `Outpost` is used internally to trigger `Node.process()`.

This is not the same concept as a user callback observing a produced output.

### External Pattern

Dagster distinguishes automation conditions and hooks from the asset computation function.

Prefect distinguishes the task function from state hooks such as completion and failure hooks.

### Problem In Reed

If Reed uses a generic `callback` term, it risks mixing:

1. internal status-change reaction;
2. execution triggering;
3. post-output observation;
4. external side effects.

### Recommendation

Use:

```text
on_output
```

for the public user callback.

Define it narrowly:

```text
on_output runs after a successful artifact commit and receives the domain output value.
```

It should not control graph routing, retries, shared artifact mutation, or trigger policy evaluation.

Recommended type shape:

```python
OnOutputCallback = (
    Callable[[OutputType], None]
    | Callable[[OutputType], Awaitable[None]]
)
```

## 6. `Node` Currently Acts Like `NodeRuntime`

### Current Reed Mechanism

The current `Node` class owns:

1. `flow_id`;
2. `definition`;
3. `function`;
4. `logistics`;
5. an `Outpost`;
6. output result state;
7. status-change behavior;
8. execution through `process()`;
9. lifecycle cleanup.

This is not just a node definition.

It is closer to a runtime instance of a node inside a flow execution.

### Problem In Reed

The class name `Node` hides the distinction between:

```text
NodeDefinition
FlowNode
NodeRuntime
NodeExecution
```

This makes future features harder:

1. multiple Runs of the same Flow;
2. multiple NodeRuntime instances from the same FlowNode;
3. execution attempts and retries;
4. per-run memory isolation;
5. per-execution tracing;
6. parallel execution.

### Recommendation

Treat current `Node` as the migration base for:

```text
NodeRuntime
```

A future `Node` may either be:

1. an alias for `NodeDefinition`, or
2. not a concrete class in the public API.

Recommended split:

```text
NodeDefinition
    reusable typed callable description

FlowNode
    flow-local participation and configuration

NodeRuntime
    run-local executable instance

NodeExecution
    one execution attempt/firing of NodeRuntime
```

## 7. `Outpost` Should Become An Internal Runtime Adapter Or Be Absorbed Into `NodeRuntime`

### Current Reed Mechanism

`Outpost` is generated dynamically from consumed and produced Parcel fields.

It provides:

1. a local view of synchronized Parcels;
2. mutation guards;
3. status management;
4. registration with `Depot`;
5. communication ports;
6. produced Parcel snapshots;
7. provenance update;
8. transaction-style publication.

### Problem In Reed

`Outpost` is not local memory.

It is also not a user-facing context.

It is an internal synchronization component currently standing between `Node` and `Depot`.

The name `Outpost` forces the reader to learn a metaphor instead of revealing the architectural role.

### Recommendation

There are two viable paths.

The preferred path is:

```text
Outpost -> NodeRuntime internals
```

Under this path, `NodeRuntime` owns the responsibilities currently distributed between `Node` and `Outpost`.

The conservative migration path is:

```text
Outpost -> ArtifactPortAdapter
```

or:

```text
Outpost -> RepositoryAdapter
```

Under this path, the class remains as an internal adapter responsible for repository synchronization, while `NodeRuntime` becomes the user-execution owner.

Recommendation:

```text
Start by treating Outpost as an internal NodeRuntime component.
Do not expose it.
Do not rename it to NodeMemory.
Introduce NodeMemory inside NodeRuntime separately.
```

## 8. `Parcel` Should Not Be Renamed Blindly To `Artifact`

### Current Reed Mechanism

`Parcel` is a base class that stores provenance and version metadata.

It represents a published or publishable value transported through Reed and stored in `Depot`.

### Problem In Reed

The word `Artifact` now has a stronger conceptual meaning:

```text
Artifact identity == domain type
```

The current `Parcel` object is not only identity. It is closer to a versioned record or envelope.

### Recommendation

Move toward:

```text
ArtifactRecord[T]
```

or:

```text
ArtifactEnvelope[T]
```

Preferred:

```text
ArtifactRecord[T]
```

because the current object stores provenance and version metadata.

The conceptual mapping should be:

```text
DomainType
    semantic artifact identity

Domain value
    user-facing value

ArtifactRecord[DomainType]
    Reed-managed committed record containing value, version, provenance, and dependencies
```

This means `Artifact` should be used carefully.

It may be a conceptual term, a type alias, or a descriptor. It should not automatically replace every occurrence of `Parcel`.

## 9. `Depot` Should Become `ArtifactRepository`

### Current Reed Mechanism

`Depot` stores one latest Parcel per Parcel type and emits validity updates through the bus.

### External Pattern

Repository is a recognized architecture term for an authoritative access point to persisted domain records.

Dagster's asset model also uses a central asset/materialization store conceptually, even though its implementation terminology differs.

### Problem In Reed

`Depot` communicates storage, but it does not communicate authority.

The current class is the central source of truth for artifact records.

### Recommendation

Rename conceptually to:

```text
ArtifactRepository
```

This better matches the role:

```text
the authoritative store of committed artifact records for a Run or execution environment
```

The migration should include message names later:

```text
DepotGet -> ArtifactRepositoryGet
DepotSet -> ArtifactRepositoryCommit
DepotUpdate -> ArtifactRepositoryUpdate
DepotRegistry -> ArtifactRepositoryRegistration
```

This rename should be staged because these names are used across the bus protocol.

## 10. Function Argument Building Must Support Injected Parameters And Unwrapping

### Current Reed Mechanism

`Node._build_function_arguments()` reads consumed Parcels from `Outpost` and passes them directly to the user function.

The current public node boundary expects Parcel types.

### External Pattern

Apache Beam explicitly distinguishes element parameters from framework-injected parameters such as state, timers, timestamp, and window.

LangGraph distinguishes graph state from runtime context.

### Problem In Reed

After issue #2 and issue #3, the function invocation path must distinguish:

```text
dataflow arguments
    domain values unwrapped from artifact records

injected arguments
    NodeContext[MemoryType, OutputType]
```

### Recommendation

Introduce explicit parameter descriptors:

```text
DataflowParameter
InjectedContextParameter
ExternalParameter
```

The function invocation path should be based on descriptors, not on ad hoc positional construction.

Target:

```text
ArtifactRecord[InputType] -> unwrap -> InputType
NodeContext[MemoryType, OutputType] -> inject
function arguments -> call user function
OutputType -> wrap -> ArtifactRecord[OutputType]
```

This is one of the most important implementation changes.

## 11. Current Schema Generation Is Useful But Too Tied To Parcel Subclasses

### Current Reed Mechanism

`OutpostBuilder` dynamically creates a dataclass with consumed and produced Parcel fields.

`SchemaBuilder` then inspects dataclass fields and metadata to identify consumed and produced Parcels.

### Problem In Reed

This mechanism assumes that graph inputs and outputs are Parcel subclasses.

After issue #2, user Nodes should be written in domain types.

### Recommendation

Preserve the useful idea:

```text
compile a structural schema from typed declarations
```

but change the unit being described:

```text
from Parcel subclasses
to artifact type descriptors
```

Recommended target names:

```text
ArtifactSchema
ArtifactDescriptor
ArtifactRole
```

This allows Reed to keep strong internal schemas while removing Parcel boilerplate from user signatures.

## 12. Validation Should Move Earlier And Become More Architectural

### Current Reed Mechanism

`NodeDescriptionBuilder` validates function annotations and Parcel return shapes.

`DependencyRegistry` validates duplicate producers during registration.

### External Pattern

LangGraph validates schemas, node names, managed channels, duplicate branches, edge endpoints, and illegal graph structures during graph construction or compilation.

Apache Beam validates framework-injected parameter declarations when constructing special DoFn parameters.

### Problem In Reed

Some critical architectural problems should fail before execution:

1. duplicate artifact producer;
2. self-flow;
3. invalid `NodeContext`;
4. missing type annotations;
5. ambiguous output type;
6. invalid callback;
7. invalid trigger policy;
8. accidental use of context as dataflow input.

### Recommendation

Introduce a validation layer around:

```text
NodeDefinition validation
Flow composition validation
Run preparation validation
```

This gives clearer errors and prevents half-materialized runtime state.

Recommended examples:

```python
def invalid_self_flow(image: Image) -> Image:
    ...
```

should fail as:

```text
SelfFlowError: Node 'invalid_self_flow' consumes and produces Image.
Use distinct domain artifact types for distinct semantic stages.
```

And:

```python
def invalid_context(
    ctx: NodeContext[Memory, OtherOutput],
    value: Input,
) -> Output:
    ...
```

should fail as:

```text
NodeContextOutputMismatchError:
NodeContext output type OtherOutput does not match return type Output.
```

## 13. Output Commit And Callback Dispatch Should Be Split

### Current Reed Mechanism

`Node._write_function_result()` writes the function result through the `Outpost` transaction context.

Status propagation and processing are coupled to the same internal callback mechanism.

### External Pattern

Dagster and Prefect keep user hooks conceptually separate from the computation itself.

Prefect stores hooks as task options and dispatches them around state transitions.

### Problem In Reed

Reed needs a clear post-commit point:

```text
output has been produced and committed
```

Only after that point should `on_output` run.

### Recommendation

Split execution into explicit phases:

```text
NodeExecution
├── build arguments
├── execute user function
├── wrap output
├── commit artifact record
├── update memory / last output
└── dispatch on_output
```

This makes callback failure easier to classify:

```text
computation failure
commit failure
callback failure
```

These should not be represented as the same failure.

## 14. Local Memory Needs Its Own Object

### Current Reed Mechanism

Reed has local runtime fields and produced Parcel snapshots, but no explicit user-facing `NodeMemory` object.

### External Pattern

Flink and Beam both make stateful processing explicit in the programming model.

Ray actors also demonstrate the value of isolating mutable state inside an execution instance, rather than attaching it to a reusable function definition.

### Problem In Reed

Without `NodeMemory`, users may resort to global variables, closures, or forcing private algorithmic memory into public artifact flow.

### Recommendation

Add explicit memory support through:

```python
NodeContext[MemoryType, OutputType]
```

with:

```python
ctx.memory
ctx.last_output
```

`NodeMemory` should belong to:

```text
Run x NodeRuntime
```

not to:

```text
NodeDefinition
```

Stateful NodeRuntime firings should initially be serialized.

## 15. Error Types Should Become Part Of The Architecture

### Current Reed Mechanism

Reed already has specific errors such as `DuplicateProducerError` and `MissingDependencyError`.

### Problem In Reed

As the API becomes more explicit, errors should teach the user's mental model.

Generic `TypeError` and `RuntimeError` are sometimes enough for Python mechanics, but Reed's architectural errors should be named.

### Recommendation

Add explicit error classes for the new validation rules:

```text
DuplicateArtifactProducerError
SelfFlowError
NodeContextOutputMismatchError
MultipleNodeContextError
InvalidNodeContextError
InvalidOutputCallbackError
InvalidTriggerPolicyError
UnannotatedNodeParameterError
UnannotatedNodeReturnError
```

Good error names become documentation.

They also make tests clearer.

## 16. Module Layout Should Follow Architecture

### Current Reed Mechanism

The current packages are organized around:

```text
activation
composition
synchronization
transportation
```

These packages contain useful concepts, but some names no longer match the new architecture.

### Problem In Reed

The new architecture centers around:

```text
artifact
node
flow
run
repository
execution
observability
```

### Recommendation

Do not reorganize packages as the first step.

But new code should avoid deepening the old ambiguity.

Possible future layout:

```text
reed/
├── artifact/
│   ├── record.py
│   ├── provenance.py
│   ├── version.py
│   └── schema.py
├── node/
│   ├── definition.py
│   ├── context.py
│   ├── memory.py
│   └── signature.py
├── flow/
│   ├── flow.py
│   ├── flow_node.py
│   └── validation.py
├── run/
│   ├── run.py
│   ├── node_runtime.py
│   └── node_execution.py
├── repository/
│   ├── artifact_repository.py
│   └── messages.py
└── execution/
    ├── trigger_policy.py
    └── callbacks.py
```

This should be a later migration after the conceptual objects exist.

## 17. Recommended Refactoring Sequence

The safest sequence is:

1. Add tests describing the new public API and validation rules.
2. Introduce `TriggerPolicy` as an alias or successor to `PropagationPolicy`.
3. Introduce `OnOutputCallback` type aliases and callback validation.
4. Introduce `FlowNode`.
5. Add `Flow.add(...)` with keyword-only `trigger_policy` and `on_output`.
6. Make `Flow.add(...)` store composition metadata without changing the execution engine yet.
7. Introduce `NodeContext[MemoryType, OutputType]` and signature parsing for injected parameters.
8. Update argument building to unwrap domain values and inject context.
9. Add `NodeMemory` storage under the run-local execution path.
10. Add `last_output` tracking for committed outputs.
11. Split output commit from `on_output` dispatch.
12. Add architectural validation errors.
13. Introduce `ArtifactRecord` naming as a new internal concept or alias.
14. Rename `Depot` protocol gradually toward `ArtifactRepository`.
15. Rename or absorb `Outpost` only after `NodeRuntime` is explicit.

This sequence avoids a broad rename before the behavioral seams are visible.

## 18. Recommended First Test Scenarios

The first implementation tasks should be test-driven around behavior, not around renames.

Recommended tests:

1. `flow.add(node)` registers a typed Node and returns a `FlowNode`.
2. `flow.add(node, trigger_policy=policy)` stores policy on the `FlowNode`.
3. `flow.add(node, on_output=callback)` stores callback on the `FlowNode`.
4. callback positional ambiguity is not supported.
5. domain input annotations become artifact input descriptors.
6. domain return annotation becomes artifact output descriptor.
7. `NodeContext` parameter does not become an input descriptor.
8. `NodeContext[Memory, Output]` matching the return type is valid.
9. `NodeContext[Memory, OtherOutput]` with return type `Output` fails.
10. two producers of the same output domain type fail.
11. `InputType -> InputType` fails as self-flow.
12. user function receives domain values, not artifact records.
13. returned domain value is wrapped into an artifact record internally.
14. `ctx.memory` persists across firings in one `Run`.
15. `ctx.memory` is isolated across different `Run` instances.
16. `ctx.last_output` returns the latest committed output value.
17. `on_output` receives the committed domain output value.
18. `on_output` runs only after commit.
19. `on_output` failure does not undo the committed output.
20. stateful NodeRuntime firings are serialized.

## 19. Practical Before And After

### Current Direction

```python
@flow
class MyFlow:
    @node
    def process(data: InputParcel) -> OutputParcel:
        ...
```

This exposes infrastructure types at the user boundary and hides Flow composition inside decoration.

### Target Direction

```python
class RawImage(Image):
    ...

class DenoisedImage(Image):
    ...

@dataclass
class DenoiseMemory:
    previous_confidence: float | None = None

def denoise(
    ctx: NodeContext[DenoiseMemory, DenoisedImage],
    image: RawImage,
) -> DenoisedImage:
    ...

async def on_denoised(image: DenoisedImage) -> None:
    ...

flow = Flow()

denoise_node = flow.add(
    denoise,
    trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED,
    on_output=on_denoised,
)

run = flow.run()
```

This makes the architecture explicit:

```text
RawImage -> DenoisedImage
```

and:

```text
FlowNode
├── NodeDefinition: denoise
├── TriggerPolicy: ALL_INPUTS_CHANGED
└── on_output: on_denoised
```

## 20. Final Recommendation

Reed should not start issue #4 by renaming every file.

It should start by introducing the missing architectural seams:

```text
Flow.add(...)
FlowNode
TriggerPolicy
on_output
NodeContext
NodeMemory
ArtifactRecord
Run
NodeRuntime
NodeExecution
```

Renames should follow behavior.

The strongest implementation principle is:

```text
First make the boundary real.
Then rename the boundary.
```
