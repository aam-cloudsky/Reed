# Flow Composition Implementation Basis

This document records the implementation basis for Reed's explicit Flow composition API.

It consolidates the architectural decisions from the previous discussions about `Node`, `Flow`, `Run`, typed artifacts, automatic wrapping, `NodeContext`, local memory, output callbacks, trigger policies, and implementation vocabulary.

This document is intended to serve as a milestone for future task planning and implementation work.

## Implementation Thesis

Issue #4 should implement the architectural surface established by issues #1, #2, and #3.

The target public API should expose:

1. typed domain Nodes;
2. explicit Flow composition;
3. optional `NodeContext`;
4. per-node trigger policy configuration;
5. post-commit output callbacks.

The implementation should also start aligning the code vocabulary with Reed's conceptual model.

The central thesis is:

```text
Node definitions describe computation.
Flow explicitly defines composition.
Run owns execution.
Flow.add(...) creates a Flow-local Node participation.
TriggerPolicy decides when a Node participation should execute.
on_output observes committed Node outputs.
```

## Target Public API

The recommended target API is:

```python
flow = Flow()

flow.add(load_raw_image)

flow.add(
    denoise,
    trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED,
    on_output=show_denoised_image,
)

flow.add(save_result)

run = flow.run()
```

With `NodeContext` when a Node needs node-local computational continuity:

```python
@dataclass
class TrackerMemory:
    previous_confidence: float | None = None

def tracker(
    ctx: NodeContext[TrackerMemory, Estimate],
    measurement: Measurement,
) -> Estimate:
    previous = ctx.last_output

    result = update(
        previous=previous,
        memory=ctx.memory,
        measurement=measurement,
    )

    ctx.memory.previous_confidence = result.confidence

    return result.estimate

flow = Flow()

flow.add(
    tracker,
    trigger_policy=TriggerPolicy.ON_ANY_INPUT_CHANGED,
    on_output=publish_estimate,
)
```

The user-facing Node signature remains centered on domain types.

Reed derives the internal artifact model from those type annotations.

## Public API Decisions

### Use `Flow.add(...)`

Reed should use:

```python
flow.add(my_node)
```

rather than requiring:

```python
flow.add_node(my_node)
```

Inside a `Flow`, the object being added is already clear.

`add` keeps the API compact and matches the previous architectural direction:

```text
callable -> NodeDefinition -> Flow.add(...) -> FlowNode -> Flow.run()
```

### Keep `@node`

`@node` may remain useful as a computational declaration mechanism.

The important change is that `@node` should not imply lexical ownership by `@flow`.

The target relationship is:

```text
function
   │
optional @node
   │
   ▼
NodeDefinition
   │
Flow.add(...)
   │
   ▼
FlowNode
```

This preserves reusable Node definitions.

### Move `@flow` Out Of The Main API Path

`@flow` should no longer be the central public composition mechanism.

A Flow is not just a decorated function or decorated class. It is a first-class composition object that owns node participation, topology, configuration, validation, and execution entry points.

The explicit model is:

```python
flow = Flow()
flow.add(node_a)
flow.add(node_b)
flow.run()
```

`@flow` may remain temporarily for compatibility, but the target model is explicit composition.

## `Flow.add(...)`

`Flow.add(...)` should register a Node definition as a Flow-local participation.

Recommended shape:

```python
flow_node = flow.add(
    my_node,
    *,
    trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED,
    on_output=None,
)
```

The configuration arguments should be keyword-only.

This avoids ambiguous calls such as:

```python
flow.add(my_node, callback, trigger_policy)
flow.add(my_node, trigger_policy, callback)
```

Those forms are convenient but weaken readability and type-guided coding.

The recommended style is:

```python
flow.add(my_node)
flow.add(my_node, on_output=callback)
flow.add(my_node, trigger_policy=TriggerPolicy.ON_ANY_INPUT_CHANGED)
flow.add(my_node, trigger_policy=policy, on_output=callback)
```

## FlowNode

`Flow.add(...)` should return a `FlowNode`.

`FlowNode` represents one Node definition participating in one Flow.

This distinction matters because:

1. the same Node definition may participate in different Flows;
2. the same Node definition may eventually participate more than once in the same Flow;
3. local memory belongs to a NodeRuntime created from a Flow-local participation, not to the reusable Node definition;
4. callbacks and trigger policies belong to the Flow-local participation.

Conceptually:

```text
NodeDefinition
    reusable computation

FlowNode
    one participation of that computation inside one Flow

NodeRuntime
    one execution instance of that FlowNode inside one Run
```

The model is:

```text
NodeDefinition -> FlowNode -> NodeRuntime -> NodeExecution
```

## TriggerPolicy

Reed should use the term `TriggerPolicy`.

The policy decides when a `FlowNode` becomes eligible for execution after input artifact changes.

It should be configured at `Flow.add(...)` time:

```python
flow.add(
    denoise,
    trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED,
)
```

Recommended initial default:

```text
TriggerPolicy.ALL_INPUTS_CHANGED
```

The exact set of policies may evolve, but the conceptual boundary should be stable:

```text
TriggerPolicy decides execution eligibility.
on_output observes successful committed output.
```

These concepts must not be merged.

## Output Callback

The callback should be named `on_output`.

`callback` is too generic. `on_output` names the event that triggers it.

Recommended shape:

```python
def on_estimate(estimate: Estimate) -> None:
    ...

flow.add(tracker, on_output=on_estimate)
```

The callback should receive the domain output value by default, not the internal artifact record.

```text
on_output(output_value)
```

not:

```text
on_output(artifact_record)
```

This keeps the public API aligned with the automatic wrapping decision:

```text
User code sees domain values.
Reed internals manage artifact records.
```

### Callback Timing

`on_output` should run after a successful output commit.

Conceptually:

```text
Node executes
    │
    ▼
domain output value produced
    │
    ▼
Reed wraps output into internal artifact record
    │
    ▼
Reed commits artifact record
    │
    ▼
Reed invokes or schedules on_output(output_value)
```

The callback is observational.

It should not control:

1. graph routing;
2. retry decisions;
3. trigger policy evaluation;
4. shared state mutation;
5. artifact commit semantics.

### Callback Failure

Failure in `on_output` should not undo an already committed artifact.

Recommended initial rule:

```text
Node failure -> NodeExecution or Run failure.
on_output failure -> callback failure event.
```

The callback failure should be observable, but it should not rewrite the result of the Node computation.

### Async Callback Support

Reed should allow both synchronous and asynchronous output callbacks.

Conceptually:

```python
OnOutputCallback = (
    Callable[[OutputType], None]
    | Callable[[OutputType], Awaitable[None]]
)
```

Async callbacks are useful for UI updates, network calls, notifications, and integration with external systems.

Reed should preserve the core execution semantics:

```text
callback execution is a reaction to a committed output
```

not a hidden second dataflow engine.

## Typed Artifact Boundary

The issue #2 decision remains central.

The user-facing domain type is the artifact semantic identity:

```text
DomainType == Artifact semantic identity
```

Reed internally represents committed values as versioned artifact records.

The target public Node signature should be:

```python
def denoise(image: RawImage) -> DenoisedImage:
    ...
```

not:

```python
def denoise(image: Parcel[RawImage]) -> Parcel[DenoisedImage]:
    ...
```

Internally, Reed may use:

```text
ArtifactRecord[RawImage]
ArtifactRecord[DenoisedImage]
```

The key distinction is:

```text
Domain value != ArtifactRecord
Domain type == Artifact identity
ArtifactRecord == Reed-managed versioned record
```

## NodeContext Boundary

The issue #3 decision also remains central.

`NodeContext` is optional and injected by Reed.

It should be detected by type annotation and excluded from dataflow inputs:

```python
def tracker(
    ctx: NodeContext[TrackerMemory, Estimate],
    measurement: Measurement,
) -> Estimate:
    ...
```

The graph contract is:

```text
Measurement -> Estimate
```

The context exposes only:

```text
ctx.memory
ctx.last_output
```

The second type argument of `NodeContext` must match the return type exactly:

```text
ctx: NodeContext[TrackerMemory, Estimate]
return: Estimate
```

Mismatches must fail before execution:

```text
ctx: NodeContext[TrackerMemory, OtherThanEstimate]
return: Estimate
```

## Vocabulary Alignment

The implementation should move toward names that directly express Reed's architecture.

This should be done gradually, not as a blind global rename.

Recommended vocabulary:

| Current name | Recommended target | Rationale |
|---|---|---|
| `Parcel` | `ArtifactRecord` | The current object carries value, version, and provenance. It is closer to a versioned record than to the abstract artifact identity. |
| `ParcelVersion` | `ArtifactVersion` | Direct rename aligned with artifact vocabulary. |
| `ParcelProvenance` | `ArtifactProvenance` | Direct rename aligned with artifact vocabulary. |
| `Depot` | `ArtifactRepository` | The central store is the authoritative source for artifact records. |
| `Outpost` | `NodeRuntime` | The current class is closer to a runtime/synchronization instance of a Node than to local memory itself. |
| `PropagationPolicy` | `TriggerPolicy` | The policy decides when execution should be triggered after artifact changes. |
| `callback` | `on_output` | The name should describe the event that invokes the function. |
| `LocalState` | `NodeMemory` | `state` is overloaded; `memory` better communicates private persistent node-local information. |

### Important Distinction

`Outpost` should not be renamed to `LocalState` or `NodeMemory`.

`Outpost` currently represents a broader execution/synchronization unit.

Conceptually:

```text
NodeRuntime
├── NodeMemory
├── latest output reference
├── artifact cache / local view
├── repository communication
├── status tracking
├── transaction boundary
└── mutation guards
```

`NodeMemory` belongs inside `NodeRuntime`.

It does not replace `NodeRuntime`.

## Conceptual Boundaries To Make Explicit In Code

The implementation should avoid implicit coupling between concepts that are now distinct.

The important boundaries are:

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

These distinctions should appear in class names, type aliases, validation code, and tests.

## Validation Rules

The implementation should include strong validation at Node or Flow construction time.

Recommended initial validations:

1. A Node parameter without annotation is invalid.
2. A Node return type without annotation is invalid.
3. A `NodeContext` parameter is injected and must not become an `InputPort`.
4. A Node may declare at most one `NodeContext` parameter.
5. `NodeContext[MemoryType, OutputType]` must match the Node return type.
6. Two Nodes in the same Flow cannot produce the same artifact type.
7. A Node cannot consume and produce the same artifact type.
8. `trigger_policy` must be a valid `TriggerPolicy`.
9. `on_output`, when provided, must be callable.
10. `on_output` should be compatible with the produced output type.

## Implementation Strategy

The recommended strategy is incremental.

Issue #4 should not be implemented as one large rewrite.

Recommended order:

1. Introduce the explicit `Flow.add(...)` API.
2. Introduce `FlowNode` as the return value of `Flow.add(...)`.
3. Store `trigger_policy` and `on_output` on the `FlowNode`.
4. Preserve the existing decorator-based API temporarily, if needed.
5. Update Node signature parsing to separate dataflow inputs from injected `NodeContext`.
6. Add validation for `NodeContext[MemoryType, OutputType]` against the return type.
7. Add validation for duplicate producers and self-flow.
8. Add automatic wrapping and unwrapping between domain values and internal artifact records.
9. Introduce `NodeMemory` inside the Node execution path.
10. Introduce `ctx.last_output`.
11. Dispatch `on_output` after successful artifact commit.
12. Start vocabulary alignment with aliases or staged renames.

This order reduces risk because it first establishes the new public surface and validation model before replacing internal names.

## Recommended Non-Goals For The First Implementation Pass

The first implementation pass should not attempt to solve every future concern.

Recommended non-goals:

1. remove every old class name immediately;
2. expose repository access through `NodeContext`;
3. expose trace IDs, span IDs, node IDs, run IDs, or counters through `NodeContext`;
4. let callbacks control graph routing;
5. let callbacks mutate shared artifact state;
6. support multiple registrations of the same Node definition without an explicit identity design;
7. support complex callback contexts;
8. implement distributed execution;
9. implement full checkpoint/restore for `NodeMemory`;
10. implement advanced parallel scheduling for stateful Nodes.

These can be addressed later after the new API and vocabulary are stable.

## Relationship To Prior Work

The implementation direction is aligned with established systems and libraries:

1. LangGraph uses explicit graph construction with nodes and edges, which supports Reed's move toward `Flow.add(...)` and first-class composition.
2. Dagster separates computation from asset materialization, hooks, sensors, and orchestration concerns, which supports Reed's separation between Node computation and `on_output` observation.
3. Prefect supports state-change hooks and asynchronous Python workflow behavior, which supports narrow post-event callback semantics.
4. Apache Beam uses framework-injected function parameters for context-like capabilities, which supports Reed's `NodeContext` injection rule.
5. Apache Flink formalizes stateful operators in dataflow systems, which supports Reed's `NodeMemory` and serialized stateful NodeRuntime firings.

The most relevant scientific references are:

1. Derek G. Murray et al., "Naiad: A Timely Dataflow System", DOI: `10.1145/2517349.2522738`.
2. Paris Carbone et al., "Apache Flink: Stream and Batch Processing in a Single Engine", DOI: `10.1109/ICDE.2015.7066051`.
3. Tyler Akidau et al., "The Dataflow Model: A Practical Approach to Balancing Correctness, Latency, and Cost in Massive-Scale, Unbounded, Out-of-Order Data Processing", DOI: `10.14778/2824032.2824076`.
4. Tyler Akidau et al., "MillWheel: Fault-Tolerant Stream Processing at Internet Scale", DOI: `10.14778/2536222.2536229`.
5. Yadu Babuji et al., "Parsl: Pervasive Parallel Programming in Python", DOI: `10.1145/3307681.3325400`.

## Implementation Milestone

This document defines the implementation base for issue #4.

The issue can move to task planning once the following target is accepted:

```text
Implement explicit Flow composition around Flow.add(...), FlowNode, TriggerPolicy, on_output, typed artifact inference, NodeContext injection, and gradual vocabulary alignment.
```

The goal is not only to add API methods.

The goal is to make Reed's implementation reflect its conceptual architecture:

```text
Node -> Flow -> Run
Domain Type -> Artifact identity -> ArtifactRecord
FlowNode -> NodeRuntime -> NodeExecution
TriggerPolicy -> execution eligibility
on_output -> post-commit observation
NodeMemory -> node-local computational continuity
```

