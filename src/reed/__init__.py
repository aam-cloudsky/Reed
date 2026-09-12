"""
Public `reed` package surface.

Reed's only supported public execution model, per the accepted
architecture (docs/architecture.md) and the explicit decision to retire
the previous decorator/Parcel/bind/callable-Flow programming model:

    from reed import Flow, NodeContext, TriggerPolicy

    flow = Flow()
    flow.add(...)

    run = flow.run()
    run.publish(...)

`Run` is also exported for direct construction/typing use (`run =
flow.run()` already returns one; the export exists for callers who want
to reference the `Run` type itself, e.g. in a type annotation).

The previous public programming model (`flow`/`node`/`input`/`output`
decorators, `Parcel`, and the legacy callable-Flow/`bind(...)` execution
path) is no longer part of Reed's public API and is not importable from
this package.
"""

from reed.composition.flow.flow_composition import Flow
from reed.composition.flow.trigger_policy import TriggerPolicy
from reed.composition.node.node_context import NodeContext
from reed.execution.run import Run

__all__ = ["Flow", "TriggerPolicy", "NodeContext", "Run"]
