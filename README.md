# Reed
<p align="center">
  <img src="assets/reed-logo.svg" alt="Reed logo" width="320">
</p>

Reed is an incremental state synchronization engine for declarative dataflow applications. It allows developers to express computations as transformations over strongly typed state. Reed automatically infers dependencies between computations and incrementally propagates updates, keeping the application state consistent with minimal user-defined orchestration.

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
from reed import Parcel, flow, input, node, output


@dataclass
class MyTextCarrier(Parcel):
    text: str

@dataclass
class TextSizeCarrier(Parcel):
    size: int


@flow
class SizeCounterFlow:

    @input
    def receive(self, text: str) -> MyTextCarrier:
        return MyTextCarrier(text)

    @node
    def compute(self, my_text_wrapper: MyTextCarrier) -> TextSizeCarrier:
        return TextSizeCarrier(len(my_text_wrapper.text))

    @output
    def result(self, text_size_carrier: TextSizeCarrier) -> int:
        return TextSizeCarrier.size


flow = SizeCounterFlow()
print(flow("Hello Reed"))
```

Output:

```text
10
```



---

## Example

A complete example demonstrating multiple flows, synchronization, and flow composition is available in:

For a more complete example demonstrating multiple flows, shared synchronization, and flow composition, see:

```text
examples/annotations.py
```

---

## Features
- Declarative flow definition.
- Strongly typed state through `Parcel` objects.
- Automatic dependency inference.
- Incremental state synchronization.
- Flow composition.

---

## License

Reed is distributed under the Apache License 2.0.






