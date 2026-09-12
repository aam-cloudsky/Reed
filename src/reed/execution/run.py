"""
Run (Slice 2A, part of Priority 11/12 -- `Flow` / `Run` separation;
Slice 2A follow-up -- Run-scoped repository ownership; Slice 2B, part of
Priority 13 -- `NodeRuntime` ownership; Slice 2E, part of Priority 13 --
the single-firing execution path, `Run.publish(...)`).

Scope for this slice (docs/refactor_priority_order.md, Milestone 2, Slice
2A; docs/architectural_decision.md, "Run"):

    Flow
        v (run())
    Run
        v (owns)
    repository (Depot, for now -- see below)
    NodeRuntime instances (one per (Run, FlowNode) pair -- see below)

`Run` represents one concrete execution instance of a `Flow`
(docs/architectural_decision.md: "A `Run` represents one concrete
execution of a flow. It owns execution-specific state, including: shared
state for that execution; node runtime instances; local state for each
node runtime; artifact versions created during the execution; activation
status; event and message history; execution traces."). This slice
establishes the identity/ownership *boundary* -- `Run` is the correct
owner for all of the above -- and, as of the Slice 2A follow-up and Slice
2B below, makes two pieces of that ownership concrete: Run-scoped
repository storage, and Run-scoped `NodeRuntime` materialization. It does
not implement the rest yet (architectural_invariants.md #4, #6:
`Flow != Run`; `Flow` owns no Run-specific execution state).

Run-scoped repository ownership (Slice 2A follow-up):

    Each `Run` constructs and owns its own repository instance, exposed
    as `run.repository`. For this migration stage the repository is the
    existing `Depot`, constructed the same way the current,
    regression-protected execution path already constructs one
    (`reed.synchronization.logistics.Logistics.__init__`):

        bus = Bus.create()
        repository = Depot(bus=bus)

    This is the temporary migration strategy
    `docs/refactor_priority_order.md`'s Slice 2A row and its
    accompanying prose describe: "`Run` gets a `.repository` accessor
    from this point on, backed by whatever the current storage class is
    called internally (still `Depot` until Milestone 3, slice 3A) ...
    Milestone 2 can and should pass its tests while the underlying
    storage class is still internally called `Depot`." It is not the
    final repository architecture: `Depot` is not renamed, no
    `ArtifactRecord`-aware `get`/`set` API is defined here, and no
    adapter/protocol/factory layer is introduced. `Run.repository` is a
    plain pass-through to the `Depot` instance this `Run` constructed
    for itself -- nothing more.

    Each `Run` gets its own `Bus` and its own `Depot`: two `Run`s
    created from the same `Flow` share no repository state and no
    repository identity (`Depot.identity` differs because each is built
    from a distinct `Bus`).

    An earlier version of this module deferred `.repository` entirely,
    reasoning that constructing a `Depot` pulled in "the full legacy
    transportation/lifecycle stack" and that doing so would read as a
    speculative abstraction under `docs/non-goals.md`. Both reasons were
    wrong on inspection: constructing a `Bus` + `Depot` pair is the same
    trivial, already-used, regression-tested two-line pattern
    `Logistics.__init__` already relies on today (no I/O, no threads, no
    sockets -- `Bus.create()` just wraps an in-process `MessageHub()`),
    and `docs/non-goals.md`'s "Repository Exposure" / "Execution
    Infrastructure Exposure" sections are scoped explicitly to
    `NodeContext` and the public node-function-body API, not to `Run`'s
    own accessor -- they say nothing about `Run`. This module corrects
    that deferral rather than leaving it for a later slice; see
    docs/refactor_state.md's Slice 2A record and Refactor State Log for
    the corrected history.

Run-scoped `NodeRuntime` ownership (Slice 2B):

    `Run.node_runtime(node)` returns this `Run`'s `NodeRuntime`
    (`reed.execution.node_runtime.NodeRuntime`) for the `FlowNode` whose
    underlying function is `node` -- `node` is the same callable
    originally passed to `Flow.add(...)`, matched by identity, exactly
    as `tests/test_target_architecture_contract.py`'s target-contract
    tests already call it (`run.node_runtime(track)`; that is the
    accepted access shape, followed here rather than inventing another
    one). The lookup is get-or-create and memoized per `Run`: repeated
    calls for the same node return the same `NodeRuntime` instance,
    while two different `Run`s -- even created from the same `Flow` --
    never share one, even for the same `FlowNode`
    (architectural_invariants.md #2: `FlowNode != NodeRuntime`; #3:
    `NodeRuntime != NodeExecution`). See
    `reed/execution/node_runtime.py`'s module docstring for
    `NodeRuntime`'s own exact scope.

Single-firing execution path (Slice 2E; docs/refactor_priority_order.md,
Milestone 2, Slice 2E row):

    `Run.publish(domain_value)` gives `Run` a real, single-firing
    execution path:

        1. find the one `FlowNode` on this `Run`'s `Flow` that consumes
           `type(domain_value)`;
        2. build that node's call arguments -- the published domain
           value for its one consumed dataflow parameter, plus a
           constructed `NodeContext` snapshot
           (`self.node_runtime(...).context`) for the parameter named by
           `FlowNode.context.parameter_name`, when the node declares one;
        3. call the node function directly (no `NodeExecution` object is
           introduced yet -- see below);
        4. wrap the returned domain value into an `ArtifactRecord` via
           `NodeRuntime.wrap(...)` and commit it via
           `NodeRuntime.commit(...)`, which together update
           `run.repository`'s additive `ArtifactRecord` storage
           (`reed/synchronization/depot.py`) and the firing
           `NodeRuntime`'s `.last_output` in one call.

    This is deliberately narrow, matching this slice's two target
    contracts (`test_run_instances_isolate_node_memory`,
    `test_last_output_exposes_latest_committed_domain_value`) and no
    more:

    - Only a single-`FlowNode`, single-published-artifact-type flow is
      supported. If zero or more than one registered `FlowNode` consumes
      `type(domain_value)`, or the one matching `FlowNode` consumes more
      than one artifact type, `publish` raises `ValueError` rather than
      inventing multi-node dispatch/routing or a rule for sourcing
      parameters the published value does not supply -- this is exactly
      the ambiguity the SliceContract's stop_conditions name, so it is
      surfaced as an explicit error instead of guessed at.
    - `TriggerPolicy` is not consulted. The one matching `FlowNode`
      always executes; `Run.publish(...)` does not check execution
      eligibility (Priority 10 recommended-work item 4, still not
      absorbed by any completed slice).
    - No `on_output` dispatch (Slice 2F).
    - No transactional rollback. `publish` implements only the
      successful-commit path; if the node function raises, or a future
      slice's wrap/commit sequence fails partway through, no accepted
      document determines the rollback mechanism yet (deepcopy vs.
      clone-protocol vs. immutable-replacement vs. transactional-proxy
      vs. serialization) -- see `docs/node_context_decision.md`,
      "Transaction Semantics", and the SliceContract's stop_conditions.
      That mechanism is reported as future work (likely Slice 2F/2G,
      alongside callback failure isolation), not guessed at here.
    - No `NodeExecution` object is introduced to represent "one concrete
      execution attempt" (docs/architectural_decision.md, "Node
      Execution") -- the node function is called directly from
      `publish`. Neither target test this slice must pass requires a
      distinct `NodeExecution` instance to exist; introducing one here
      would be a speculative abstraction ahead of a concrete need.
    - No multi-node graph propagation -- `publish` fires exactly the one
      matching node and returns.

Explicitly still out of scope for this slice (Milestone 2, later slices):

    - No domain-facing `repository.get(domain_type)` /
      `repository.set(...)` API on `Run` itself. `run.repository`
      exposes the raw `Depot` instance as-is (its existing
      `get_parcel`/`set_parcel`/`get_pallet` methods, plus Slice 2E's
      additive `set_artifact_record`/`get_artifact_record`); a
      `Run`-level accessor wired into `on_output` dispatch is Slice 2F's
      job.
    - No rename of `Depot` to `ArtifactRepository` (Milestone 3, slice
      3A; docs/non-goals.md, "Broad Renaming").
    - No new node-participation identity semantics, no distributed
      execution, no advanced scheduling -- unchanged from Milestone 1.

`Run`'s responsibilities in this slice: exist as a distinct object per
`Flow.run()` call, know which `Flow` created it, own a distinct
repository instance, own a distinct, per-node `NodeRuntime` for each node
materialized through it, and support one real, single-node firing via
`.publish(...)`.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING, Any, Callable

from reed.execution.node_runtime import NodeRuntime
from reed.synchronization.depot import Depot
from reed.transportation.bus import Bus

if TYPE_CHECKING:
    from reed.composition.flow.flow_composition import Flow
    from reed.composition.flow.flow_node import FlowNode


class Run:
    """
    One concrete execution instance of a `Flow` (Slice 2A; repository
    ownership corrected by the Slice 2A follow-up; `NodeRuntime`
    ownership added by Slice 2B; single-firing execution path,
    `.publish(...)`, added by Slice 2E).

    See module docstring for the exact scope. `Run` owns an
    identity/ownership boundary plus its own repository instance
    (`.repository`, currently backed directly by `Depot`), its own
    `NodeRuntime` per materialized node (`.node_runtime(...)`), and a
    single-node firing path (`.publish(...)`) -- it exists so that later
    slices (2F-2G) have somewhere correct to attach callback dispatch and
    stateful-firing serialization, without any of that state ever being
    stored on `Flow` or `FlowNode`.
    """

    def __init__(self, flow: Flow) -> None:
        self._flow = flow
        self._repository = Depot(bus=Bus.create())
        self._node_runtimes: dict[FlowNode, NodeRuntime] = {}
        self.callback_failures: list[BaseException] = []
        self._pending_callback_coroutines: list[Any] = []

    @property
    def flow(self) -> Flow:
        """The `Flow` that created this `Run` via `Flow.run()`."""
        return self._flow

    @property
    def repository(self) -> Depot:
        """
        This `Run`'s own repository instance.

        Backed directly by `Depot` for this migration stage (Slice 2A
        follow-up; docs/refactor_priority_order.md's Slice 2A row).
        Every `Run` constructs its own `Bus` + `Depot` pair, so two
        `Run`s -- even from the same `Flow` -- never share repository
        state or repository identity.
        """
        return self._repository

    def node_runtime(self, node: Callable) -> NodeRuntime:
        """
        This `Run`'s `NodeRuntime` for the `FlowNode` wrapping `node`
        (Slice 2B).

        `node` is the original callable passed to `Flow.add(...)`,
        matched by identity against each of this `Run`'s `Flow`'s
        registered `FlowNode`s. Get-or-create and memoized per `Run`:
        calling this twice for the same node returns the same
        `NodeRuntime`; calling it on a different `Run` never does, even
        for the same node.

        Raises `ValueError` if `node` was never registered on this
        `Run`'s `Flow` via `Flow.add(...)`.
        """
        flow_node = self._find_flow_node(node)

        if flow_node not in self._node_runtimes:
            self._node_runtimes[flow_node] = NodeRuntime(self, flow_node)

        return self._node_runtimes[flow_node]

    def publish(self, domain_value: object) -> object:
        """
        Entry point to the automatic propagation cascade (Slice 2H;
        Slice 2E's original single-firing dispatch is now
        `Run._fire(...)`, reused unchanged by both direct publication
        and cascade propagation).

        `domain_value` is treated as an already-committed input and
        seeds a FIFO queue of pending committed domain values. While the
        queue is non-empty, this pops one committed value, uses
        `self._flow.dependency_graph.consumers_of(type(value))` to find
        every `FlowNode` consuming that type, fires each single-input
        consumer (`len(flow_node.consumed_artifacts) == 1`) via
        `self._fire(...)`, and enqueues its committed output domain
        value for the next iteration. A discovered multi-input FlowNode
        (a join candidate) is left inert -- looked up, found, and
        deliberately skipped, never fired and never an error (Slice
        2I's job). No per-version "already fired" bookkeeping is
        introduced: a fresh cascade runs to quiescence (queue empty) on
        every call, so a second `publish(...)` call re-fires downstream
        nodes again with new data.

        Returns the domain value produced by firing the `FlowNode`(s)
        that directly consume `domain_value` itself -- specifically,
        the last such direct firing's committed value, unaffected by
        anything the cascade goes on to fire afterward. If nothing
        consumes `type(domain_value)`, returns `domain_value` itself
        (there was no direct firing to report a result for).
        """
        pending: list[object] = [domain_value]
        direct_result: object = domain_value
        is_first_iteration = True

        while pending:
            current_value = pending.pop(0)
            domain_type = type(current_value)

            consumers = self._flow.dependency_graph.consumers_of(domain_type)

            for flow_node in consumers:
                if len(flow_node.consumed_artifacts) != 1:
                    # Multi-input FlowNode: discovered, not fired, no
                    # error -- Slice 2I owns join-firing semantics.
                    continue

                result = self._fire(flow_node, current_value)
                pending.append(result)

                if is_first_iteration:
                    direct_result = result

            is_first_iteration = False

        return direct_result

    def _fire(self, flow_node: "FlowNode", domain_value: object) -> object:
        """
        Fire one `FlowNode` with `domain_value` as its single consumed
        input (Slice 2H; the exact single-firing body Slice 2E
        originally inlined into `publish`, refactored out unchanged so
        it runs identically whether invoked directly or from cascade
        propagation).

        Builds `flow_node`'s call arguments (`domain_value` for its one
        consumed parameter, plus a constructed `NodeContext` snapshot
        when the node declares one), calls the node function, wraps the
        returned domain value into an `ArtifactRecord`, commits it into
        `self.repository`, updates the firing `NodeRuntime`'s
        `.last_output`, and dispatches `on_output`. Returns the produced
        domain value (`record.value`).
        """
        node_runtime = self.node_runtime(flow_node.definition.function)

        call_kwargs: dict[str, object] = {
            flow_node.consumed_artifacts[0].name: domain_value,
        }

        if flow_node.context is not None:
            call_kwargs[flow_node.context.parameter_name] = node_runtime.context

        firing_lock = node_runtime.firing_lock

        if firing_lock is not None:
            firing_lock.acquire()
        try:
            result = flow_node.definition.function(**call_kwargs)

            record = node_runtime.wrap(result)
            node_runtime.commit(record)
        finally:
            if firing_lock is not None:
                firing_lock.release()

        self._dispatch_on_output(flow_node, record.value)

        return record.value

    def publish_many(self, domain_values: "list[object]") -> None:
        """
        Publish each value in `domain_values`, in order, via
        `self.publish(...)` (Slice 2G).

        A thin, sequential convenience wrapper -- not a second
        execution path, a queue, or a scheduler: it calls
        `self.publish(value)` once per value, exactly as if the caller
        had called `.publish(...)` in a loop themselves. See
        `test_stateful_node_runtime_firings_are_serialized`
        (tests/test_target_architecture_contract.py), which uses this
        method; the actual concurrency guarantee it relies on
        (`architectural_invariants.md #17) comes from
        `NodeRuntime.firing_lock`, not from this method firing
        concurrently -- see module docstring and the SliceContract's
        stop_conditions for why a sequential loop, plus a real
        per-NodeRuntime lock, is the correct shape here.
        """
        for domain_value in domain_values:
            self.publish(domain_value)

    def _dispatch_on_output(self, flow_node: "FlowNode", domain_value: object) -> None:
        """
        Invoke `flow_node`'s declared `on_output` callback with
        `domain_value`, strictly after `NodeRuntime.commit(...)` has
        already succeeded (Slice 2F; architectural_invariants.md #21,
        #22, #23).

        A synchronous `on_output` is invoked inline, inside a
        try/except; any raised exception is caught and appended to
        `self.callback_failures` rather than propagating out of
        `publish(...)` or being silently swallowed. An async
        `on_output` (detected via `inspect.iscoroutinefunction`) is
        not awaited here -- calling it only produces a coroutine
        object, which is queued onto `self._pending_callback_coroutines`
        for `.wait_for_callbacks()` to drain. Either way, nothing here
        can undo or affect the already-committed `ArtifactRecord` or
        repository state -- this method only observes a commit that
        has already happened.
        """
        on_output = flow_node.on_output
        if on_output is None:
            return

        if inspect.iscoroutinefunction(on_output):
            self._pending_callback_coroutines.append(on_output(domain_value))
            return

        try:
            on_output(domain_value)
        except BaseException as exc:  # noqa: BLE001 -- isolate any callback failure
            self.callback_failures.append(exc)

    def wait_for_callbacks(self) -> None:
        """
        Drain every pending async `on_output` coroutine queued by
        `._dispatch_on_output(...)` to completion (Slice 2F).

        Uses `asyncio.run` over an internal `asyncio.gather` as a
        bounded, synchronous driver -- not an always-on background
        event loop or thread pool (non-goals.md, "Execution
        Infrastructure Exposure"): once this method returns, nothing
        it started keeps running. Each pending coroutine's exception,
        if any, is isolated into `self.callback_failures` the same
        way a synchronous callback's exception is -- it never
        propagates out of this method and never affects any
        already-committed `ArtifactRecord` or repository state.
        """
        if not self._pending_callback_coroutines:
            return

        pending, self._pending_callback_coroutines = (
            self._pending_callback_coroutines,
            [],
        )

        async def _drain() -> None:
            results = await asyncio.gather(*pending, return_exceptions=True)
            for result in results:
                if isinstance(result, BaseException):
                    self.callback_failures.append(result)

        asyncio.run(_drain())

    def _find_flow_node(self, node: Callable) -> FlowNode:
        for flow_node in self._flow.flow_nodes:
            if flow_node.definition.function is node:
                return flow_node

        raise ValueError(
            f"{node!r} is not registered on this Run's Flow via "
            "Flow.add(...)"
        )
