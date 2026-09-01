# Future Work
# Reed Publication Roadmap

## 1. Compare Reed with Shiny

Study the Shiny programming model and evaluate similarities and differences with Reed.

The objective is to identify architectural ideas that may improve Reed before the first public release.

---

## 2. Stabilize the Architecture

- Consolidate the architectural vocabulary.
- Refine layer boundaries.
- Reorganize internal modules.
- Improve internal naming.
- Strengthen layer isolation.

---

## 3. Consolidate the Public API

Prepare the first stable public API.

Goals:

- simple imports;
- consistent naming;
- stable decorators;
- stable Flow API.

---

## 4. Improve Developer Tooling

Implement introspection features such as:

- graph visualization;
- node description;
- execution layers;
- debugging utilities.

---

## 5. Documentation

Produce the first complete documentation.

Recommended documents:

- Installation
- Quick Start
- Tutorials
- API Reference
- Computational Model
- Architecture
- Comparison with existing systems

---

## 6. Publish the Library

Prepare Reed for public distribution.

Tasks include:

- semantic versioning;
- PyPI publication;
- GitHub Releases;
- license definition;
- README;
- contribution guidelines;
- continuous integration.

---

## 7. Software Registration

Prepare the software for long-term archival and citation.

Possible actions include:

- assigning a permanent identifier (DOI);
- archiving the source code;
- registering the released version;
- preserving reproducibility through versioned releases.

---

## 8. Scientific Publication

Prepare the first scientific paper describing Reed.

Topics include:

- computational model;
- architectural layers;
- dependency inference;
- synchronization model;
- comparison with related systems;
- case studies;
- performance evaluation.





## 0. Compare Reed with Shiny

Study the Shiny programming model and evaluate similarities and differences with Reed.

Topics of interest include:

- reactive programming model;
- dependency tracking;
- invalidation and recomputation;
- execution model;
- state management;
- developer API;
- graph construction;
- visualization and debugging tools.

The objective is not to reproduce Shiny, but to identify architectural ideas and determine whether any concepts can improve Reed's computational model or developer experience.

---

## 1. Consolidate the Architectural Vocabulary

Review and stabilize the terminology adopted by Reed.

Concepts under evaluation:

- Depot
- Outpost
- Parcel

The remaining architectural concepts are considered stable:

- Transport
- Synchronization
- Activation
- Composition
- Flow
- Node
- Port
- Bus
- Message

---

## 2. Refine Layer Boundaries

Strengthen the separation between architectural layers.

The intended dependency hierarchy is:

```text
Composition
      ↓
Activation
      ↓
Synchronization
      ↓
Transport
```

Each layer should depend only on the layer immediately below it.

---

## 3. Reorganize Internal Modules

Review the current package organization to better reflect architectural responsibilities.

Goals include:

- improving file organization;
- grouping related concepts together;
- reducing unnecessary package nesting;
- separating implementation details from public APIs.

---

## 4. Consolidate the Public API

Expose only the public concepts of each layer through `__init__.py`.

The goal is to make Reed feel like a cohesive library:

```python
from reed import Parcel
from reed import flow, node, input, output
```

instead of:

```python
from reed.synchronization.parcel.parcel import Parcel
```

Internal modules should remain hidden from library users.

---

## 5. Improve Internal Naming

Review file and package names to eliminate redundant structures such as:

```text
outpost/
    outpost.py

flow/
    flow.py

node/
    node.py
```

The internal organization should clearly reflect architectural responsibilities while keeping imports concise.

---

## 6. Strengthen Layer Isolation

Ensure that implementation details do not leak across architectural boundaries.

This includes:

- reducing unnecessary imports between layers;
- avoiding upward dependencies;
- exposing only stable abstractions;
- clearly separating public and private APIs.

---

# Introspection and Developer Tooling

## 7. Graph Visualization

Provide a built-in mechanism to inspect the graph automatically inferred from the flow definition.

Example:

```python
flow.show_graph()
```

Possible terminal output:

```text
RawText
   │
   ├────────► Normalize ─────────► ContainsPython
   │
   └────────► Tokenize ───────────► Statistics
                                  │
                                  ▼
                               Analysis
                                  │
                                  ▼
                                Output
```

Future formats may include:

- Graphviz (`.dot`)
- Mermaid
- SVG
- Interactive visualization

---

## 8. Node Introspection

Allow inspection of the inferred definition of each node.

Example:

```python
flow.describe()
```

Output:

```text
Node: statistics

Consumes
    Tokens

Produces
    Statistics

Activation Policy
    AnyDependencyChanged
```

---

## 9. Execution Layers

Display the inferred execution topology of the graph.

Example:

```text
Layer 0
    build_report

Layer 1
    tokenize
    normalize

Layer 2
    statistics
    contains_python

Layer 3
    merge

Layer 4
    show
```

This information is useful for understanding execution order, dependency structure, and potential parallelism.

---

## 10. Documentation

Produce the first complete version of the architectural documentation.

Recommended documents include:

- Terminology
- Computational Model
- Transport Layer
- Synchronization Layer
- Activation Layer
- Composition Layer
- Dependency and Materialization Model
- Architectural Comparison

The documentation should explain the architectural concepts independently of the implementation and establish Reed's computational model in relation to existing systems such as ROS 2, Blackboard Systems, Salsa, Hamilton, Dagster, and Flow-Based Programming.




## Future Work — Asynchronous Distributed Coordination

Eu descreveria como uma evolução futura do Reed para concorrência de escrita com arbitragem centralizada, sem ainda falar em rollback. Algo assim:

Concurrent Multi-Writer Parcels

Reed could evolve to allow multiple Outposts to write to the same Parcel while preserving the Depot as the centralized and authoritative source of truth.

Currently, a Parcel has a single well-defined producer. In the proposed model, multiple Outposts could submit concurrent state changes to the same Parcel.

Outpost A ──┐
            │
Outpost B ──┼──► Parcel X @ Depot
            │
Outpost C ──┘

Writes would not become visible immediately. Instead, each Outpost would submit a proposed state transition to the Depot. The Depot would atomically arbitrate competing writes and only committed state would be propagated through the dataflow.

Each Parcel could maintain a monotonically increasing revision:

Parcel X
revision 17: FREE
revision 18: ALLOCATED
revision 19: RELEASING
revision 20: FREE

An Outpost attempting to modify the Parcel would submit both the proposed value and the revision on which the operation is based:

Outpost A:
    expected_revision = 17
    proposed_value = ALLOCATED_BY_A
Outpost B:
    expected_revision = 17
    proposed_value = ALLOCATED_BY_B

If both operations race, the Depot establishes the authoritative ordering. The first operation successfully committed changes the Parcel:

X: revision 17 → revision 18

The competing operation is then rejected because its expected revision no longer matches the current state:

expected_revision = 17
current_revision  = 18
→ write rejected

This follows a first-commit-wins optimistic concurrency model, similar to compare-and-swap semantics.

Importantly, concurrency would be scoped to individual Parcels. Independent state could still evolve concurrently:

Outpost A ──► Parcel X
Outpost B ──► Parcel Y
Outpost C ──► Parcel Z

Only competing writes to the same Parcel revision require arbitration.

A fundamental consistency rule would be:

Only committed Depot state may propagate.

Therefore, rejected writes never enter the propagation graph. This avoids the need for rollback or backtracking in the initial implementation.

Conceptually:

                 ┌── proposed write ── Outpost A
                 │
                 │
              Depot
          authoritative state
                 │
          atomic commit
            /         \
       accepted      rejected
          │
          ▼
     propagation
          │
     ┌────┼────┐
     ▼    ▼    ▼
    O1   O2   O3

This mechanism would enable Reed to model shared-resource coordination, reservation systems, concurrent multi-agent environments, and dynamic resource allocation while retaining a centralized Depot as the single source of truth.

A later, more advanced model could allow speculative propagation, where Outposts act before a write is committed. That extension would require version tracking, invalidation, rollback, and recomputation. It should therefore be considered separately from the initial multi-writer concurrency model.

Acho que essa formulação captura exatamente a ideia sem transformar o Reed prematuramente em um sistema distribuído: o Depot continua centralizado; o novo problema é concorrência sobre estado compartilhado, não consenso distribuído.

Os nós teriam que atualziar também a versão do parcel que eles produzem para a versão do depot.