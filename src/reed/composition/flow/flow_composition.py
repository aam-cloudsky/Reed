"""
Flow (Slice 1F, remainder of Priority 11 -- `Flow.add(...)`; Slice 2A,
part of Priority 11/12 -- `Flow.run()` / `Run` separation; Slice 2B,
part of Priority 13 -- adds a read-only `flow_nodes` accessor so
`Run.node_runtime(...)` can resolve a node function to its
`FlowNode`).

Slice 1F connected the composition collaborators already built in
Slices 1A-1E into the target composition surface
(docs/flow_composition_implementation_basis.md, "Move `@flow` Out
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

Slice 2A (docs/architectural_decision.md, "Run"; architectural_invariants.md
#4, #6 -- `Flow != Run`, `Flow` owns no Run-specific execution state) adds
`Flow.run()`, which creates and returns a new `Run`
(`reed.execution.run.Run`) associated with this `Flow`. `Flow` itself
stores nothing about the `Run`s it has created -- no list, no counter,
no last-created reference -- so it remains a plain, reusable composition
object no matter how many times `run()` is called. `Run` owns a
distinct, `ArtifactRepository`-backed repository instance per `Run` (Slice 2A
follow-up) and a distinct `NodeRuntime` per materialized node (Slice
2B, `run.node_runtime(...)`) -- `Flow` and `FlowNode` acquire none of
that state; see `reed/execution/run.py`'s and
`reed/execution/node_runtime.py`'s module docstrings for the exact
scope of each.

Explicitly out of scope for this slice (Milestone 2, later slices):

    - `NodeRuntime` exists as of Slice 2B, but only as an
      ownership boundary owned by `Run` (`run.node_runtime(...)`);
      `Flow` itself gains no new capability from it beyond exposing
      `flow_nodes` for `Run` to resolve against. `NodeExecution`
      (2E) does not exist yet.
    - No `ArtifactRecord` wrapping/unwrapping (2C), no `NodeMemory`
      (2D), no `ctx.memory`/`ctx.last_output` runtime behavior (2D/2E).
    - `on_output` is never called; `trigger_policy` is never read for
      eligibility decisions. Both are inert metadata here.
    - No `.publish(...)`, no commit semantics, no callback dispatch
      (sync or async, 2F), no `callback_failures` (2F), no
      stateful-firing serialization (2G), no `ArtifactRepository`
      migration.
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

import hashlib
import sys
from typing import Callable, TypeVar

from reed.composition.flow.artifact_dependency_graph import ArtifactDependencyGraph
from reed.composition.flow.flow_node import FlowNode
from reed.composition.flow.trigger_policy import TriggerPolicy
from reed.composition.node.domain_node_description import DomainNodeDescriptionBuilder
from reed.execution.run import Run


OutputT = TypeVar("OutputT")


class Flow:
    """
    Explicit Flow composition object (target architecture, Slices 1F,
    2A, and 2B).

    See module docstring for the exact scope. Owns `FlowNode`
    registrations and one `ArtifactDependencyGraph` for topology
    validation; owns no Run-specific execution state, including after
    `run()` is called any number of times. `flow_nodes` (Slice 2B) is
    a read-only view of those registrations, added so `Run` can
    resolve a node function to its `FlowNode` without reaching into
    `Flow`'s private internals.
    """

    def __init__(self) -> None:
        self._flow_nodes: list[FlowNode] = []
        self._dependency_graph = ArtifactDependencyGraph()

    @property
    def flow_nodes(self) -> tuple[FlowNode, ...]:
        """
        This `Flow`'s registered `FlowNode` participations, in
        registration order (Slice 2B).

        A read-only snapshot -- mutating the returned tuple is not
        possible, and mutating it would not affect `Flow`'s own
        registrations either way. Added so `Run.node_runtime(...)`
        can resolve a node function to its `FlowNode` without
        reaching into `Flow`'s private internals.
        """
        return tuple(self._flow_nodes)

    @property
    def flow_id(self) -> str:
        """
        This `Flow`'s stable observability identity (Milestone O1, Slice
        O1a/O1b; docs/observability_design.md Section 18 -- `flow_id`/
        `node_id` cross-run stability).

        Deterministically derived from the ordered tuple of this Flow's
        registered `FlowNode.node_id` values: a SHA-256 digest (first 16
        hex characters -- short enough to be usable in a path/filename,
        long enough that accidental collision is not a practical
        concern) of those ids joined by `"|"`, in registration order.

        This is computed fresh from `self._flow_nodes` on every access,
        never cached: `flow_id` is a pure function of "which FlowNodes
        are registered, in what order" at the moment it is read, so a
        Flow that is still being composed (nodes added after an earlier
        read) is never stuck with a stale value.

        Two consequences, both intentional (docs/observability_design.md
        Section 17.1/17.2 and Section 18):

        1. Running the same script twice (the same sequence of
           `Flow.add(...)` calls) in two separate OS processes produces
           the same `flow_id` both times -- no user-supplied name or
           identifier is required (docs/observability_non_goals.md
           Section 8: no `name=` parameter on `Flow.add(...)`).
        2. A code change to the Flow's composition (a node added,
           removed, or reordered) changes `flow_id` automatically, as a
           direct consequence of this deterministic derivation -- there
           is no separate "should this force a new flow_id" mechanism
           to design, because `flow_id` was never an independent,
           storable value in the first place.

        Known, accepted limitation: two independently authored Flows
        that happen to register the exact same sequence of node
        functions (same modules, same qualified names, same order)
        collide on `flow_id`. This is considered acceptable given how
        narrow and low-stakes that coincidence is in practice; it is not
        the "some UUID will do" shortcut `observability_non_goals.md`
        Section 10 warns against; it is a documented trade-off of a
        specific, deterministic derivation.
        """
        joined = "|".join(flow_node.node_id for flow_node in self._flow_nodes)
        digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
        return digest[:16]

    @property
    def dependency_graph(self) -> ArtifactDependencyGraph:
        """
        This `Flow`'s `ArtifactDependencyGraph` (Slice 2H).

        A minimal, read-only accessor mirroring the `flow_nodes`
        property's exact precedent above -- added so `Run.publish(...)`
        can query `consumers_of(...)` to discover cascade-eligible
        FlowNodes without reaching into `Flow`'s private state or
        `Run` duplicating a second producer/consumer index of its own.
        The graph instance itself is the same one `add(...)` already
        registers every `FlowNode` against; this property does not
        construct a new one or copy it.
        """
        return self._dependency_graph

    def add(
        self,
        function: Callable[..., OutputT],
        *,
        trigger_policy: TriggerPolicy = TriggerPolicy.ALL_INPUTS_CHANGED,
        on_output: Callable[[OutputT], object] | None = None,
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

    def run(self) -> Run:
        """
        Create a new `Run` -- one concrete execution instance of this
        `Flow` (Slice 2A; docs/architectural_decision.md, "Run").

        Each call returns a distinct `Run`. `Flow` records nothing
        about the `Run`s it creates, so it remains a reusable
        composition object -- `add(...)` can still be called, and
        `run()` can be called again, after any number of prior
        `run()` calls.

        The returned `Run` cannot yet execute meaningful computation.
        `NodeRuntime` exists as of Slice 2B as an ownership boundary
        only (`run.node_runtime(...)`); commit semantics and callback
        dispatch remain Milestone 2C-2G -- see
        `reed/execution/run.py`'s and
        `reed/execution/node_runtime.py`'s module docstrings for the
        exact scope.
        """
        return Run(self)
