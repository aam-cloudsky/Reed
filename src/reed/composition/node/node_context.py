"""
NodeContext (Slice 1A -- minimal structural shell; Slice 2D -- real
`ctx.memory` / `ctx.last_output` runtime behavior).

Scope established here across slices (docs/refactor_priority_order.md,
Milestone 1 Slice 1A and Milestone 2 Slice 2D; docs/node_context_decision.md;
docs/architectural_invariants.md #12-17):

    NodeContext[MemoryType, OutputType]

        ctx.memory        -- private, node-local mutable state, scoped to
                              Run x NodeRuntime (architectural_invariants.md
                              #14, #16).
        ctx.last_output   -- latest successfully committed domain output
                              for this NodeRuntime (architectural_invariants.md
                              #15); always `None` in this slice -- nothing
                              commits a domain output yet (Slice 2E).

`NodeContext != InputPort` (architectural_invariants.md #12) was already
established in Slice 1A (`domain_signature.py` detects and excludes a
`NodeContext[...]`-annotated parameter from a node's dataflow input
parameters); this slice makes the two capabilities `NodeContext` is
allowed to expose (architectural_invariants.md #13; docs/non-goals.md,
"NodeContext Scope") real for the first time.

`NodeContext` remains intentionally narrow (docs/non-goals.md, "NodeContext
Scope"): it must not become an `InputPort`, a service locator, or a proxy
to `Run`, `Flow`, `Repository`, `Bus`, `Outpost`, or `NodeRuntime`. This
class holds only the two plain values it is constructed with -- the
memory instance and the last-output value -- and exposes nothing else.
It does not hold a reference back to the `NodeRuntime` (or `Run`, `Flow`,
etc.) that constructed it, so there is no path from `ctx` to any internal
execution infrastructure (architectural_invariants.md #26). This is a
deliberately stronger boundary than "don't add convenience properties for
internal objects" -- there is no internal reference here at all to
accidentally leak.

Who constructs a `NodeContext` and how memory is initialized is
`NodeRuntime`'s responsibility (`reed/execution/node_runtime.py`), not
this class's: `NodeRuntime.context` builds a fresh `NodeContext` snapshot
from its own `.memory` (lazily instantiated from the owning `FlowNode`'s
declared `MemoryType`, memoized so mutations persist across firings
within one Run -- see `node_runtime.py`'s module docstring for exactly
how) and `.last_output` (always `None` in this slice) on every access.
This class must still not be instantiated directly by user code -- only
`NodeRuntime.context` does, matching "injected by Reed"
(docs/node_context_decision.md, "Core Thesis").

Explicitly out of scope for this slice (Milestone 2, later slices; see
docs/refactor_priority_order.md's Priority 13 traceability split
"context/memory wiring -> 2D; firing pipeline -> 2E"):

    - No node-function execution, no argument construction/injection
      from descriptors -- nothing calls a node function or builds its
      call arguments yet (2E).
    - No transactional commit, no `.publish(...)`, no wiring of
      `ctx.last_output` to any real committed value -- `last_output` is
      always `None` in this slice. See docs/node_context_decision.md,
      "Transaction Semantics": "failed firing -> no committed memory
      transition and no committed output; successful firing -> memory
      transition and output publication commit together" -- there is no
      firing at all yet, so this rule has nothing to violate or satisfy
      here.
    - No stateful-firing serialization (architectural_invariants.md #17,
      Slice 2G) -- nothing in this slice executes a node function, so
      there is no concurrent access to a `NodeRuntime`'s memory to
      serialize against yet.
    - No `on_output` dispatch (Slice 2F).
    - No `ArtifactRecord` wrap/unwrap through this boundary -- `ctx.memory`
      and `ctx.last_output` are always plain domain-typed values (the
      declared `MemoryType`/`OutputType`), never an internal
      `ArtifactRecord` (Slice 2C's own wrap/unwrap boundary is unaffected
      by this slice; see `reed/execution/artifact_record.py`).
"""

from __future__ import annotations

from typing import Generic, TypeVar

MemoryType = TypeVar("MemoryType")
OutputType = TypeVar("OutputType")


class NodeContext(Generic[MemoryType, OutputType]):
    """
    Reed-injected execution context, identified by type annotation
    (Slice 1A); real `ctx.memory`/`ctx.last_output` values as of Slice 2D.

    See module docstring for the exact scope. Constructed only by
    `NodeRuntime.context` -- never directly by user code, and never
    holding a reference back to the `NodeRuntime`, `Run`, `Flow`, or
    anything else internal to Reed's execution infrastructure.
    """

    __slots__ = ("_memory", "_last_output")

    def __init__(
        self, *, memory: MemoryType, last_output: OutputType | None
    ) -> None:
        self._memory = memory
        self._last_output = last_output

    @property
    def memory(self) -> MemoryType:
        """
        This `NodeRuntime`'s private, node-local mutable memory
        (docs/node_context_decision.md, "Memory";
        architectural_invariants.md #14, #16 -- scoped to `Run x
        NodeRuntime`, never shared across Runs).

        The same object identity is returned across repeated
        `NodeRuntime.context` accesses on the same `NodeRuntime`, so
        in-place mutations (`ctx.memory.some_field = ...`) persist
        across firings within one Run.
        """
        return self._memory

    @property
    def last_output(self) -> OutputType | None:
        """
        The latest successfully committed domain output for this
        `NodeRuntime` (docs/node_context_decision.md, "Last Output";
        architectural_invariants.md #15 -- `NodeMemory != last_output`).

        Always `None` in this slice: nothing commits a domain output yet
        (Slice 2E). Must not be confused with `ctx.memory`, which is
        private computational memory, not a record of committed output.
        """
        return self._last_output
