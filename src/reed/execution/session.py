"""
Session (Slice 2A, part of Priority 11/12 -- `Flow` / `Session` separation;
Slice 2A follow-up -- Session-scoped repository ownership; Slice 2B, part of
Priority 13 -- `NodeSession` ownership; Slice 2E, part of Priority 13 --
the single-firing execution path, `Session.publish(...)`; Slice 21C, GitHub
issue #21 -- firing eligibility evaluated over TRIGGERING-role consumed
types only).

Slice 21C ("Distinguish triggering inputs from sampled inputs in node
firing rules"): a consumed artifact whose `ArtifactDescriptor.input_role`
is `InputRole.SAMPLED` (Slice 21A/21B) still counts toward
`_is_fully_covered` -- the node still cannot be called without a value
for it -- but its arrival never by itself marks it fresh
(`_fresh_since_last_firing`) and never by itself satisfies
`ANY_INPUT_CHANGED`. Concretely: `_record_input` only adds a domain type
to `_fresh_since_last_firing` when that type is one of `flow_node`'s
TRIGGERING-role consumed types (`_triggering_types`); `_is_eligible_to_fire`
now also takes the domain type that just arrived, so
`TriggerPolicy.ANY_INPUT_CHANGED` can refuse to fire when that arrival is
SAMPLED, even if it is the arrival that completes coverage. See
reed-sampled-inputs-proposal.md's acceptance criterion 4 ("a SAMPLED
arrival alone never fires") and
tests/test_slice_21c_run_eligibility_sampled.py.

Scope for this slice (docs/refactor_priority_order.md, Milestone 2, Slice
2A; docs/architectural_decision.md, "Session"):

    Flow
        v (session())
    Session
        v (owns)
    repository (ArtifactRepository, for now -- see below)
    NodeSession instances (one per (Session, FlowNode) pair -- see below)

`Session` represents one concrete execution instance of a `Flow`
(docs/architectural_decision.md: "A `Session` represents one concrete
execution of a flow. It owns execution-specific state, including: shared
state for that execution; node runtime instances; local state for each
node runtime; artifact versions created during the execution; activation
status; event and message history; execution traces."). This slice
establishes the identity/ownership *boundary* -- `Session` is the correct
owner for all of the above -- and, as of the Slice 2A follow-up and Slice
2B below, makes two pieces of that ownership concrete: Session-scoped
repository storage, and Session-scoped `NodeSession` materialization. It does
not implement the rest yet (architectural_invariants.md #4, #6:
`Flow != Session`; `Flow` owns no Session-specific execution state).

Session-scoped repository ownership (Slice 2A follow-up):

    Each `Session` constructs and owns its own repository instance, exposed
    as `session.repository`. For this migration stage the repository is the
    existing `ArtifactRepository`, constructed the same way the current,
    regression-protected execution path already constructs one
    (`reed.synchronization.logistics.Logistics.__init__`):

        bus = Bus.create()
        repository = ArtifactRepository(bus=bus)

    This is the temporary migration strategy
    `docs/refactor_priority_order.md`'s Slice 2A row and its
    accompanying prose describe: "`Session` gets a `.repository` accessor
    from this point on, backed by whatever the current storage class is
    called internally (still `ArtifactRepository` until Milestone 3, slice 3A) ...
    Milestone 2 can and should pass its tests while the underlying
    storage class is still internally called `ArtifactRepository`." It is not the
    final repository architecture: `ArtifactRepository` is not renamed, no
    `ArtifactRecord`-aware `get`/`set` API is defined here, and no
    adapter/protocol/factory layer is introduced. `Session.repository` is a
    plain pass-through to the `ArtifactRepository` instance this `Session` constructed
    for itself -- nothing more.

    Each `Session` gets its own `Bus` and its own `ArtifactRepository`: two `Session`s
    created from the same `Flow` share no repository state and no
    repository identity (`ArtifactRepository.identity` differs because each is built
    from a distinct `Bus`).

    An earlier version of this module deferred `.repository` entirely,
    reasoning that constructing a `ArtifactRepository` pulled in "the full legacy
    transportation/lifecycle stack" and that doing so would read as a
    speculative abstraction under `docs/non-goals.md`. Both reasons were
    wrong on inspection: constructing a `Bus` + `ArtifactRepository` pair is the same
    trivial, already-used, regression-tested two-line pattern
    `Logistics.__init__` already relies on today (no I/O, no threads, no
    sockets -- `Bus.create()` just wraps an in-process `MessageHub()`),
    and `docs/non-goals.md`'s "Repository Exposure" / "Execution
    Infrastructure Exposure" sections are scoped explicitly to
    `NodeContext` and the public node-function-body API, not to `Session`'s
    own accessor -- they say nothing about `Session`. This module corrects
    that deferral rather than leaving it for a later slice; see
    docs/refactor_state.md's Slice 2A record and Refactor State Log for
    the corrected history.

Session-scoped `NodeSession` ownership (Slice 2B):

    `Session.node_session(node)` returns this `Session`'s `NodeSession`
    (`reed.execution.node_session.NodeSession`) for the `FlowNode` whose
    underlying function is `node` -- `node` is the same callable
    originally passed to `Flow.add(...)`, matched by identity, exactly
    as `tests/test_target_architecture_contract.py`'s target-contract
    tests already call it (`session.node_session(track)`; that is the
    accepted access shape, followed here rather than inventing another
    one). The lookup is get-or-create and memoized per `Session`: repeated
    calls for the same node return the same `NodeSession` instance,
    while two different `Session`s -- even created from the same `Flow` --
    never share one, even for the same `FlowNode`
    (architectural_invariants.md #2: `FlowNode != NodeSession`; #3:
    `NodeSession != NodeExecution`). See
    `reed/execution/node_session.py`'s module docstring for
    `NodeSession`'s own exact scope.

Single-firing execution path (Slice 2E; docs/refactor_priority_order.md,
Milestone 2, Slice 2E row):

    `Session.publish(domain_value)` gives `Session` a real, single-firing
    execution path:

        1. find the one `FlowNode` on this `Session`'s `Flow` that consumes
           `type(domain_value)`;
        2. build that node's call arguments -- the published domain
           value for its one consumed dataflow parameter, plus a
           constructed `NodeContext` snapshot
           (`self.node_session(...).context`) for the parameter named by
           `FlowNode.context.parameter_name`, when the node declares one;
        3. call the node function directly (no `NodeExecution` object is
           introduced yet -- see below);
        4. wrap the returned domain value into an `ArtifactRecord` via
           `NodeSession.wrap(...)` and commit it via
           `NodeSession.commit(...)`, which together update
           `session.repository`'s additive `ArtifactRecord` storage
           (`reed/synchronization/depot.py`) and the firing
           `NodeSession`'s `.last_output` in one call.

    This is deliberately narrow, matching this slice's two target
    contracts (`test_session_instances_isolate_node_memory`,
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
      always executes; `Session.publish(...)` does not check execution
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
      `repository.set(...)` API on `Session` itself. `session.repository`
      exposes the raw `ArtifactRepository` instance as-is (its existing
      `get_parcel`/`set_parcel`/`get_pallet` methods, plus Slice 2E's
      additive `set_artifact_record`/`get_artifact_record`); a
      `Session`-level accessor wired into `on_output` dispatch is Slice 2F's
      job.
    - The `Depot` -> `ArtifactRepository` rename itself (Milestone 3,
      slice 3A; docs/non-goals.md, "Broad Renaming") is now done -- this
      module's own `Depot` references were updated by that slice.
    - No new node-participation identity semantics, no distributed
      execution, no advanced scheduling -- unchanged from Milestone 1.

`Session`'s responsibilities in this slice: exist as a distinct object per
`Flow.session()` call, know which `Flow` created it, own a distinct
repository instance, own a distinct, per-node `NodeSession` for each node
materialized through it, and support one real, single-node firing via
`.publish(...)`.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING, Any, Callable

import functools
import time
import uuid
from pathlib import Path

from reed.composition.flow.trigger_policy import TriggerPolicy
from reed.composition.node.artifact_descriptor import InputRole
from reed.execution.node_session import NodeSession
from reed.execution.snapshot import Snapshot
from reed.observability.identity import NodeExecutionIdentity
from reed.observability.provenance import ProvenanceEvent
from reed.observability.trace import ExecutionTrace, TraceEvent, TraceEventType
from reed.observability.presentation import (
    PresentationPolicy,
    resolve_presentation_policy,
)
from reed.observability.presenter import build_presenter
from reed.observability.storage import (
    CSVProvenanceStore,
    CSVRecordingStore,
    ProvenanceStore,
    RecordingStore,
    merge_discovered_instruments,
    write_manifest,
)
from reed.execution.artifact_record import ArtifactOrigin, ArtifactRecord
from reed.synchronization.artifact_repository import ArtifactRepository
from reed.transportation.bus import Bus

if TYPE_CHECKING:
    from reed.composition.flow.flow_composition import Flow
    from reed.composition.flow.flow_node import FlowNode


class Session:
    """
    One concrete execution instance of a `Flow` (Slice 2A; repository
    ownership corrected by the Slice 2A follow-up; `NodeSession`
    ownership added by Slice 2B; single-firing execution path,
    `.publish(...)`, added by Slice 2E).

    See module docstring for the exact scope. `Session` owns an
    identity/ownership boundary plus its own repository instance
    (`.repository`, currently backed directly by `ArtifactRepository`), its own
    `NodeSession` per materialized node (`.node_session(...)`), and a
    single-node firing path (`.publish(...)`) -- it exists so that later
    slices (2F-2G) have somewhere correct to attach callback dispatch and
    stateful-firing serialization, without any of that state ever being
    stored on `Flow` or `FlowNode`.
    """

    def __init__(
        self,
        flow: Flow,
        *,
        storage_root: str | None = None,
        observability: "str | PresentationPolicy | None" = None,
    ) -> None:
        self._flow = flow
        self._repository = ArtifactRepository(bus=Bus.create())
        self._node_sessions: dict[FlowNode, NodeSession] = {}
        # Milestone O1, Slice O1b/O1e: observability identity. `execution_id`
        # is minted once per Session instance; `_execution_seq_counter` is
        # incremented once per node_execution_id minted (Section 13.1 --
        # deterministic observation order, never causality), scoped to
        # this one execution_id.
        self._execution_id: str = str(uuid.uuid4())
        self._execution_seq_counter: int = 0

        # Milestone O3: durable storage is opt-in via `storage_root`
        # (docs/observability_implementation_state.md's O3a-e entry
        # records this as a deliberate default -- omitting `storage_root`
        # keeps Recordings in-memory only, exactly as Milestone O2 left
        # them, so every existing caller of `Flow.session()`/`Session(flow)` is
        # completely unaffected and no test or script silently starts
        # writing files to disk).
        self._recording_store: RecordingStore | None = None
        self._provenance_store: ProvenanceStore | None = None
        self._storage_root: Path | None = None
        if storage_root is not None:
            root = Path(storage_root)
            self._storage_root = root
            write_manifest(
                root, execution_id=self._execution_id, flow_id=flow.flow_id
            )
            # Milestone O7, Slice O7i: instruments.json is no longer
            # written up front from prospectively declared Instruments --
            # there is nothing to write yet at Session-construction time.
            # `.record_discovered_instruments(...)` merges bindings in as
            # NodeSessions discover them during execution.
            run_dir = root / "runs" / self._execution_id
            self._recording_store = CSVRecordingStore(run_dir / "recordings.csv")
            self._provenance_store = CSVProvenanceStore(run_dir / "provenance.csv")
        self.callback_failures: list[BaseException] = []
        self._pending_callback_coroutines: list[Any] = []
        # Slice 2I: per-(Session, FlowNode) join-state bookkeeping for the
        # cascade's TriggerPolicy eligibility check -- see module
        # docstring's "Multi-input joins" section. `_last_known_values`
        # holds the last committed value observed for each consumed
        # domain type ever seen for a FlowNode (needed to build a join's
        # full call-argument set once eligible); `_fresh_since_last_firing`
        # holds the subset of consumed types that have received a value
        # since that FlowNode's last firing (used only to evaluate
        # ALL_INPUTS_CHANGED's "every input is fresh" condition, and reset
        # after each firing).
        self._last_known_values: dict[FlowNode, dict[type, object]] = {}
        self._fresh_since_last_firing: dict[FlowNode, set[type]] = {}

        # Milestone O5, Slice O5a: Level 1 Execution Trace -- an
        # in-memory ring buffer, not required to be durable (design
        # record Section 11.1). Always constructed (unlike
        # recording_store/provenance_store, which are opt-in via
        # `storage_root`): Level 1 has no durability contract to opt in
        # to, so there is no existing-caller behavior to protect by
        # defaulting it off.
        self._trace = ExecutionTrace()

        # Milestone O7, Slice O7d: the terminal presentation layer is a
        # pure *consumer* of the identity/trace/recording data above --
        # constructing it here, after `self._trace` exists, changes
        # nothing about what Reed observes or persists (Recordings/
        # Provenance/Execution Trace collection above is entirely
        # unaffected by `observability=`). `resolve_presentation_policy`
        # compiles a preset name / PresentationPolicy / None into one
        # `PresentationPolicy`; `build_presenter` turns that into a
        # renderer (or `NullPresenter`, a total no-op, for `silent`).
        self._presentation_policy = resolve_presentation_policy(observability)
        self._presenter = build_presenter(self._presentation_policy)

    @property
    def flow(self) -> Flow:
        """The `Flow` that created this `Session` via `Flow.session()`."""
        return self._flow

    @property
    def execution_id(self) -> str:
        """
        This `Session`'s observability identity (Milestone O1, Slice O1b;
        docs/observability_goals.md Section 3): a uuid4 minted once in
        `__init__`, identifying this one concrete execution instance.
        Distinct from `flow_id`, which identifies the logical `Flow`
        definition this `Session` was created from, not this particular
        execution of it.
        """
        return self._execution_id

    @property
    def recording_store(self) -> "RecordingStore | None":
        """
        This `Session`'s `RecordingStore` (Milestone O3), or `None` if this
        `Session` was created with no `storage_root` -- Recordings then stay
        in-memory only (`NodeSession.recordings`), exactly as Milestone
        O2 left them.
        """
        return self._recording_store

    @property
    def provenance_store(self) -> "ProvenanceStore | None":
        """This `Session`'s `ProvenanceStore` (Milestone O4), or `None` -- see `.recording_store`."""
        return self._provenance_store

    def record_discovered_instruments(
        self,
        *,
        node_id: str,
        node_name: str,
        instruments: "list[type]",
    ) -> None:
        """
        Merge newly-discovered Instrument bindings for `node_id` into
        this Flow's `instruments.json` manifest (Milestone O7, Slice
        O7i). Called from `NodeSession.flush_recordings(...)` -- see
        that method's docstring for why this stays proportional to
        genuinely new bindings, not once per `ctx.record(...)` call.
        A no-op if this Session has no `storage_root` configured.
        """
        if self._storage_root is None:
            return
        merge_discovered_instruments(
            self._storage_root,
            flow_id=self._flow.flow_id,
            node_id=node_id,
            node_name=node_name,
            instruments=[
                (
                    instrument.instrument_name(),
                    instrument.kind.value,
                    instrument.unit,
                    instrument.description,
                )
                for instrument in instruments
            ],
        )

    @property
    def presenter(self):
        """This `Session`'s terminal `Presenter` (Milestone O7, Slice O7d)."""
        return self._presenter

    @property
    def presentation_policy(self) -> PresentationPolicy:
        """
        This `Session`'s compiled terminal `PresentationPolicy` (Milestone O7,
        Slice O7d) -- read-only; set once via `Flow.session(observability=...)`.
        """
        return self._presentation_policy

    @property
    def trace(self) -> ExecutionTrace:
        """
        This `Session`'s Level 1 Execution Trace (Milestone O5, Slice O5a): an
        in-memory ring buffer of `TraceEvent`s recording which Node fired,
        in what order, correlated by the same identity Recordings/
        Provenance use. Not durable -- see `docs/observability_design.md`
        Section 11.1 and `reed.observability.trace.ExecutionTrace`.
        """
        return self._trace

    @property
    def flow_id(self) -> str:
        """
        The observability identity of the `Flow` that created this `Session`
        (Milestone O1, Slice O1b) -- a passthrough to `self.flow.flow_id`.
        See `Flow.flow_id` for the derivation and its stability
        guarantees.
        """
        return self._flow.flow_id

    @property
    def repository(self) -> ArtifactRepository:
        """
        This `Session`'s own repository instance.

        Backed directly by `ArtifactRepository` for this migration stage (Slice 2A
        follow-up; docs/refactor_priority_order.md's Slice 2A row).
        Every `Session` constructs its own `Bus` + `ArtifactRepository` pair, so two
        `Session`s -- even from the same `Flow` -- never share repository
        state or repository identity.
        """
        return self._repository

    def _commit(
        self,
        value: object,
        *,
        origin: "ArtifactOrigin",
        producer: "NodeSession | None" = None,
    ) -> "ArtifactRecord":
        """
        The one shared commit operation (Slice 22D,
        docs/refactor/session_snapshot_decision.md section 6 "Unified
        versioning and ArtifactOrigin"; architectural invariants #10,
        #27, #28).

        Both real commit paths route through here instead of two
        parallel implementations: `NodeSession.wrap()` (this slice)
        calls it with `origin=ArtifactOrigin.NODE, producer=<that
        NodeSession>`; the not-yet-implemented `Session.feed()` (Slice
        22E) will call it with `origin=ArtifactOrigin.EXTERNAL,
        producer=None`.

        Reads `self.repository.get_artifact_record(type(value))`. If a
        record already exists for that domain type, advances it in
        place (`ArtifactRecord.advance(...)`, Slice 22C) and returns
        that *same* object -- so the next version for a type is always
        derived from that type's *current* `ArtifactRecord` in the
        repository (invariant #28), never from a private, per-node or
        per-type running counter. If absent, constructs a fresh
        `ArtifactRecord` holding `value` and advances its (freshly
        default-constructed, pending) provenance exactly once --
        `ArtifactVersion.pending()` (0) -> `.next()` == `.initial()`
        (1) -- via the same `ArtifactProvenance.advance(...)` mechanic
        `ArtifactRecord.advance()` itself uses, so a first commit here
        is byte-identical to a first commit via the in-place path: same
        version (`ArtifactVersion.initial()`), same `origin`, same
        `producer`, same empty `dependencies`. Stores the new record via
        `self.repository.set_artifact_record(...)` and returns it.
        """
        existing = self._repository.get_artifact_record(type(value))
        if existing is not None:
            existing.advance(value, origin=origin, producer=producer)
            return existing

        record = ArtifactRecord(value=value)
        record.provenance.advance(origin=origin, producer=producer)
        self._repository.set_artifact_record(record)
        return record

    def feed(self, value: object) -> None:
        """
        Record and commit an externally supplied domain value (Slice 22E;
        docs/refactor/session_snapshot_decision.md section 4 "`feed()` is a
        node"; architectural_invariants.md #10, #29, #30, #31).

        `feed()` is modeled architecturally as a node whose function is the
        identity, triggered manually instead of by the eligibility cascade:

        1. Performs the existing input-recording bookkeeping unchanged, via
           `._record_input(...)` -- the same method `publish(...)`'s cascade
           loop calls -- for every `FlowNode` on this `Session`'s `Flow` that
           consumes `type(value)` (`self._flow.dependency_graph.consumers_of`).
           This updates `_last_known_values` per consuming `FlowNode` and marks
           `_fresh_since_last_firing` only for `InputRole.TRIGGERING` consumed
           types (issue #21's existing distinction) -- a `SAMPLED` edge is
           still recorded but never marked fresh by this alone.
        2. Commits `value` into `self.repository` through the same shared
           commit path a node firing uses (`Session._commit`, Slice 22D),
           tagged `origin=ArtifactOrigin.EXTERNAL, producer=None`. Per
           invariant 30, this deliberately performs no
           `DuplicateArtifactProducerError`-style guard against `type(value)`
           already having a declared producer `FlowNode` -- `feed()` never
           participated in the declared `Flow`/`ArtifactDependencyGraph`
           composition graph in the first place (invariant 10 governs only
           `Flow.add(...)`-registered `FlowNode`s against each other), so
           overwriting a declared producer's type here is an intentional
           escape hatch, not a bug. `Session._commit`'s fresh-record path
           (no prior `ArtifactRecord` for the type) never sets
           `dependencies`, so the resulting record's `dependencies` is always
           `{}` -- a fed value depends on nothing.
        3. Fires the same observability hooks a node firing does, via the
           exact methods `Session._fire(...)` calls around a node's own
           commit (reused here, not duplicated): a `"node_finished"`
           `TraceEvent` (`._record_trace_event`) and a `"generated"`
           `ProvenanceEvent` (`._emit_generated_provenance_event`), both
           keyed to a freshly minted `NodeExecutionIdentity` exactly as a
           real firing mints one (`._begin_node_execution`'s own pattern:
           `self._execution_seq_counter` incremented once, a fresh
           `node_execution_id`). Because `feed()` has no `FlowNode` of its
           own -- it is a node only in the identity-function sense, never a
           `Flow.add(...)`-registered one -- its `node_id` is the fed
           domain type's own stable identity (`._artifact_id`, the same
           `module.qualname` derivation `FlowNode.node_id` itself uses, per
           `._artifact_id`'s own docstring): "the node" `feed()` models here
           IS the type's identity function, so its identity-bundle `node_id`
           is the type's identity. If `type(value)` has a declared producer
           `FlowNode` (`self._flow.dependency_graph.producer_of`), that
           producer's `on_output` is dispatched with the fed value
           (`._dispatch_on_output`, unchanged) -- the same callback that
           would run had that producer computed this value itself, since
           from `on_output`'s perspective (invariant 21: "executes only
           after successful commit"; invariant 22: "receives domain
           values") a fresh, successfully committed value for its type is
           what it reacts to, regardless of which commit path produced it.
           If no producer is declared for the type, there is no `on_output`
           to dispatch, exactly as an undeclared `on_output` is already a
           no-op elsewhere in this module. This is a genuine, deliberate
           behavior change from today's `publish()`, which fires none of
           this for a root-published value -- not suppressed here.

        Does **not** evaluate firing eligibility and does **not** fire any
        node itself (invariant 31) -- that is `Session.push()`'s job
        (Slice 22F, not yet implemented).
        """
        domain_type = type(value)

        for flow_node in self._flow.dependency_graph.consumers_of(domain_type):
            self._record_input(flow_node, domain_type, value)

        record = self._commit(value, origin=ArtifactOrigin.EXTERNAL, producer=None)

        self._execution_seq_counter += 1
        identity = NodeExecutionIdentity(
            execution_id=self._execution_id,
            flow_id=self.flow_id,
            node_id=self._artifact_id(domain_type),
            node_execution_id=str(uuid.uuid4()),
            execution_seq=self._execution_seq_counter,
        )

        self._record_trace_event("node_finished", identity)
        self._emit_generated_provenance_event(record, identity)

        producer_node = self._flow.dependency_graph.producer_of(domain_type)
        if producer_node is not None:
            self._dispatch_on_output(producer_node, record.value)


    def push(self) -> None:
        """
        Fire every `FlowNode` made eligible by a `feed()` since the last
        `push()`, cascading to quiescence (Slice 22F;
        docs/refactor/session_snapshot_decision.md section 5 "`push()` and
        `snapshot()`"; architectural_invariants.md #18, #19, #31, #32).

        Adapts `publish()`'s existing eligibility -> fire ->
        cascade-to-quiescence loop (unchanged there -- see
        `Session.publish`'s own docstring; this method has its own,
        separate copy of that loop so `publish()` remains byte-for-byte
        untouched until it is removed in Slice 22H) so that it is seeded
        by every `FlowNode` that has received a `feed()`-driven
        TRIGGERING-role arrival since the last `push()`, instead of by
        one directly-published value's consumers.

        Seed set: every `FlowNode` with a non-empty
        `_fresh_since_last_firing` entry -- the exact "since last
        firing" freshness bookkeeping `_record_input` already maintains
        for `publish()`'s own `ALL_INPUTS_CHANGED` gate, and that
        `feed()` (Slice 22E) already populates for TRIGGERING-role
        consumed types only (issue #21's SAMPLED/TRIGGERING split,
        unchanged and reused here -- a `feed()` of a SAMPLED-role value
        alone never adds anything to this set, so it can never seed a
        node). A `FlowNode` in this set may hold values for more than
        one recently-fed TRIGGERING type at once; any one of them is a
        valid stand-in for "arrived_domain_type" in
        `_is_eligible_to_fire`, since `ALL_INPUTS_CHANGED` ignores that
        argument entirely and `ANY_INPUT_CHANGED` only checks that it is
        TRIGGERING-role -- true by construction for every member of this
        set.

        Each seeded node is checked for full coverage
        (`_is_fully_covered`) and `TriggerPolicy` eligibility
        (`_is_eligible_to_fire`) exactly as `publish()`'s loop checks a
        newly-arrived value's consumers, then fired (`_fire`) if both
        hold; its committed output seeds the same FIFO
        cascade-to-quiescence loop `publish()` runs, so downstream
        nodes fire in turn using the identical mechanism, all the way
        to quiescence (multi-hop cascades behave exactly as they do
        under `publish()`).

        Resetting "since last push": every `FlowNode` this call actually
        fires (from the seed pass or from the cascade) has its
        `_fresh_since_last_firing` entry cleared to the empty set
        immediately after it fires -- regardless of `TriggerPolicy`
        (`_fire()` itself only clears this for `ALL_INPUTS_CHANGED`,
        since that is all `publish()` ever needed; `push()` additionally
        clears it here for `ANY_INPUT_CHANGED` firings too, since an
        `ANY_INPUT_CHANGED` node's freshness would otherwise never be
        spent and would wrongly re-seed the next `push()` call with no
        intervening `feed()`). A seeded node that is *not* fired this
        call (not fully covered yet, or `TriggerPolicy` says wait) keeps
        its freshness untouched, exactly like `publish()` today -- so
        that partial progress toward `ALL_INPUTS_CHANGED` coverage made
        by one `feed()` is not silently discarded by an intervening
        `push()` that could not yet fire it. Together, this makes a
        second `push()` with no intervening `feed()` a genuine no-op:
        every node that fired last time now has an empty freshness set
        (so it is not reseeded), and every node that did not fire is
        re-evaluated against unchanged state and again does not fire --
        quiescent immediately, nothing fires (invariant #18: dirty state
        does not imply immediate execution).

        Returns `None`, strictly (invariant #32) -- unlike `publish()`,
        there is no "direct result" to report; `Session.snapshot()`
        (Slice 22G, not yet implemented) is the separate call for
        reading resulting state.
        """
        seeded_flow_nodes = [
            flow_node
            for flow_node, fresh in self._fresh_since_last_firing.items()
            if fresh
        ]

        pending: list[tuple[object, int]] = []

        for flow_node in seeded_flow_nodes:
            if not self._is_fully_covered(flow_node):
                # Not every consumed type has a value yet -- discovered
                # via feed(), but not callable, regardless of
                # TriggerPolicy. Its freshness is left untouched so a
                # later feed() completing coverage can still find it.
                continue

            arrived_domain_type = next(
                iter(self._fresh_since_last_firing[flow_node])
            )
            if not self._is_eligible_to_fire(flow_node, arrived_domain_type):
                # Covered but TriggerPolicy says wait. Freshness is left
                # untouched (e.g. ALL_INPUTS_CHANGED still needs another
                # TRIGGERING type fed before every consumed TRIGGERING
                # type is fresh at once).
                continue

            identity = self._begin_node_execution(flow_node)
            call_kwargs = self._build_call_kwargs(flow_node, identity)
            result = self._fire(flow_node, call_kwargs, identity, depth=0)
            self._fresh_since_last_firing[flow_node] = set()
            pending.append((result, 1))

        while pending:
            current_value, depth = pending.pop(0)
            domain_type = type(current_value)

            consumers = self._flow.dependency_graph.consumers_of(domain_type)

            for flow_node in consumers:
                self._record_input(flow_node, domain_type, current_value)

                if not self._is_fully_covered(flow_node):
                    continue

                if not self._is_eligible_to_fire(flow_node, domain_type):
                    continue

                identity = self._begin_node_execution(flow_node)
                call_kwargs = self._build_call_kwargs(flow_node, identity)
                result = self._fire(flow_node, call_kwargs, identity, depth=depth)
                self._fresh_since_last_firing[flow_node] = set()
                pending.append((result, depth + 1))

        return None

    def snapshot(self) -> Snapshot:
        """
        The full current state of this `Session`'s repository, as plain
        domain values (Slice 22G;
        docs/refactor/session_snapshot_decision.md section 5 "`push()` and
        `snapshot()`"; architectural_invariants.md #33).

        Reads every domain type currently committed in `self.repository` at
        the moment this method is called -- not scoped to whatever the most
        recent `push()` touched -- and returns an immutable `Snapshot`
        exposing plain domain values only, never `ArtifactRecord`
        (`reed/execution/snapshot.py`'s own docstring covers why and how).
        There is no automatic history: each call builds a fresh `Snapshot`
        reflecting repository state at that moment, and a later commit into
        the repository never changes a `Snapshot` already returned.
        `self.repository` remains the lower-level escape hatch it is today
        ("latest known value of X, whenever committed"); `snapshot()`
        answers "what does the repository look like right now."
        """
        return Snapshot.from_repository(self._repository)

    def invoke(self, value: object) -> Snapshot:
        """
        Convenience, single-input round trip (Slice 22G;
        docs/refactor/session_snapshot_decision.md section 8 "Target public
        API reference").

        Equivalent to calling `feed(value)`, then `push()`, then
        `snapshot()`, and returning that `Snapshot` -- for the common case
        of feeding exactly one value and immediately wanting the resulting
        state back, without a caller needing to sequence the three calls
        itself.
        """
        self.feed(value)
        self.push()
        return self.snapshot()

    def node_session(self, node: Callable) -> NodeSession:
        """
        This `Session`'s `NodeSession` for the `FlowNode` wrapping `node`
        (Slice 2B).

        `node` is the original callable passed to `Flow.add(...)`,
        matched by identity against each of this `Session`'s `Flow`'s
        registered `FlowNode`s. Get-or-create and memoized per `Session`:
        calling this twice for the same node returns the same
        `NodeSession`; calling it on a different `Session` never does, even
        for the same node.

        Raises `ValueError` if `node` was never registered on this
        `Session`'s `Flow` via `Flow.add(...)`.
        """
        flow_node = self._find_flow_node(node)

        if flow_node not in self._node_sessions:
            self._node_sessions[flow_node] = NodeSession(self, flow_node)

        return self._node_sessions[flow_node]

    def _consumed_types(self, flow_node: "FlowNode") -> set[type]:
        return {
            descriptor.domain_type for descriptor in flow_node.consumed_artifacts
        }

    def _triggering_types(self, flow_node: "FlowNode") -> set[type]:
        """
        The subset of `flow_node`'s consumed types whose
        `ArtifactDescriptor.input_role` is `InputRole.TRIGGERING` (Slice
        21C) -- the only types whose arrival can ever mark `flow_node`
        fresh (`_record_input`) or, under `ANY_INPUT_CHANGED`, fire it
        by itself (`_is_eligible_to_fire`). Coverage
        (`_is_fully_covered`) is unaffected by this distinction and
        still requires every consumed type, TRIGGERING and SAMPLED
        alike.
        """
        return {
            descriptor.domain_type
            for descriptor in flow_node.consumed_artifacts
            if descriptor.input_role is InputRole.TRIGGERING
        }

    def _record_input(
        self, flow_node: "FlowNode", domain_type: type, value: object
    ) -> None:
        """
        Record `value` as the last-known committed value for
        `domain_type` on `flow_node` (Slice 2I), and -- only when
        `domain_type` is one of `flow_node`'s TRIGGERING-role consumed
        types (Slice 21C) -- mark it fresh since `flow_node`'s last
        firing. A SAMPLED-role arrival still updates
        `_last_known_values` unconditionally (so a later TRIGGERING
        firing can use its latest value), but never enters
        `_fresh_since_last_firing`: it must never by itself cause
        `ALL_INPUTS_CHANGED` to consider every input fresh, nor (via
        `_is_eligible_to_fire`'s `arrived_domain_type` check)
        `ANY_INPUT_CHANGED` to fire.

        Populated as commits are observed by the cascade's existing
        find-consumers loop -- no new traversal, no new index.
        """
        self._last_known_values.setdefault(flow_node, {})[domain_type] = value

        if domain_type in self._triggering_types(flow_node):
            self._fresh_since_last_firing.setdefault(flow_node, set()).add(domain_type)

    def _is_fully_covered(self, flow_node: "FlowNode") -> bool:
        """
        Whether every one of `flow_node`'s consumed types has at least
        one last-known value -- required before it can ever be called,
        regardless of TriggerPolicy (Slice 2I).
        """
        known = self._last_known_values.get(flow_node, {})
        return self._consumed_types(flow_node) <= known.keys()

    def _is_eligible_to_fire(
        self, flow_node: "FlowNode", arrived_domain_type: type
    ) -> bool:
        """
        TriggerPolicy eligibility check, given `flow_node` is already
        fully covered (Slice 2I; extended by Slice 21C to distinguish
        TRIGGERING from SAMPLED consumed types --
        architectural_invariants.md #18-20).

        - MANUAL: never eligible via the cascade.
        - ALL_INPUTS_CHANGED: eligible once every TRIGGERING-role
          consumed type is fresh since the last firing (or since ever,
          before the first firing). A SAMPLED type's freshness is never
          tracked (`_record_input`), so it can neither block nor force
          this condition.
        - ANY_INPUT_CHANGED: eligible once full coverage is reached
          (already guaranteed by the caller) *and* the arrival that
          triggered this evaluation is itself TRIGGERING-role. A
          SAMPLED arrival that happens to complete or refresh coverage
          must not, by itself, fire the node (reed-sampled-inputs-
          proposal.md acceptance criterion 4) -- the node still fires
          on the next TRIGGERING arrival, using that SAMPLED value's
          latest last-known value (`_build_call_kwargs`).

        This originally read `self._consumed_types(flow_node) <= fresh`
        for ALL_INPUTS_CHANGED, which would be permanently unsatisfiable
        for a node with any SAMPLED consumed type once Slice 21C's
        `_record_input` stopped marking SAMPLED arrivals fresh -- fixed
        here rather than assumed correct, per this slice's own
        SliceContract stop_condition ("confirm this by test, don't
        assume it"); see
        tests/test_slice_21c_run_eligibility_sampled.py.
        """
        policy = flow_node.trigger_policy

        if policy is TriggerPolicy.MANUAL:
            return False

        if policy is TriggerPolicy.ALL_INPUTS_CHANGED:
            fresh = self._fresh_since_last_firing.get(flow_node, set())
            return self._triggering_types(flow_node) <= fresh

        # TriggerPolicy.ANY_INPUT_CHANGED
        return arrived_domain_type in self._triggering_types(flow_node)

    def _build_call_kwargs(
        self, flow_node: "FlowNode", identity: NodeExecutionIdentity
    ) -> dict[str, object]:
        """
        Build `flow_node`'s full call-argument set from its last-known
        values (Slice 2I) -- one value per consumed parameter, using
        each type's most recently observed value (substituting the
        just-arrived value for its own type, since `_record_input` is
        always called before this).
        """
        known = self._last_known_values[flow_node]

        call_kwargs: dict[str, object] = {
            descriptor.name: known[descriptor.domain_type]
            for descriptor in flow_node.consumed_artifacts
        }

        if flow_node.context is not None:
            node_session = self.node_session(flow_node.definition.function)
            recorder = functools.partial(node_session.accept_recording, identity)
            call_kwargs[flow_node.context.parameter_name] = (
                node_session.build_context(identity, recorder)
            )

        return call_kwargs

    def _begin_node_execution(self, flow_node: "FlowNode") -> NodeExecutionIdentity:
        """
        Mint the observability identity for one Node firing (Milestone
        O1, Slice O1d/O1e/O1f).

        Called once per firing, from the `publish(...)` cascade loop,
        before `._build_call_kwargs(...)` -- every firing gets an
        identity, whether or not its Node declares a `NodeContext`
        parameter, so Milestone O4's provenance events have a
        `node_execution_id`/`execution_seq` to attach to regardless
        (docs/observability_design.md Section 18/21).

        `node_execution_id` is a fresh uuid4 per call (one per firing,
        never reused). `execution_seq` is this `Session`'s own monotonic
        counter, incremented once per call -- a deterministic
        observation order scoped to this `execution_id`, never a
        causality claim (Section 13.1; docs/observability_invariants.md
        #7-9).
        """
        self._execution_seq_counter += 1
        return NodeExecutionIdentity(
            execution_id=self._execution_id,
            flow_id=self.flow_id,
            node_id=flow_node.node_id,
            node_execution_id=str(uuid.uuid4()),
            execution_seq=self._execution_seq_counter,
        )

    def _fire(
        self,
        flow_node: "FlowNode",
        call_kwargs: dict[str, object],
        identity: NodeExecutionIdentity,
        *,
        depth: int = 0,
    ) -> object:
        """
        Fire one `FlowNode` with `call_kwargs` as its full call
        arguments (Slice 2E; generalized to multi-input joins by Slice
        2I -- `call_kwargs` now covers every consumed parameter plus an
        optional `NodeContext` snapshot, built by
        `._build_call_kwargs(...)`, instead of always being a single
        domain value).

        Calls the node function, wraps the returned domain value into
        an `ArtifactRecord`, commits it into `self.repository`, updates
        the firing `NodeSession`'s `.last_output`, dispatches
        `on_output`, and -- for `TriggerPolicy.ALL_INPUTS_CHANGED` --
        clears `flow_node`'s freshness set so a later partial update
        round does not immediately re-trigger it. Returns the produced
        domain value (`record.value`).

        Milestone O4 (Slices O4b/O4c): emits a `"used"` provenance event
        for each of `flow_node`'s consumed artifact types that already
        has a committed `ArtifactRecord` (nothing to report the first
        time a type is consumed with no prior producer), before calling
        the node function, and a `"generated"` event for the artifact
        this firing itself commits, after `.commit(...)` succeeds. Both
        are no-ops when this `Session` has no `provenance_store` configured
        (`storage_root` was not passed to `Flow.session(...)`).

        Milestone O5 (Slice O5a): records a `"node_started"` `TraceEvent`
        into `self.trace` before calling the node function, and a
        `"node_finished"` `TraceEvent` after it commits -- unconditional,
        unlike Provenance/Recordings, since Level 1 has no opt-in
        (design record Section 11.1; `self._trace` is always constructed).

        Milestone O7 (Slice O7c): flushes this firing's buffered
        `Recording`s (`node_session.flush_recordings(...)`) in a `finally`
        block covering the node function call -- the NodeExecution
        durability boundary applies whether the firing succeeds or
        raises (docs/observability_goals.md Section 5), not only on the
        success path.
        """
        node_session = self.node_session(flow_node.definition.function)

        self._emit_used_provenance_events(flow_node, identity)
        self._record_trace_event("node_started", identity)
        self._safe_presenter_call(self._presenter.on_node_started, identity, depth=depth)

        firing_lock = node_session.firing_lock

        start_time = time.monotonic()
        if firing_lock is not None:
            firing_lock.acquire()
        try:
            try:
                result = flow_node.definition.function(**call_kwargs)

                record = node_session.wrap(result)
                node_session.commit(record)
            except BaseException as exc:
                # Milestone O7, Slice O7d: report the failure to the
                # terminal presenter -- a pure observer, never a handler
                # (the exception always propagates unchanged; invariant
                # #25, "observability failures must never change
                # application semantics," read here in its stronger form:
                # observability *reporting* must not change application
                # semantics either).
                self._safe_presenter_call(
                    self._presenter.on_node_error,
                    identity,
                    exc,
                    duration=time.monotonic() - start_time,
                )
                raise
            finally:
                node_session.flush_recordings(identity.node_execution_id)
        finally:
            if firing_lock is not None:
                firing_lock.release()

        duration = time.monotonic() - start_time

        self._record_trace_event("node_finished", identity)
        self._safe_presenter_call(self._presenter.on_node_finished, identity, depth=depth, duration=duration)

        self._emit_generated_provenance_event(record, identity)

        if flow_node.trigger_policy is TriggerPolicy.ALL_INPUTS_CHANGED:
            self._fresh_since_last_firing[flow_node] = set()

        self._dispatch_on_output(flow_node, record.value)

        return record.value

    @staticmethod
    def _artifact_id(domain_type: type) -> str:
        """
        Milestone O4: an Artifact type's provenance identity --
        deliberately the same `module.qualname` derivation
        `FlowNode.node_id` uses (Section 18), for the same reason: stable
        across process runs, no user-supplied identifier required.
        """
        return f"{domain_type.__module__}.{domain_type.__qualname__}"

    def _emit_used_provenance_events(
        self, flow_node: "FlowNode", identity: NodeExecutionIdentity
    ) -> None:
        """
        Emits a durable `"used"` `ProvenanceEvent` per consumed Artifact type
        with a prior producer (only when `self._provenance_store` is
        configured -- Milestone O3/O4's own opt-in), and -- independently,
        Milestone O8, Slice O8b -- reports the same fact to the terminal
        `Presenter` via `on_artifact_consumed`, regardless of whether durable
        storage is configured. Presentation must never depend on the durable
        storage opt-in (docs/observability_invariants.md #35): a `Session` with no
        `storage_root` still renders `propagation` terminal output.
        """
        for descriptor in flow_node.consumed_artifacts:
            existing = self._repository.get_artifact_record(descriptor.domain_type)
            if existing is None:
                # Nothing produced this type yet -- no "used" event to
                # emit (there is no artifact_version to report).
                continue

            if self._provenance_store is not None:
                self._provenance_store.append(
                    ProvenanceEvent(
                        event_type="used",
                        artifact_id=self._artifact_id(descriptor.domain_type),
                        artifact_version=existing.version.number,
                        node_execution_id=identity.node_execution_id,
                        node_id=identity.node_id,
                        execution_seq=identity.execution_seq,
                    )
                )

            self._safe_presenter_call(
                self._presenter.on_artifact_consumed,
                identity,
                artifact_type=descriptor.domain_type.__name__,
                artifact_version=existing.version.number,
            )

    def _emit_generated_provenance_event(
        self, record: "ArtifactRecord", identity: NodeExecutionIdentity
    ) -> None:
        """
        Emits a durable `"generated"` `ProvenanceEvent` (only when
        `self._provenance_store` is configured), and -- independently,
        Milestone O8, Slice O8b -- reports the same fact to the terminal
        `Presenter` via `on_artifact_generated`, regardless of durable
        storage configuration (see `_emit_used_provenance_events` docstring).
        """
        if self._provenance_store is not None:
            self._provenance_store.append(
                ProvenanceEvent(
                    event_type="generated",
                    artifact_id=self._artifact_id(type(record.value)),
                    artifact_version=record.version.number,
                    node_execution_id=identity.node_execution_id,
                    node_id=identity.node_id,
                    execution_seq=identity.execution_seq,
                )
            )

        self._safe_presenter_call(
            self._presenter.on_artifact_generated,
            identity,
            artifact_type=type(record.value).__name__,
            artifact_version=record.version.number,
        )

    def _safe_presenter_call(self, hook, *args, **kwargs) -> None:
        """
        Milestone O7, Slice O7g (final invariant audit finding): call a
        `Presenter` hook, isolating any exception it raises so that a
        rendering failure (a broken terminal, a Rich/Console error, a
        custom `Presenter` subclass with a bug) can never change
        application semantics -- architectural invariant #25 ("Observability
        failures must never change application semantics"), extended here
        explicitly to the O7d/O7e Presenter hooks. `Presenter` is a pure
        observer of data Reed has already committed (Trace/Provenance/
        Recording); nothing a Presenter does can undo or affect that
        already-committed state, so a Presenter exception is swallowed
        rather than isolated into a reportable list (unlike
        `callback_failures`, which reports user-authored `on_output`
        callback failures because those are part of the Flow's declared
        behavior) -- there is no equivalent public surface for terminal
        rendering errors, and inventing one would risk becoming a second,
        competing observability channel.
        """
        try:
            hook(*args, **kwargs)
        except BaseException:  # noqa: BLE001 -- isolate any presenter/rendering failure
            pass

    def _record_trace_event(
        self, event_type: TraceEventType, identity: NodeExecutionIdentity
    ) -> None:
        """
        Milestone O5, Slice O5a: append one `TraceEvent` to `self.trace`
        (Level 1 Execution Trace, design record Section 11.1).
        Unconditional -- unlike Recordings/Provenance (Milestone O2-O4),
        Level 1 has no `storage_root` opt-in and no store to be `None`.
        """
        self._trace.record(
            TraceEvent(
                event_type=event_type,
                execution_id=identity.execution_id,
                flow_id=identity.flow_id,
                node_id=identity.node_id,
                node_execution_id=identity.node_execution_id,
                execution_seq=identity.execution_seq,
                timestamp=time.time(),
            )
        )

    def _dispatch_on_output(self, flow_node: "FlowNode", domain_value: object) -> None:
        """
        Invoke `flow_node`'s declared `on_output` callback with
        `domain_value`, strictly after `NodeSession.commit(...)` has
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
            f"{node!r} is not registered on this Session's Flow via "
            "Flow.add(...)"
        )
