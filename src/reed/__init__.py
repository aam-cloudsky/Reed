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

Slice 21D (GitHub issue #21, "Distinguish triggering inputs from sampled
inputs in node firing rules") additionally exports `InputRole` and
`Sampled`: a node signature is meant to reference `Sampled` directly
(`Annotated[T, Sampled]`) exactly as it already references `NodeContext`,
and `InputRole` for callers that inspect a `FlowNode`'s consumed
artifacts. Both are new public types, the same category as
`TriggerPolicy`/`NodeContext` (see
`.claude/reed-refactor/run-3G-20260912T205200Z/no_change_rationale.md`
for the precedent this follows: a new public type a node signature is
meant to reference directly belongs here; an internal execution or
repository class does not) -- not internal execution classes.
"""

from reed.composition.flow.flow_composition import Flow
from reed.composition.flow.trigger_policy import TriggerPolicy
from reed.composition.node.artifact_descriptor import InputRole
from reed.composition.node.node_context import NodeContext
from reed.composition.node.sampled import Sampled
from reed.execution.run import Run

__all__ = ["Flow", "TriggerPolicy", "NodeContext", "Run", "InputRole", "Sampled"]
