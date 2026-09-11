# Node Context Decision

This document records the conceptual decision for Reed's Node context, local memory, and previous output access.

The decision is focused on public Node signatures and execution semantics. It does not introduce an implementation plan by itself.

## Decision

Reed will introduce an optional `NodeContext` parameter for Nodes that need node-local computational continuity.

The target public shape is:

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
```

`NodeContext` is not a dataflow input.

It is injected by Reed and must be excluded from the inferred Flow topology.

The graph contract for the example above is:

```text
Measurement -> Estimate
```

not:

```text
NodeContext[TrackerMemory, Estimate] + Measurement -> Estimate
```

## Core Thesis

Reed Nodes may receive two different categories of function arguments:

```text
Node invocation
├── Reed-injected context
└── dataflow artifact values
```

The distinction is architectural:

```text
ctx != InputPort
measurement == InputPort[Measurement]
return == OutputPort[Estimate]
```

The context exists only to expose selected node-local computational continuity.

It should not expose Reed's internal execution objects.

## Strong Typing Rule

Reed will prefer the strongly typed form:

```python
def tracker(
    ctx: NodeContext[TrackerMemory, Estimate],
    measurement: Measurement,
) -> Estimate:
    ...
```

over the shorter form:

```python
def tracker(
    ctx: NodeContext[TrackerMemory],
    measurement: Measurement,
) -> Estimate:
    ...
```

Even though Reed can infer the output type at Flow construction time, Python's static type system cannot generally infer a generic argument of one parameter from the return annotation of the same function.

Reed can read the full signature:

```text
ctx: NodeContext[TrackerMemory, Estimate]
measurement: Measurement
return: Estimate
```

and derive:

```text
memory type: TrackerMemory
input artifact: Measurement
output artifact: Estimate
previous output type: Estimate | None
```

The repetition of `Estimate` is acceptable because Reed values explicit typing over implicit convenience.

The `NodeContext` output type must match the Node return type exactly.

This is valid:

```text
ctx: NodeContext[TrackerMemory, Estimate]
measurement: Measurement
return: Estimate
```

This is invalid:

```text
ctx: NodeContext[TrackerMemory, OtherThanEstimate]
measurement: Measurement
return: Estimate
```

Reed must raise an error during Node or Flow construction and prevent execution.

The second type argument of `NodeContext` exists to make `ctx.last_output` statically visible as `Estimate | None`. If it diverges from the declared return type, the signature becomes internally inconsistent:

```text
ctx.last_output refers to the previous output of this NodeRuntime.
The previous output of this NodeRuntime must have the same type as the current output artifact.
```

The guiding rule is:

```text
If a type relation matters to the user while coding, it should be visible to the type checker.
```

## NodeContext Scope

`NodeContext` is a controlled public interface.

It is not:

1. the internal `NodeRuntime`;
2. the internal `Outpost`;
3. the `Flow`;
4. the `Run`;
5. the `Repository`;
6. the `Bus`;
7. a general service locator.

The initial public capabilities should be limited to:

```text
ctx.memory
ctx.last_output
```

Other execution metadata should remain internal until a concrete user-facing need justifies exposing it.

This includes:

```text
trace_id
span_id
run_id
node_id
execution_count
attempt_count
scheduler details
repository access
bus access
```

These values are useful for Reed's observability, retries, logging, diagnostics, and execution control. They are not currently justified as part of the user-facing computational API.

## Memory

`ctx.memory` is the user-defined private memory owned by one `NodeRuntime` inside one `Run`.

Conceptually:

```text
Memory = Memory(NodeRuntime, Run)
```

The same Node definition may participate in different Runs, but the memory instances must remain independent:

```text
same Node definition
├── Run #1 -> NodeRuntime #1 -> Memory #1
└── Run #2 -> NodeRuntime #2 -> Memory #2
```

This preserves Run isolation.

`memory` is intentionally preferred over `state`.

The term `state` is already overloaded in Reed and related systems:

1. shared state;
2. run state;
3. lifecycle state;
4. artifact validity state;
5. graph state;
6. local state.

The word `memory` better communicates the intended meaning:

```text
private persistent information used by this NodeRuntime across firings in one Run
```

Example:

```python
@dataclass
class FilterMemory:
    covariance: Matrix
    initialized: bool = False

def filter_measurement(
    ctx: NodeContext[FilterMemory, Estimate],
    measurement: Measurement,
) -> Estimate:
    ...
```

## Last Output

`ctx.last_output` is the latest committed domain value produced by the same `NodeRuntime`.

It is not the same concept as `ctx.memory`.

```text
memory
    private mutable memory owned by this NodeRuntime

last_output
    latest committed output value produced by this NodeRuntime
```

They may be related in some algorithms, but Reed should keep them conceptually separate.

For example:

```python
@dataclass
class TrackerMemory:
    covariance: Matrix

def tracker(
    ctx: NodeContext[TrackerMemory, Estimate],
    measurement: Measurement,
) -> Estimate:
    previous_estimate = ctx.last_output
    covariance = ctx.memory.covariance

    result = update(previous_estimate, covariance, measurement)

    ctx.memory.covariance = result.covariance

    return result.estimate
```

The previous estimate is the last committed output artifact value.

The covariance is private computational memory.

Both influence the next execution, but they have different ownership and persistence semantics.

## Formal Interpretation

A stateless Node can be described as:

```text
f(x) -> y
```

A state-aware Node can be described as:

```text
f(c; x) -> y
```

where:

```text
c = Reed-injected NodeContext
x = dataflow input value
y = dataflow output value
```

When memory is considered directly, the Node behaves like a local state machine:

```text
(memory_next, y) = f(memory_current, last_output, x)
```

This is different from a pure function:

```text
y = f(x)
```

Reed should treat this distinction explicitly because it affects retries, replay, checkpointing, testing, and future parallel execution.

## Context Injection Rule

Reed should detect `NodeContext[...]` by type annotation.

The recommended convention is to place it first:

```python
def node(
    ctx: NodeContext[MemoryType, OutputType],
    input_value: InputType,
) -> OutputType:
    ...
```

But the semantic rule should be based on the annotation, not only on parameter position.

This avoids fragile positional magic.

The following must be true:

```text
NodeContext parameters are Reed-injected parameters.
Domain-typed parameters are dataflow input ports.
```

## Transaction Semantics

For Nodes with memory, Reed should eventually treat memory updates and output publication as one logical firing result.

Conceptually:

```text
begin firing
    read current memory
    read last committed output
    unwrap input Parcels
    execute user function
    obtain updated memory
    obtain output value
    wrap output value into Parcel
commit firing
    persist memory update
    publish output Parcel
```

This matters for failure and retry behavior.

If a firing fails, Reed should not leave partially committed memory changes that do not correspond to a committed output.

The desired rule is:

```text
failed firing -> no committed memory transition and no committed output
successful firing -> memory transition and output publication commit together
```

This rule may require implementation work beyond the first public API, but the conceptual boundary should be recorded now.

## Concurrency Rule

A state-aware `NodeRuntime` should initially execute at most one firing at a time.

This prevents lost updates to `ctx.memory`.

For example:

```text
memory = M0

firing A reads M0
firing B reads M0

firing A writes M1
firing B writes M2
```

Without serialization or transactional conflict detection, one memory transition can overwrite another.

The initial rule should be:

```text
If a Node declares NodeContext, its NodeRuntime firings are serialized.
```

Stateless Nodes may still be candidates for parallel execution when their artifact dependencies allow it.

## Relationship To Existing Reed Concepts

The current Reed architecture already contains concepts close to this decision.

`Outpost` already has:

1. node identity;
2. synchronized Parcel access;
3. produced Parcel snapshots;
4. status tracking;
5. a transaction boundary;
6. controlled mutation flags.

The decision here is not to expose `Outpost` directly.

Instead, Reed should expose a smaller public capability object:

```text
Outpost / NodeRuntime internals
        │
        ▼
NodeContext[MemoryType, OutputType]
        │
        ▼
user Node function
```

This preserves Reed's ability to evolve its internal implementation while giving user Nodes a stable, strongly typed way to access local continuity.

## Relationship To Prior Work

This decision is aligned with established systems while preserving Reed's own identity.

LangGraph exposes graph execution context separately from graph state. Its node functions can receive runtime information through a dedicated runtime parameter, and its graph model distinguishes state, nodes, edges, and compilation checks.

Dagster exposes an execution context object to ops and assets as a controlled interface for system information such as resources, config, logging, asset keys, and metadata.

Prefect exposes task and flow run contexts, but its internal context models are explicitly treated as framework-managed context rather than arbitrary user-mutated state.

Apache Beam provides a strong precedent for framework-injected parameters in user functions. Beam `DoFn` methods can receive special parameters such as timestamp, window, pane information, state, and timers. These parameters are supplied by the framework, not by normal pipeline data.

Apache Flink provides the strongest conceptual precedent for local memory. It distinguishes stateless operations from stateful operations, and makes the framework aware of operator state so that checkpointing, recovery, and rescaling can be handled safely.

The Flink paper reinforces the idea that many continuous, iterative, and real-time applications can be expressed as fault-tolerant dataflows where operators may keep state across records.

Relevant references:

1. Tyler Akidau et al., "MillWheel: Fault-Tolerant Stream Processing at Internet Scale", DOI: `10.14778/2536222.2536229`.
2. Tyler Akidau et al., "The Dataflow Model: A Practical Approach to Balancing Correctness, Latency, and Cost in Massive-Scale, Unbounded, Out-of-Order Data Processing", DOI: `10.14778/2824032.2824076`.
3. Derek G. Murray et al., "Naiad: A Timely Dataflow System", DOI: `10.1145/2517349.2522738`.
4. Paris Carbone et al., "Apache Flink: Stream and Batch Processing in a Single Engine", DOI: `10.1109/ICDE.2015.7066051`.

## Adopted Concepts

Reed adopts the following concepts for this issue:

1. `NodeContext` exists as an optional Reed-injected parameter.
2. `NodeContext` is identified by type annotation.
3. `NodeContext` is not a dataflow input and must not become an `InputPort`.
4. `NodeContext` should be strongly typed as `NodeContext[MemoryType, OutputType]`.
5. The `OutputType` in `NodeContext[MemoryType, OutputType]` must exactly match the Node return type.
6. Reed must reject mismatched `NodeContext` output type and return type before execution.
7. `ctx.memory` exposes private user-defined memory for one `NodeRuntime` inside one `Run`.
8. `ctx.last_output` exposes the latest committed domain output value for that same `NodeRuntime`.
9. Execution metadata remains internal until a concrete public use case justifies exposing it.
10. User code must not receive `Outpost`, `NodeRuntime`, `Run`, `Flow`, `Repository`, or `Bus` directly.
11. Stateful Nodes should initially have serialized firings per `NodeRuntime`.
12. Memory transition and output publication should be treated as one logical firing result.
