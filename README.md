# Reed
<p align="center">
  <img src="assets/reed-logo.svg" alt="Reed logo" width="320">
</p>

Reed is a reactive computation framework for coordinating interdependent transformations over ordinary, strongly typed Python values. Developers express computations as plain functions over domain types; Reed infers the dependencies between them, and automatically propagates change through the resulting graph until it settles, keeping every derived value consistent with minimal orchestration code.

Reed is named after the reed of a weaving loom—a comb-like structure that aligns, separates, and synchronizes warp threads as fabric is woven.

Likewise, Reed organizes strongly typed pieces of application state, automatically coordinating their dependencies and keeping the states synchronized.

---

## Installation

Reed requires Python 3.12 or later. It is not yet published on PyPI;
install it from a clone of this repository:

```bash
pip install .
```

The distribution name is `reed-sync`; the import name is `reed`.

---

## Quick Start

```python
from dataclasses import dataclass

from reed import Flow


@dataclass
class Text:
    value: str


@dataclass
class TextSize:
    value: int


def compute(text: Text) -> TextSize:
    return TextSize(len(text.value))


def show_size(size: TextSize) -> None:
    print(size.value)


flow = Flow()
flow.add(compute, on_output=show_size)

session = flow.session(observability="silent")
session.feed(Text("Hello Reed"))
session.push()
```

Output:

```text
10
```

`Text` and `TextSize` are ordinary Python dataclasses -- Reed places no
base class or decorator requirement on domain types. A function's
parameter and return type annotations are enough for Reed to infer the
dependency between `compute`'s input and output.

A `Session` is one execution of a `Flow`. `feed()` stores a value,
`push()` propagates every pending change through the eligible
downstream nodes until the graph settles, and `snapshot()` returns the
committed values. `invoke(value)` does `feed` -> `push` -> `snapshot`
in one call. `observability="silent"` turns off the default per-node
terminal output.

---

## Examples

The `examples/` directory contains runnable scripts:

- `text_analysis_pipeline.py`: fan-out, a multi-input join gated by a
  `TriggerPolicy`, and multi-hop propagation through a full graph.
- `sampled_inputs.py`: non-triggering (`Sampled`) inputs.
- `multi_instance_fleet_example.py`: multiple instances of the same
  type (`InstanceKey`) and fan-in through `Collective[T]`.
- `self_flow/`: feedback through a `Sampled` self-input (unit delay).
- `superstep/`: fan-out/fan-in, diamond joins, feedback loops and
  the barrier commit of each superstep.
- `observability_example.py`: tracing, instruments and provenance.

---

## Features

- Ordinary Python domain values -- no base class or decorator required.
- Explicit `Flow` composition (`flow.add(...)`) with dependencies
  inferred from type annotations.
- Automatic, multi-hop incremental propagation: fan-out, multi-input
  joins and repeated updates, driven by `session.feed(...)` and
  `session.push()`.
- Per-node `TriggerPolicy` (`ANY_INPUT_CHANGED`, `ALL_INPUTS_CHANGED`,
  `MANUAL`) governing execution eligibility.
- `Sampled` inputs that are read but do not trigger a node.
- Multiple instances per type (`InstanceKey`) and collective inputs
  (`Collective[T]`).
- Superstep execution with a barrier commit.
- Optional `NodeContext` for node-local memory and access to the
  previous committed output.
- Post-commit `on_output` observation, isolated from execution.
- Observability: structured logging, execution traces, provenance and
  optional OpenTelemetry export (`pip install ".[otel]"`).

---

## Authors

- Davi Guanabara de Aragão
- Cesar Augusto Cavalheiro Marcondes
- Filipe Alves Neto Verri
- Marcos Ricardo Omena de Albuquerque Máximo

Autonomous Computational Systems Lab (LAB-SCA), Aeronautics Institute of
Technology (ITA).

---

## License

Reed is distributed under the Apache License 2.0.
