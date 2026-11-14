"""
Public `reed` package surface.

Reed's only supported public execution model, per the accepted
architecture (docs/refactor/architecture.md) and the explicit decision to retire
the previous decorator/Parcel/bind/callable-Flow programming model:

    from reed import Flow, NodeContext, TriggerPolicy

    flow = Flow()
    flow.add(...)

    session = flow.session()
    session.feed(...)
    session.push()
    snapshot = session.snapshot()

`Session` is also exported for direct construction/typing use (`session =
flow.session()` already returns one; the export exists for callers who want
to reference the `Session` type itself, e.g. in a type annotation).

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
`TriggerPolicy`/`NodeContext`. The precedent: a new public type a node
signature is meant to reference directly belongs here.

Issue #31 additionally exports `Collective` and `InstanceKey`, by the
same rule: a node signature references `Collective[T]` directly (a
generic alias of `Annotated[tuple[T, ...], CollectiveMarker]`, so the
parameter is typed as the tuple it receives), and callers build
`InstanceKey`s to feed instances (`session.feed_instances({...})`).
"""

from reed.composition.flow.flow_composition import Flow
from reed.composition.flow.trigger_policy import TriggerPolicy
from reed.composition.node.artifact_descriptor import InputRole
from reed.composition.node.collective import Collective
from reed.composition.node.node_context import NodeContext
from reed.composition.node.sampled import Sampled
from reed.execution.instance_key import InstanceKey
from reed.execution.session import Session

__all__ = [
    "Flow",
    "TriggerPolicy",
    "NodeContext",
    "Session",
    "InputRole",
    "Sampled",
    "Collective",
    "InstanceKey",
]
