"""
NodeRuntime (Slice 2B, part of Priority 13 -- `Node` -> `NodeRuntime`,
runtime-ownership portion; Slice 2C, part of Priority 13 -- the
`ArtifactRecord` unwrap boundary; Slice 2D, part of Priority 13 -- memory
and `.context` construction).

Scope for this slice (docs/refactor_priority_order.md, Milestone 2, Slice
2B row: "`Node` migrated to `NodeRuntime`: run-local ownership of one
`FlowNode`'s execution state, created and held by `Run`"; Priority 13's
own traceability split: "runtime ownership -> 2B"; docs/architectural_
decision.md, "Node Runtime"; docs/flow_composition_implementation_basis.md,
"FlowNode" -- the `NodeDefinition -> FlowNode -> NodeRuntime ->
NodeExecution` model):

    FlowNode
        v (materialized inside one Run)
    NodeRuntime

`NodeRuntime` represents one node participation (`FlowNode`) materialized
inside one `Run` (docs/architectural_decision.md, "Node Runtime": "A
`NodeRuntime` represents one node participation materialized inside one
run. It is distinct from `NodeDefinition`. This distinction prevents a
reusable node definition from accidentally carrying state across
unrelated executions.").

Slice 2B established only the ownership/identity boundary (a `NodeRuntime`
exists per (`Run`, `FlowNode`) pair, created and held by `Run`, stable
within a `Run`, never shared across `Run`s). Slice 2C added exactly one
thing on top of that: `NodeRuntime.unwrap(record)`, a pure passthrough
(`record.value`) for the "NodeRuntime boundary -> unwrap -> DomainValue"
step (see `reed/execution/artifact_record.py`'s module docstring for that
boundary's own exact scope).

Slice 2D adds NodeMemory ownership and `.context` construction
(docs/refactor_priority_order.md, Priority 5 "Create `NodeMemory`";
Priority 13's traceability split "context/memory wiring -> 2D";
docs/node_context_decision.md; docs/architectural_invariants.md #14, #15,
#16):

    NodeRuntime
        .memory        -- lazily instantiated from this NodeRuntime's
                           FlowNode's declared MemoryType (a zero-argument
                           construction -- docs/refactor_priority_order.md,
                           Priority 5, "instantiate memory from
                           MemoryType"), memoized so the same object is
                           returned (and can be mutated in place) on every
                           subsequent access.
        .last_output   -- always None in this slice; nothing commits an
                           output yet (Slice 2E).
        .context       -- a fresh NodeContext(memory=.., last_output=..)
                           snapshot built from the two properties above.

Both `.memory` and `.last_output` (and therefore `.context`, which is
built from them) raise `AttributeError` if this `NodeRuntime`'s node
function does not declare a `NodeContext[MemoryType, OutputType]`
parameter at all (`self.flow_node.context is None` -- see `FlowNode.context`,
Slice 1C, delegating to `NodeContextDescriptor`, Slice 1B). `AttributeError`
is used deliberately, not `ValueError`: it lets `hasattr(node_runtime,
"memory")` correctly report `False` for such a node (Python's `hasattr`
only swallows `AttributeError`), matching the intuition that a node
without a `NodeContext` parameter simply has no memory/context/last_output
capability -- there is no `MemoryType` to construct from and no declared
`OutputType` for `last_output` to be typed against.

Because two different `Run`s never share a `NodeRuntime` (Slice 2B) and
each `NodeRuntime`'s `.memory` is memoized on the `NodeRuntime` instance
itself (not on `FlowNode` or `Flow`), `NodeMemory` is scoped to exactly
`Run x NodeRuntime` (architectural_invariants.md #14) and is never shared
across `Run`s (architectural_invariants.md #16) as a direct structural
consequence of Slice 2B's ownership boundary -- this slice does not need
to add any additional isolation mechanism of its own.

Explicitly out of scope for this slice (Milestone 2, later slices; see
`docs/refactor_priority_order.md`'s Priority 13 "Recommended work" items
3-8, split across 2C-2G by the Priority-To-Slice Traceability table):

    - No argument construction from descriptors, no injecting a
      constructed `NodeContext` into an actual node-function call (2E) --
      `.context` is directly constructible/inspectable from `NodeRuntime`
      for testing and later wiring, but nothing calls a node function
      with it yet.
    - No `NodeExecution`, no node-function execution, no `wrap(...)` (the
      reverse, commit-tied direction), no transactional commit, no
      `.publish(...)` (2E).
    - No wiring of `ctx.last_output` to any real committed value --
      `.last_output` is always `None` in this slice (2E).
    - No `on_output` dispatch (sync or async), no `callback_failures`
      (2F).
    - No stateful-firing serialization (architectural_invariants.md #17,
      2G) -- nothing in this slice executes a node function at all, so
      there is no concurrent firing to serialize against yet.
    - No repository communication. `run.repository` is not read from or
      written to by anything here -- see
      `reed/execution/artifact_record.py`'s module docstring for why
      (`Depot`'s current API cannot hold an `ArtifactRecord`, and nothing
      needs it to yet, since nothing commits one until Slice 2E).
    - No new executors, schedulers, managers, factories, or lifecycle
      frameworks.

`NodeRuntime`'s responsibilities in this slice: exist as a distinct
object per (`Run`, `FlowNode`) pair, know which `Run` and which
`FlowNode` it materializes, unwrap an `ArtifactRecord` into its domain
value on request, own a private, node-local memory instance and a
last-committed-output slot (both scoped to itself), and construct a
`NodeContext` snapshot exposing both.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from reed.composition.node.node_context import NodeContext

if TYPE_CHECKING:
    from reed.composition.flow.flow_node import FlowNode
    from reed.execution.artifact_record import ArtifactRecord
    from reed.execution.run import Run


class NodeRuntime:
    """
    One node participation (`FlowNode`) materialized inside one `Run`
    (Slice 2B; `ArtifactRecord` unwrap boundary added by Slice 2C; memory
    and `.context` construction added by Slice 2D).

    See module docstring for the exact scope: an identity/ownership
    boundary, a single pure unwrap operation, and now a private,
    node-local memory instance plus a `.context` snapshot. `NodeRuntime`
    still owns no execution capability -- it exists so that later slices
    (2E-2G) have somewhere correct to attach real firing, commit, and
    callback dispatch behavior, without any of that state ever being
    stored on `FlowNode` (which remains reusable Flow-local composition
    metadata) or on `Flow` itself.
    """

    def __init__(self, run: Run, flow_node: FlowNode) -> None:
        self._run = run
        self._flow_node = flow_node
        self._memory: object | None = None
        self._last_output: object | None = None

    @property
    def run(self) -> Run:
        """The `Run` this `NodeRuntime` was materialized inside."""
        return self._run

    @property
    def flow_node(self) -> FlowNode:
        """
        The `FlowNode` (Flow-local participation) this runtime
        materializes.
        """
        return self._flow_node

    def unwrap(self, record: "ArtifactRecord") -> object:
        """
        Unwrap `record` into its domain value (Slice 2C).

        A pure passthrough (`record.value`) -- see module docstring for
        why this is the entire operation at this slice: no repository
        read, no descriptor-based validation, no node execution.
        """
        return record.value

    @property
    def memory(self) -> object:
        """
        This `NodeRuntime`'s private memory instance (Slice 2D), lazily
        instantiated from its `FlowNode`'s declared `MemoryType` and
        memoized: the same object is returned -- and can be mutated in
        place -- on every subsequent access for as long as this
        `NodeRuntime` (one per (`Run`, `FlowNode`) pair, Slice 2B) lives.

        Raises `AttributeError` if this `NodeRuntime`'s node function
        does not declare a `NodeContext` parameter -- there is no
        `MemoryType` to construct from.
        """
        if self._flow_node.context is None:
            raise AttributeError(
                f"{self._flow_node.definition.function!r} does not "
                "declare a NodeContext parameter; it has no memory."
            )

        if self._memory is None:
            self._memory = self._flow_node.context.memory_type()

        return self._memory

    @property
    def last_output(self) -> object | None:
        """
        The latest successfully committed domain output for this
        `NodeRuntime` (Slice 2D representation only). Always `None` in
        this slice: nothing commits an output yet (Slice 2E).

        Raises `AttributeError` for the same reason and under the same
        condition as `.memory` -- see its docstring.
        """
        if self._flow_node.context is None:
            raise AttributeError(
                f"{self._flow_node.definition.function!r} does not "
                "declare a NodeContext parameter; it has no last_output."
            )

        return self._last_output

    @property
    def context(self) -> NodeContext:
        """
        A fresh `NodeContext` snapshot (Slice 2D) exposing this
        `NodeRuntime`'s current `.memory` and `.last_output`.

        Raises `AttributeError` (via `.memory`) if this `NodeRuntime`'s
        node function does not declare a `NodeContext` parameter.
        """
        return NodeContext(memory=self.memory, last_output=self.last_output)
