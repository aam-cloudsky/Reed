
## Design Principles
- State-oriented: Computation revolves around synchronized states rather than direct communication.
- Declarative: Dependencies are described rather than manually orchestrated.
- Incremental: Only affected computations are recomputed.
- Event-driven: State evolution is triggered by events rather than queries.
- Strongly Typed: Artifacts and dependencies are statically defined.
- Layered: Transport, synchronization, computation and dataflow remain independent concerns.

## Architecture
Layer 1
How does information move?

Layer 2
What is the shared truth?

Layer 3
What must be recomputed?

Layer 4
How is computation described?


                 Reed

       4. Declarative Dataflow Composition
                 ▲
                 │
      3. Incremental Activation
                 ▲
                 │
      2. Shared-State Synchronization
                 ▲
                 │
       1. Message Transport





## Layer 1: Transport - How does information move?
Deliver information.

Publisher-Subscriber pattern:
- Bus: Message Hub, Broker, Registry...
- End point here is Port.
- Point to Point (Direct) Connection
- Split-Phase: process-postprocess defer-flush


### Taxonomy:

| ROS 2 | Reed |
|--------|------|
| Message | Message (`BaseMessage`) |
| Topic | Topic |
| Node | Node (Unit) |
| Middleware | Bus |
| Publisher | Port (Publisher Endpoint) |
| Subscriber | Port (Subscriber Endpoint) |
| Lifecycle | Node (Unit) Lifecycle (`bind`, `unbind`, `close`) |


What about the split phase deffer-flush ?

### Split-Phase protocol (Open Research Question)
Transactional Message Delivery
Transactional Message Delivery

* command buffering
* deferred event dispatch
* event batching
* transactional event bus
* staged event-driven architecture (SEDA)

the gol is consistency:

I want to avoid:
'''
Node A publish

↓

Node B receives imediatamente

↓

Node A ainda está executando
'''

Therefore, it is a kind of temporal fence, or 


'''

Node A publish a query
↓

Begin new transaction

↓

Node B process incomming message

↓

defer the result

↓

End transaction

↓

flush()

↓

Node B publish a answer (to the node a query) (post-processing)

↓

Begin new transaction
...
'''

## Layer 2: Synchronization - What is the shared truth?
maintain shared state

This layer is responsible for maintaining a globally consistent shared state. Every node interacts with the Depot through an Outpost, which provides a synchronized local interface while preserving centralized consistency.

- Depot-Outpost system
- Endpoint: Outpost
- Centrilized Repository: Depot
- Star Topology connection
- Shared State system
- State: set of parcels


### Taxonomy:

| Blackboard | Reed |
|------------|------|
| Shared Knowledge Base | Depot |
| Knowledge Source | Node (Unit) |
| Blackboard Entry | Parcel |
| Local Access Interface | Outpost |
| Shared State | Depot State (Set of Parcels) |
| Control Component | Dirty Flags + Dependency Evaluation + Propagation Policy|
| Activation Condition | Dependency + Validity |


| Dagster | Reed |
|----------|------|
| Asset | Parcel |
| Asset Definition | Parcel Descriptor |
| Asset Dependency | Parcel Dependency |
| Materialization | Parcel Update |
| Asset Graph | Parcel Dependency Graph |
| Asset Check | Validity Policy |
| Asset Store | Depot |



Dagster: dependências centradas nos artefatos
O Dagster possui o conceito de software-defined asset: uma definição combina a identidade de um artefato com a função capaz de produzi-lo. O grafo é fortemente orientado pelos dados materializados, não apenas pelas tarefas executadas.

Dagster Skyweaver

assets parcels

## Layer 3: Incremental Activation - Once a state change, what must be recomputed?
maintain consistency


- Node (unit): consumer-producer pattern. transform input parcel into output parcel by 'process call'. Automatically trigged by dirty flags and Propagation Policy.
- Status: dirty flags
- Dependency Descriptors
- Role: Consumed, Produced.. (parcel tag as being consumed, produced...)
- Parcel Versioning: provenance
- Schema:
    It contains two complementary projections:

    - types_by_role:
        Groups every declared element according to its synchronization role
        (CONSUMED, PRODUCED, MUTATES).

    - descriptors:
        Structural descriptors of every declared element.

        Produced elements record their dependency graph, whereas consumed
        and mutated elements have an empty dependency set.

O Salsa  é um framework para computações incrementais e sob demanda: entradas mudam, o sistema rastreia dependências entre consultas, reutiliza resultados válidos e recalcula somente o que for necessário. Sua origem está ligada às técnicas de recompilação incremental usadas pelo compilador Rust.

Salsa: lazy

only computes when a state is asked

Reed: eager
automatically recomputing



Reed: Recomputation is triggered exclusively by dirty state propagation.

## Taxonomy

| Salsa | Reed |
|--------|------|
| Input | Input Parcel |
| Tracked Function | Node `process()` |
| Query Dependency | Parcel Dependency |
| Memoized Result | Produced Parcel |
| Revision | Dirty Flag |
| On-demand Recomputation (Lazy Propagation - query-driven) | Automatic recomputation (eager propagation - event driven) |
| Database | Depot |



## Comparation

Salsa 

Reed

Query-driven incremental computation

Event-driven incremental computation

Pull-based evaluation

Push-based propagation

Lazy recomputation

Reactive propagation

Memoized queries

Synchronized artifacts


Salsa.
Make.
Bazel.



## Layer 4: Dataflow Composition - How is computation described?
describe computation

- Flow: Declarative composition of producers and consumers into a dataflow graph.
- Decorator API.

Flow-Based Programming define aplicações como redes de processos independentes, conectados externamente e trocando pacotes de informação por portas nomeadas. A configuração das conexões é separada da implementação dos processos. 


### Taxonomy:
| Flow-Based Programming | Reed |
|------------------------|------|
| Process | Node (Unit) |
| Information Packet | Parcel |
| Input/Output Port | Outpost |
| Connection | Depot Synchronization mechanism |
| Network | Flow |

Each function can be seen as a node.



### Reed vs. Flow-Based Programming

Flow-Based Programming (FBP) connects independent processes through explicit input and output ports. Data is transmitted as packets over point-to-point connections, and each process communicates only through its ports. The network topology is therefore defined by the connections established between process ports.

Reed adopts a different computational model. Instead of connecting nodes directly, every node interacts with a synchronized shared state through an Outpost. Nodes consume and produce typed Parcels, while the Depot maintains the globally consistent state. Dependencies are defined between Parcels rather than between nodes, allowing the runtime to automatically detect invalid data, propagate changes, and perform incremental recomputation.

Consequently, while FBP is connection-oriented, Reed is artifact-oriented. In FBP, the primary abstraction is the flow of packets between ports. In Reed, the primary abstraction is the evolution of synchronized artifacts (Parcels) and the dependency graph that relates them.

In other words, Flow-Based Programming models communication between processes, whereas Reed models the evolution of shared synchronized knowledge through incremental data transformations.





# Architectural Comparison with Existing Models

## Dimensions

The comparison presented in this document is based on a set of architectural dimensions that characterize how each system organizes computation, state management, and coordination. Rather than comparing implementation details or APIs, these dimensions capture fundamental design decisions that distinguish different execution models.

### Trigger Design

Describes the fundamental paradigm that initiates computation.

- **Event-driven:** Computation is initiated by events or state changes.
- **Query-driven:** Computation is initiated only when a result is explicitly requested.

---

### Execution Trigger

Describes the runtime mechanism responsible for triggering computation.

Typical execution triggers include:

- Topic or message arrival
- Scheduler or orchestration component
- Query evaluation
- Dirty-state propagation

Two systems may share the same trigger design while relying on completely different execution triggers.

---

### Dependency Model

Describes how computational dependencies are represented.

- **Explicit:** Dependencies are declared as part of the computational model and are available for runtime analysis.
- **Implicit:** Dependencies emerge from runtime interactions and are not explicitly represented.

Explicit dependency models enable dependency analysis, automatic scheduling, and incremental recomputation.

---

### Propagation Strategy

Describes when dependent computations are executed after a state change.

- **Automatic:** Dependent computations are automatically propagated by the runtime.
- **Lazy:** Recomputation is postponed until the corresponding result is requested.

---

### Execution Model

Describes how computation is coordinated in time.

- **Synchronous:** State transitions occur within coordinated execution boundaries, preserving deterministic consistency.
- **Asynchronous:** Components execute independently and coordinate through message passing without global synchronization.

---

### State Ownership

Describes where the authoritative application state resides.

- **Single Source of Truth:** The system maintains a single authoritative shared state.
- **Multiple Sources of Truth:** Each component maintains its own local state, synchronized only through communication.

---

### Execution Scope

Describes the scope over which computational consistency is maintained.

- **Global:** The runtime maintains consistency across the entire application state.
- **Local:** Each component is responsible only for its own local execution context.

---

### Interaction Architecture

Describes how computational components exchange information.

- **Direct Connections:** Components communicate directly with one another.
- **Shared Repository:** Components communicate indirectly through a centralized shared state.

This dimension distinguishes connection-oriented architectures from repository-oriented architectures.

---

### State-centric Design

Describes whether the architecture is fundamentally organized around the evolution of shared state.

- **Yes:** State is the primary architectural abstraction, and computation exists primarily to transform and synchronize it.
- **Partial:** State plays a significant role, but other abstractions (e.g., assets or queries) are equally fundamental.
- **No:** Computation is primarily organized around communication or execution rather than shared state.

| Model | Trigger Design | Execution Trigger | Dependency Model | Propagation Strategy | Execution Model | State Ownership | Execution Scope | Interaction Architecture   | State-centric Design |
|--------|----------------|-------------------|------------------|----------------------|-----------------|-----------------|-----------------|----------------------------|----------------------|
| ROS 2 | Event-driven | Topic/Event | Implicit | Automatic | Asynchronous | Multiple Sources of Truth | Local | Direct Connections | No |
| Blackboard | Event-driven | Scheduler / Control Component | Implicit | Automatic | Synchronous | Single Source of Truth | Global | Shared Repository | Yes |
| Dagster | Event-driven | Scheduler | Explicit | Automatic | Asynchronous | Single Source of Truth | Global | Shared Repository | Partial |
| Salsa | Query-driven | Query Evaluation | Explicit | Lazy | Synchronous | Single Source of Truth | Global | Shared Repository | Partial |
| Flow-Based Programming | Event-driven | Stream | Explicit | Automatic | Asynchronous | Multiple Sources of Truth | Local | Direct Connections | No |
| **Reed** | Event-driven | Dirty Propagation | Explicit | Automatic | Synchronous | Single Source of Truth | Global | Shared Repository | Yes |






