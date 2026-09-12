"""
Run (Slice 2A, part of Priority 11/12 -- `Flow` / `Run` separation;
Slice 2A follow-up -- Run-scoped repository ownership; Slice 2B, part of
Priority 13 -- `NodeRuntime` ownership).

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
    `NodeRuntime`'s own exact scope -- it is an ownership boundary only
    in this slice, with no execution capability, no `NodeMemory`, and no
    repository wiring yet.

Explicitly still out of scope for this slice (Milestone 2, later slices):

    - No argument construction from descriptors, no unwrapping artifact
      records into domain values, no `NodeContext` injection (2C/2D).
    - No `NodeMemory`, no `ctx.memory`/`ctx.last_output` runtime
      behavior (2D).
    - No `NodeExecution`, no node-function execution, no wrapping
      returned domain values into artifact records, no `.publish(...)`,
      no transactional commit (2E).
    - No `on_output` dispatch (sync or async, 2F), no
      `callback_failures` (2F), no stateful-firing serialization (2G).
    - No domain-facing `repository.get(domain_type)` /
      `repository.set(...)` API. `run.repository` exposes the raw
      `Depot` instance as-is (its existing `get_parcel`/`set_parcel`/
      `get_pallet` methods); the final, `ArtifactRecord`-aware query
      surface the target-contract tests use
      (`run.repository.get(Estimate)`) is Slice 2C/3A's job.
    - No `NodeRuntime` <-> repository wiring: a `NodeRuntime` does not
      read or write through `run.repository` yet.
    - No rename of `Depot` to `ArtifactRepository` (Milestone 3, slice
      3A; docs/non-goals.md, "Broad Renaming").
    - No new node-participation identity semantics, no distributed
      execution, no advanced scheduling -- unchanged from Milestone 1.

`Run`'s responsibilities in this slice: exist as a distinct object per
`Flow.run()` call, know which `Flow` created it, own a distinct
repository instance, and own a distinct, per-node `NodeRuntime` for each
node materialized through it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

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
    ownership added by Slice 2B).

    See module docstring for the exact scope. `Run` owns an
    identity/ownership boundary plus its own repository instance
    (`.repository`, currently backed directly by `Depot`) and its own
    `NodeRuntime` per materialized node (`.node_runtime(...)`) -- it
    exists so that later slices (2C-2G) have somewhere correct to attach
    `NodeMemory`, artifact commits, and callback dispatch, without any
    of that state ever being stored on `Flow` or `FlowNode`.
    """

    def __init__(self, flow: Flow) -> None:
        self._flow = flow
        self._repository = Depot(bus=Bus.create())
        self._node_runtimes: dict[FlowNode, NodeRuntime] = {}

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
        for flow_node in self._flow.flow_nodes:
            if flow_node.definition.function is node:
                break
        else:
            raise ValueError(
                f"{node!r} is not registered on this Run's Flow via "
                "Flow.add(...)"
            )

        if flow_node not in self._node_runtimes:
            self._node_runtimes[flow_node] = NodeRuntime(self, flow_node)

        return self._node_runtimes[flow_node]
