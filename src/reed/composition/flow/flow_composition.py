"""
Flow (Slice 1F, remainder of Priority 11 -- `Flow.add(...)`).

This is the Milestone 1 integration gate: it connects the composition
collaborators already built in Slices 1A-1E into the target composition
surface (docs/flow_composition_implementation_basis.md, "Move `@flow` Out
Of The Main API Path", "`Flow.add(...)`"; docs/refactor_priority_order.md,
Priority 11):

    NodeDefinition
        v
    Flow.add(...)
        v
    FlowNode
        v
    ArtifactDependencyGraph

`Flow` is an explicit composition object (docs/architectural_decision.md,
"Flow Composition"; docs/refactor_priority_order.md, Priority 11 target):
it owns `FlowNode` registrations and validates topology (unique producer,
self-flow) through one `ArtifactDependencyGraph` per `Flow` instance. It
owns no Run-specific execution state (architectural_invariants.md #4, #6:
`Flow != Run`).

`add(...)`'s `trigger_policy` and `on_output` are keyword-only (matching
`flow_composition_implementation_basis.md`'s recommended shape and
rejecting the positional-ambiguity forms it warns against). Both are
stored on the returned `FlowNode` as Flow-local composition metadata
only -- this slice does not evaluate `trigger_policy` or invoke
`on_output` (architectural_invariants.md #18-20: dirty state does not
imply execution, `TriggerPolicy` decides eligibility but nothing here
evaluates that eligibility, and `TriggerPolicy != on_output`).

Explicitly out of scope for this slice (Milestone 2):

    - `Flow.run()`, `Run`, `NodeRuntime`, `NodeExecution` do not exist.
      This class deliberately has no `run()` method.
    - No `ArtifactRecord` wrapping/unwrapping, no `NodeMemory`, no
      `ctx.memory`/`ctx.last_output` runtime behavior.
    - `on_output` is never called; `trigger_policy` is never read for
      eligibility decisions. Both are inert metadata here.
    - No commit semantics, no callback dispatch (sync or async), no
      stateful-firing serialization, no `ArtifactRepository` migration.
    - No `Flow.connect(...)` (docs/non-goals.md, "Manual Topology
      Connection"): topology is inferred from producer/consumer artifact
      types via `ArtifactDependencyGraph`, not from an explicit connect
      step.
    - No new node-participation identity semantics
      (docs/non-goals.md, "Multiple Registrations of the Same Node
      Definition") -- unchanged from Slice 1C.

This class is unrelated to the old, decorator-bound
`reed.composition.flow.flow.Flow` (current-behavior, regression-protected,
`Generic[P, R]`, owns `_nodes`/materialization/execution) -- that class is
never imported by `reed/__init__.py` and is left untouched. The two
happen to share a class name in different modules; only this one is
exposed as the top-level `reed.Flow`.
"""

from __future__ import annotations

import sys
from typing import Callable

from reed.composition.flow.artifact_dependency_graph import ArtifactDependencyGraph
from reed.composition.flow.flow_node import FlowNode
from reed.composition.flow.trigger_policy import TriggerPolicy
from reed.composition.node.domain_node_description import DomainNodeDescriptionBuilder


class Flow:
    """
    Explicit Flow composition object (target architecture, Slice 1F).

    See module docstring for the exact scope. Owns `FlowNode`
    registrations and one `ArtifactDependencyGraph` for topology
    validation; owns no Run-specific execution state.
    """

    def __init__(self) -> None:
        self._flow_nodes: list[FlowNode] = []
        self._dependency_graph = ArtifactDependencyGraph()

    def add(
        self,
        function: Callable,
        *,
        trigger_policy: TriggerPolicy = TriggerPolicy.ALL_INPUTS_CHANGED,
        on_output: Callable[[object], object] | None = None,
    ) -> FlowNode:
        """
        Register `function` as a Flow-local node participation.

        Builds a `DomainNodeDefinition` (Slice 1B, via Slice 1A's
        signature parser -- this is where self-flow and `NodeContext`
        output-type validation happen), wraps it in a `FlowNode` (Slice
        1C) carrying `trigger_policy`/`on_output` as composition
        metadata, registers it against this Flow's
        `ArtifactDependencyGraph` (Slice 1D -- unique-producer and
        self-flow validation at the composition level), and returns the
        `FlowNode`.

        `trigger_policy` and `on_output` are keyword-only: this is what
        makes `flow.add(my_node, callback, policy)` a `TypeError` rather
        than an ambiguous positional call.

        Annotation resolution: normal `typing.get_type_hints`
        resolution (via `function`'s own defining module globals) is
        always the primary path. Only if that raises `NameError` does
        this method retry once using its own immediate caller's local
        namespace, as a narrow, best-effort compatibility fallback for
        a node function defined and registered inline -- see
        `domain_signature.py`'s module docstring for the full
        rationale and limits.
        """

        try:
            definition = DomainNodeDescriptionBuilder(function).build_definition()
        except NameError:
            # Slice 1F follow-up (maintenance, not a new architectural
            # slice): normal resolution above already failed. Retry
            # exactly once using this method's own immediate caller's
            # local namespace -- a best-effort compatibility fallback,
            # not general lexical-scope resolution -- so a node
            # function defined and registered immediately inline (for
            # example `def node(...): ...; flow.add(node)`) can still
            # reference a name (such as NodeContext) imported only in
            # that caller's local scope. This does not generalize to
            # functions returned through wrapper/factory scopes -- only
            # the direct caller of `add(...)` is inspected, and only
            # once. If frame introspection itself is unavailable
            # (non-CPython interpreters), `caller_globalns` stays
            # `None` and the retry fails the same way the first
            # attempt did, propagating the original `NameError`.
            try:
                caller_globalns = dict(sys._getframe(1).f_locals)
            except (AttributeError, ValueError):
                caller_globalns = None

            definition = DomainNodeDescriptionBuilder(
                function, extra_globalns=caller_globalns
            ).build_definition()

        flow_node = FlowNode(
            definition=definition,
            trigger_policy=trigger_policy,
            on_output=on_output,
        )

        self._dependency_graph.register(flow_node)
        self._flow_nodes.append(flow_node)

        return flow_node
