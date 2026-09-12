# Reed
<p align="center">
  <img src="assets/reed-logo.svg" alt="Reed logo" width="320">
</p>

Reed is a reactive computation framework for coordinating interdependent transformations over ordinary, strongly typed Python values. Developers express computations as plain functions over domain types; Reed infers the dependencies between them, and automatically propagates change through the resulting graph until it settles, keeping every derived value consistent with minimal orchestration code.

Reed is named after the reed of a weaving loom—a comb-like structure that aligns, separates, and synchronizes warp threads as fabric is woven.

Likewise, Reed organizes strongly typed pieces of application state, automatically coordinating their dependencies and keeping the states synchronized.

---

## Installation

Using pip:

```bash
pip install reed
```

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

run = flow.run()
run.publish(Text("Hello Reed"))
```

Output:

```text
10
```

`Text` and `TextSize` are ordinary Python dataclasses -- Reed places no
base class or decorator requirement on domain types. A function's
parameter and return type annotations are enough for Reed to infer the
dependency between `compute`'s input and output; publishing a `Text`
automatically propagates through every eligible downstream node.

---

## Example

A complete example demonstrating fan-out, a multi-input join gated by a
`TriggerPolicy`, and automatic multi-hop propagation through a full
graph is available in:

```text
examples/text_analysis_pipeline.py
```

---

## Features
- Ordinary Python domain values -- no base class or decorator required.
- Explicit `Flow` composition (`flow.add(...)`) with automatic, type-inferred dependencies.
- Automatic, multi-hop reactive propagation: fan-out, multi-input joins, and repeated updates, driven by a single `run.publish(...)`.
- Per-node `TriggerPolicy` (any-input, all-inputs, or manual) governing execution eligibility.
- Optional `NodeContext` for node-local memory and access to the previous committed output.
- Post-commit `on_output` observation, isolated from execution.

---

## License

Reed is distributed under the Apache License 2.0.
