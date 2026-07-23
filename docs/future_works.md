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