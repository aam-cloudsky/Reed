"""
NodeRuntime (Slice 2B, part of Priority 13 -- `Node` -> `NodeRuntime`,
runtime-ownership portion; Slice 2C, part of Priority 13 -- the
`ArtifactRecord` unwrap boundary; Slice 2D, part of Priority 13 -- memory
and `.context` construction; Slice 2E, part of Priority 13 -- wrap/commit,
the firing-tied direction).

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

Slice 2D added NodeMemory ownership and `.context` construction
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
        .last_output   -- the latest committed domain output, set by
                           `.commit(record)` (Slice 2E). `None` until this
                           NodeRuntime's first successful commit.
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

Slice 2E adds the firing-tied, commit direction (docs/refactor_priority_
order.md, Milestone 2, Slice 2E row; docs/parcel_boundary_decision.md,
"Parcel As Internal Envelope" -- `wrap: U -> Parcel[U]`, read here as
`wrap: DomainValue -> ArtifactRecord[DomainValue]`):

    NodeRuntime
        .wrap(domain_value)   -- wraps a returned domain value into a
                                  fresh ArtifactRecord, with this
                                  NodeRuntime recorded as its producer
                                  (docs/architectural_decision.md's
                                  ArtifactProvenance.producer) and its
                                  version advanced from pending (0) to
                                  initial (1).
        .commit(record)       -- the successful-commit path only
                                  (docs/node_context_decision.md,
                                  "Transaction Semantics"): stores
                                  `record` into `self.run.repository`'s
                                  additive ArtifactRecord storage (see
                                  `reed/synchronization/depot.py`,
                                  `set_artifact_record`) and updates
                                  `self._last_output` to `record.value`
                                  together, in that order, so both moves
                                  happen as one call. Failure/rollback
                                  semantics for a firing that raises
                                  partway through are explicitly out of
                                  scope for this slice (see
                                  `run.py`'s `publish` docstring and the
                                  SliceContract's stop_conditions) --
                                  neither target test this slice must
                                  pass exercises them.

`Run.publish(domain_value)` (`reed/execution/run.py`, Slice 2E) is what
actually calls `.wrap(...)` and `.commit(...)` as part of one firing; this
class only owns the two operations themselves, not the decision of when
to fire.

Explicitly out of scope for this slice (Milestone 2, later slices; see
`docs/refactor_priority_order.md`'s Priority 13 "Recommended work" items
3-8, split across 2C-2G by the Priority-To-Slice Traceability table):

    - No `on_output` dispatch (sync or async), no `callback_failures`
      (2F).
    - No stateful-firing serialization (architectural_invariants.md #17,
      2G) -- `.commit(...)` here is not itself a lock/serialization
      mechanism; concurrent firings of the same NodeRuntime are not
      guarded against yet.
    - No transactional rollback for a firing that fails partway through
      wrap/commit -- only the successful-commit path is implemented (see
      above and the SliceContract's stop_conditions for why guessing a
      rollback mechanism here would be wrong).
    - No multi-node dispatch/routing, no TriggerPolicy-gated execution
      eligibility -- both remain `Run.publish(...)`'s concern (2E) and,
      for TriggerPolicy specifically, out of this slice entirely.
    - No new executors, schedulers, managers, factories, or lifecycle
      frameworks.

`NodeRuntime`'s responsibilities in this slice: exist as a distinct
object per (`Run`, `FlowNode`) pair, know which `Run` and which
`FlowNode` it materializes, unwrap an `ArtifactRecord` into its domain
value on request, own a private, node-local memory instance and a
last-committed-output slot (both scoped to itself), construct a
`NodeContext` snapshot exposing both, and wrap/commit a successfully
produced domain value into the run's repository.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from reed.composition.node.node_context import NodeContext
from reed.execution.artifact_record import ArtifactRecord
from reed.observability.identity import NodeExecutionIdentity
from reed.observability.instrument import Instrument
from reed.observability.recording import Recording, ScalarValue

if TYPE_CHECKING:
    from reed.composition.flow.flow_node import FlowNode
    from reed.execution.run import Run


class NodeRuntime:
    """
    One node participation (`FlowNode`) materialized inside one `Run`
    (Slice 2B; `ArtifactRecord` unwrap boundary added by Slice 2C; memory
    and `.context` construction added by Slice 2D; wrap/commit added by
    Slice 2E).

    See module docstring for the exact scope: an identity/ownership
    boundary, a pure unwrap operation, a private, node-local memory
    instance plus a `.context` snapshot, and now the wrap/commit
    operations `Run.publish(...)` uses to complete one firing.
    `NodeRuntime` still owns no execution-eligibility policy and no
    callback dispatch -- it exists so that later slices (2F-2G) have
    somewhere correct to attach callback dispatch and stateful-firing
    serialization, without any of that state ever being stored on
    `FlowNode` (which remains reusable Flow-local composition metadata)
    or on `Flow` itself.
    """

    def __init__(self, run: Run, flow_node: FlowNode) -> None:
        self._run = run
        self._flow_node = flow_node
        self._memory: object | None = None
        self._last_output: object | None = None
        self._firing_lock: threading.Lock | None = None
        # Milestone O2, Slice O2c/O2d: in-memory Recording buffer (Level 2
        # precursor -- Milestone O3 gives it a durable store) plus the
        # lazy-mode registry that makes "first observed kind/unit wins"
        # enforceable (docs/observability_goals.md Section 2.3).
        self._recordings: list[Recording] = []
        # name -> authoritative unit for a lazily-declared (undeclared
        # Instrument) name -- Slice O2d's "first observed unit wins" rule.
        self._lazy_units: dict[str, str | None] = {}
        self._declared_instruments: dict[str, Instrument] = {
            instrument.name: instrument for instrument in flow_node.instruments
        }

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

    def wrap(self, domain_value: object) -> "ArtifactRecord":
        """
        Wrap `domain_value` -- a node function's returned domain value --
        into a fresh `ArtifactRecord` (Slice 2E).

        This `NodeRuntime` is recorded as the record's producer and its
        provenance is advanced once (pending (0) -> initial (1) on first
        firing, matching `ArtifactProvenance.advance`'s existing,
        regression-tested version mechanics from Slice 2C). This is the
        "wrap" half of docs/parcel_boundary_decision.md's boundary
        diagram (`U -> wrap -> Parcel[U]`, read here as `ArtifactRecord`);
        it does not commit anything by itself -- see `.commit(...)`.
        """
        record: ArtifactRecord = ArtifactRecord(value=domain_value)
        record.provenance.advance(producer=self)
        return record

    def commit(self, record: "ArtifactRecord") -> None:
        """
        Commit `record` -- the successful-commit path only (Slice 2E).

        Stores `record` into `self.run.repository`'s additive,
        domain-type-keyed `ArtifactRecord` storage
        (`reed/synchronization/depot.py`, `set_artifact_record`,
        docs/parcel_boundary_decision.md's "Addendum: Slice 2E
        ArtifactRecord Commit Storage") and updates `self._last_output`
        to `record.value`, so that both the repository commit and the
        local `last_output` transition happen together
        (docs/node_context_decision.md, "Transaction Semantics":
        "successful firing -> memory transition and output publication
        commit together"). Only the successful path is implemented here
        -- a firing that raises before reaching `.commit(...)` leaves
        both untouched, which already satisfies "failed firing -> no
        committed memory transition and no committed output" for that
        case; a firing that fails *partway through* wrap/commit is
        explicitly out of scope (see module docstring and the
        SliceContract's stop_conditions).
        """
        self._run.repository.set_artifact_record(record)
        self._last_output = record.value

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
        `NodeRuntime` (Slice 2D representation; wired to a real
        committed value by `.commit(...)`, Slice 2E). `None` until this
        `NodeRuntime` has completed its first successful commit.

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
    def firing_lock(self) -> "threading.Lock | None":
        """
        This `NodeRuntime`'s own mutual-exclusion primitive (Slice 2G;
        architectural_invariants.md #17, "Stateful NodeRuntime firings
        are serialized").

        Lazily instantiated and memoized exactly like `.memory`, and
        gated by the same state-awareness signal `.memory`/`.last_output`
        already use (`self.flow_node.context is not None`): a
        `NodeRuntime` whose node function declares no `NodeContext`
        parameter has nothing to race on and gets no `Lock` at all --
        this property returns `None` for it rather than constructing an
        unnecessary lock.

        For a state-aware `NodeRuntime`, `Run.publish(...)` acquires
        this `Lock` immediately before calling the node function and
        releases it (via try/finally) immediately after
        `.commit(...)` completes, so that at most one firing of this
        `NodeRuntime` is ever in flight at the same time -- across
        threads, and reentrantly within the same thread (a plain
        `threading.Lock`, not an `RLock`, so a reentrant firing blocks
        rather than silently nesting).
        """
        if self._flow_node.context is None:
            return None

        if self._firing_lock is None:
            self._firing_lock = threading.Lock()

        return self._firing_lock

    @property
    def context(self) -> NodeContext:
        """
        A fresh `NodeContext` snapshot (Slice 2D) exposing this
        `NodeRuntime`'s current `.memory` and `.last_output`.

        Raises `AttributeError` (via `.memory`) if this `NodeRuntime`'s
        node function does not declare a `NodeContext` parameter.
        """
        return NodeContext(memory=self.memory, last_output=self.last_output)

    @property
    def recordings(self) -> tuple[Recording, ...]:
        """
        Every `Recording` accepted on this `NodeRuntime` so far (Milestone
        O2, Slice O2c/O2d), in acceptance order. In-memory only -- see
        Milestone O3 for durable persistence.
        """
        return tuple(self._recordings)

    def accept_recording(
        self,
        identity: NodeExecutionIdentity,
        instrument_or_name: "Instrument | str",
        value: ScalarValue,
        *,
        unit: str | None = None,
        attributes: dict[str, ScalarValue] | None = None,
    ) -> Recording:
        """
        Validate and accept one `ctx.record(...)` call (Milestone O2,
        Slice O2c/O2d), bound (via `functools.partial`) into the
        `NodeContext.record`-facing recorder built by
        `Run._build_call_kwargs` for one firing's `identity`.

        Two modes (docs/observability_goals.md Section 2.3):

        - Declared mode (`self._flow_node.instruments` non-empty): an
          `Instrument` instance, or a plain string matching a declared
          Instrument's `name`, resolves to that Instrument. A name not
          among the declared Instruments is an error at first call -- no
          silent ad hoc registration once a Node has opted into explicit
          declarations.
        - Lazy mode (`self._flow_node.instruments` empty): a plain string
          `name` is accepted with no prior declaration. The first
          observed `unit` for a given `name` is authoritative; a later
          call for the same `name` with a different `unit` raises
          `ValueError`. `kind` is `None` in lazy mode (there was never an
          `Instrument` to declare one).

        `value` must be scalar (`str | int | float | bool`) --
        docs/observability_non_goals.md Section 3.
        """
        if not isinstance(value, (str, int, float, bool)):
            raise TypeError(
                f"Recording value must be scalar (str | int | float | bool), "
                f"got {type(value).__name__!r} (docs/observability_non_goals.md "
                "Section 3 -- no mappings, dataclasses, lists, or nested "
                "structures; flatten a compound fact into multiple explicit "
                "ctx.record(...) calls with dot-segmented names instead)."
            )

        name, kind, resolved_unit = self._resolve_instrument(
            instrument_or_name, unit=unit
        )

        recording = Recording(
            instrument_id=f"{identity.flow_id}.{identity.node_id}.{name}",
            name=name,
            value=value,
            kind=kind,
            unit=resolved_unit,
            execution_id=identity.execution_id,
            flow_id=identity.flow_id,
            node_id=identity.node_id,
            node_execution_id=identity.node_execution_id,
            execution_seq=identity.execution_seq,
            attributes=dict(attributes) if attributes else {},
        )
        self._recordings.append(recording)
        return recording

    def _resolve_instrument(
        self, instrument_or_name: "Instrument | str", *, unit: str | None
    ) -> tuple[str, str | None, str | None]:
        """Returns `(name, kind, unit)` -- `kind` is `None` in lazy mode."""
        if isinstance(instrument_or_name, Instrument):
            instrument = instrument_or_name
            return instrument.name, instrument.kind, instrument.unit

        name = instrument_or_name

        if self._declared_instruments:
            if name not in self._declared_instruments:
                raise ValueError(
                    f"{name!r} is not among this Node's declared instruments "
                    f"({sorted(self._declared_instruments)!r}) -- calling "
                    "ctx.record(...) with an undeclared name is an error once "
                    "a Node has opted into explicit instruments=[...] "
                    "(docs/observability_goals.md Section 2.3)."
                )
            declared = self._declared_instruments[name]
            return declared.name, declared.kind, declared.unit

        # Lazy mode: first observed unit for `name` is authoritative
        # (docs/observability_goals.md Section 2.3); `kind` is always
        # `None` here -- there was never an Instrument declared to carry
        # one.
        if name in self._lazy_units:
            existing_unit = self._lazy_units[name]
            if unit is not None and existing_unit != unit:
                raise ValueError(
                    f"ctx.record({name!r}, ...) was first observed with "
                    f"unit={existing_unit!r}; a later call supplied a "
                    f"different unit={unit!r}. The first observed unit for a "
                    "lazily-declared name is authoritative "
                    "(docs/observability_goals.md Section 2.3)."
                )
            return name, None, existing_unit

        self._lazy_units[name] = unit
        return name, None, unit

    def build_context(
        self,
        identity: NodeExecutionIdentity,
        recorder: "object | None" = None,
    ) -> NodeContext:
        """
        A fresh `NodeContext` snapshot carrying an observability identity
        bundle (Milestone O1, Slice O1f).

        Identical to `.context` except for the added `identity=...`
        argument -- used exclusively by `Run._build_call_kwargs(...)` to
        build the `NodeContext` that is actually injected into a real
        firing, once `Run._begin_node_execution(...)` has minted that
        firing's identity. Kept as a separate method rather than an
        optional parameter on `.context` because `.context` is a
        property (called without parentheses throughout the existing,
        regression-protected call sites) and properties cannot take
        arguments.

        Raises `AttributeError` (via `.memory`) if this `NodeRuntime`'s
        node function does not declare a `NodeContext` parameter --
        same as `.context`.
        """
        return NodeContext(
            memory=self.memory,
            last_output=self.last_output,
            identity=identity,
            recorder=recorder,
        )
