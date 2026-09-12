"""
Minimal structural NodeContext shell (Slice 1A).

Scope for this slice (docs/refactor_priority_order.md, Milestone 1, Slice
1A; docs/node_context_decision.md):

    NodeContext[MemoryType, OutputType] exists as a real, importable,
    generic type so that signature parsing (see `domain_signature.py`) has
    a concrete type to detect via `typing.get_origin(annotation)`.

Explicitly out of scope for this slice:

    `ctx.memory` and `ctx.last_output` are NOT implemented here. Both are
    scoped to `Run x NodeRuntime` (architectural_invariants.md #14), which
    do not exist until Milestone 2. Adding runtime behavior to this class
    now would require inventing Run/NodeRuntime wiring ahead of schedule --
    see docs/refactor_priority_order.md, "The 1A / 1C dependency (resolved)".

    This class must not be instantiated by user code. It became part of
    the public `reed` package surface in Slice 1F (`Flow.add(...)`,
    exported as `reed.NodeContext`) for type-annotation/detection
    purposes only: nothing constructs an instance or passes one to a
    user function yet -- that still requires Slice 2D (`NodeMemory`
    wiring) and the `Run`/`NodeRuntime` execution boundary.
"""

from __future__ import annotations

from typing import Generic, TypeVar

MemoryType = TypeVar("MemoryType")
OutputType = TypeVar("OutputType")


class NodeContext(Generic[MemoryType, OutputType]):
    """
    Reed-injected execution context, identified by type annotation.

    `NodeContext != InputPort` (architectural_invariants.md #12): a
    parameter annotated with `NodeContext[MemoryType, OutputType]` is
    excluded from a node's dataflow input parameters.

    This shell intentionally has no runtime behavior in Slice 1A.
    """

    __slots__ = ()
