# Issue 1 Architectural Decision

This document records the architectural decision for issue #1.

The decision is focused on Reed's public API and its conceptual boundaries. It does not introduce an implementation plan and does not imply changes to the current codebase by itself.

## Decision

Reed will move toward an API model that makes the separation between `Node`, `Flow`, and `Run` explicit.

The target model is:

```text
Node -> Flow -> Run
```

This means:

| Concept | Decision |
|---|---|
| `Node` | A reusable computational definition. |
| `Flow` | An explicit composition of nodes and their interaction topology. |
| `Run` | A concrete execution instance of a flow. |

The central design decision is:

```text
A node does not conceptually belong to a flow.
A node becomes part of a flow when the flow explicitly adds it to its topology.
```

This changes Reed's conceptual API direction from nested declaration to explicit composition.

## Current API Shape

The current style tends to define nodes lexically inside a flow:

```python
@flow
class MyFlow:
    @node
    def my_node(parcel1) -> parcel2:
        ...
```

This API shape makes the boundary between node definition, flow composition, and flow execution less explicit.

It can suggest that:

1. a node is owned by a flow definition;
2. the flow definition is also the execution object;
3. execution-specific state belongs directly to the flow.

Issue #1 resolves that these concepts should be separated.

## Target API Shape

The target API should be closer to explicit graph composition, similar in spirit to LangGraph's public builder style:

```python
def my_node(parcel1) -> parcel2:
    ...

my_flow = Flow()
my_flow.add(my_node)
my_flow.run()
```

A slightly more explicit version may look like:

```python
def source() -> ParcelA:
    ...

def transform(parcel: ParcelA) -> ParcelB:
    ...

flow = Flow()
source_ref = flow.add(source)
transform_ref = flow.add(transform)
flow.connect(source_ref, transform_ref)

run = flow.run()
```

The final public syntax may still evolve, but the boundary is decided:

```text
callable or @node -> NodeDefinition
Flow.add(...) -> flow-local participation
Flow.connect(...) -> topology
Flow.run(...) -> Run
```

The `@node` decorator may remain useful, but it should not require lexical ownership by `@flow`.

## Relationship To LangGraph

Reed's target API should be closer to the graph composition style used by LangGraph:

1. define computational capabilities independently;
2. add them to a graph or flow;
3. connect them explicitly;
4. execute the compiled or prepared graph.

The useful reference is the API boundary, not the agent architecture.

LangGraph models workflows through shared state, nodes, and edges. Reed should learn from that public shape while preserving its own identity: Reed coordinates interdependent computational artifacts, not only agent state transitions.

## Adopted Concepts

Reed will adopt the following conceptual boundaries.

### Node Definition

A `NodeDefinition` represents a reusable computational capability.

It may be created from:

1. a plain Python callable;
2. a callable annotated with `@node`;
3. a future explicit constructor such as `Node(...)`.

A node definition should not own execution state.

### Flow Composition

A `Flow` represents an explicit composition boundary.

It owns:

1. the set of node participations in the flow;
2. the topology between those participations;
3. the declared dependency or interaction structure;
4. the public execution entry point.

A flow should not own concrete execution state.

### Flow-Local Node Reference

When a node definition is added to a flow, Reed should create or return a flow-local reference.

This matters because the same node definition may eventually participate:

1. in multiple flows;
2. more than once in the same flow;
3. in multiple concurrent runs of the same flow.

The node definition is reusable. The flow-local reference identifies one participation in one flow topology.

### Run

A `Run` represents one concrete execution of a flow.

It owns execution-specific state, including:

1. shared state for that execution;
2. node runtime instances;
3. local state for each node runtime;
4. artifact versions created during the execution;
5. activation status;
6. event and message history;
7. execution traces.

This allows multiple runs of the same flow to execute independently.

### Node Runtime

A `NodeRuntime` represents one node participation materialized inside one run.

It is distinct from `NodeDefinition`.

This distinction prevents a reusable node definition from accidentally carrying state across unrelated executions.

### Node Execution

A `NodeExecution` represents one concrete execution attempt of a node runtime.

This concept is useful for:

1. retries;
2. provenance;
3. tracing;
4. failure reporting;
5. future parallel execution.

### Shared State

`SharedState` is scoped to one run.

It should not be described as global state. It is shared inside a concrete execution context, not across the whole Reed process by default.

### Local State

`LocalState` is scoped to:

```text
Run x NodeRuntime
```

It belongs to a node's participation in one run, not to the reusable node definition.

### Artifacts

Artifacts should be treated as first-class computational products.

State may contain references or metadata about artifacts, but large or persistent products do not need to live directly inside shared state.

### Artifact Change

Reed will use a simplified change model.

The conceptual separation is:

```text
Artifact Value != Artifact Delta != Artifact Version != Trigger Decision
```

Reed does not need full differential dataflow. A dirty marker is enough for the current scope if it is documented as a coarse approximation of a delta.

### Activation

Activation should be defined as the boundary between change detection and node execution.

The adopted rule is:

```text
Dirty does not mean execute now.
Dirty means an artifact may no longer be consistent.
Trigger policy decides when invalidation becomes execution.
```

Reed remains reactive by default. Demand-driven behavior may exist later as a policy, but it is not the primary identity of Reed.

### Notification

Reed should preserve external notification as a first-class behavior.

When an artifact changes or becomes stale, Reed may notify observers. A trigger policy can decide whether Reed executes downstream nodes eagerly, waits for an explicit request, or follows another policy.

This keeps Reed suitable for simulations where intermediate states matter, while preserving a future path for workloads that can skip intermediate states.

## Adopted References

The decision adopts concepts from the following references.

| Reference | Adopted concept |
|---|---|
| LangGraph official documentation | Public API style based on independent functions, explicit graph composition, and execution after graph construction. |
| Parsl | Separation between user function, dependency graph, execution coordinator, and executor. |
| Naiad | Causal ordering, logical execution progress, safe notification, and future grounding for parallel execution. |
| Differential Dataflow | Separation between value, version, delta, and propagation. |
| Adapton | Separation between dirtying, propagation, and execution demand. |

## Resulting Direction

The architectural direction for issue #1 is:

```text
Use explicit flow composition as the public API direction.
Make Run the owner of execution state.
Keep NodeDefinition reusable and independent from Flow.
Create flow-local node participation when a node is added to a Flow.
Separate invalidation from execution.
Keep Reed reactive by default.
Use trigger policy as the execution decision boundary.
Treat artifacts as first-class computational products.
Use academic and framework references as grounding, not as implementation templates.
```

## Ready-To-Post Issue Comment

The proposed resolution for this issue is to make Reed's public API reflect a clearer separation between `Node`, `Flow`, and `Run`.

The current nested declaration style can suggest that nodes belong to a flow definition and that the flow itself owns execution state. The direction we should move toward is explicit composition:

```python
def my_node(parcel1) -> parcel2:
    ...

flow = Flow()
flow.add(my_node)
flow.run()
```

Conceptually, a node should be an independently defined computational capability. A flow should compose nodes into an interaction topology. A run should represent one concrete execution of that flow and own execution-specific state.

The decided boundary is:

```text
NodeDefinition -> Flow Composition -> Run Context -> NodeRuntime -> NodeExecution
```

This direction is close to LangGraph's public composition style, where nodes are defined as functions, added to a graph, connected with edges, and executed after graph construction. Reed should adopt the API boundary, not LangGraph's agent assumptions.

This issue also clarifies related concepts:

```text
Artifact Value != Artifact Delta != Artifact Version != Trigger Decision
```

Reed should not implement full differential dataflow. Instead, Reed should document dirty status as a coarse approximation of a delta. Dirty means an artifact may no longer be consistent; it does not automatically mean immediate execution. Trigger policy is the boundary that decides when invalidation becomes execution.

Reed remains reactive by default. External notification is still first-class: Reed may notify observers when artifacts change or become stale. Future policies may support lazy or request-triggered execution, but that is a policy choice, not the default identity of the framework.

This resolution gives Reed a stronger conceptual model while keeping implementation scope controlled.

References used as conceptual grounding:

1. LangGraph official documentation, Graph API.
2. Parsl: Pervasive Parallel Programming in Python. DOI: 10.1145/3307681.3325400.
3. Naiad: A Timely Dataflow System. DOI: 10.1145/2517349.2522738.
4. Differential Dataflow. CIDR 2013.
5. Adapton: Composable, Demand-Driven Incremental Computation. DOI: 10.1145/2594291.2594324.

