"""
NodeSession: one node participation (`FlowNode`) materialized inside one
`Session`.

A `NodeSession` exists per (`Session`, `FlowNode`) pair, is created and
held by its `Session`, and is never shared across `Session`s, so a node's
state never leaks between executions (docs/refactor/architectural_decision.md,
"Node Session").

    NodeSession
        .memory:          the node's private memory, built lazily from the
                          `MemoryType` declared in `NodeContext[MemoryType,
                          OutputType]` and kept per `InstanceKey`.
        .last_output:     the latest committed output, per `InstanceKey`;
                          `None` before the first commit.
        .context:         a fresh `NodeContext(memory=..., last_output=...)`.
        .unwrap(record):      `record.value`.
        .wrap(value):         a new `ArtifactRecord` produced by this node.
        .commit(record):      stores the record in the repository and sets
                              `last_output`, together.

`.memory`, `.last_output` and `.context` raise `AttributeError` for a node
without a `NodeContext` parameter, so `hasattr(node_session, "memory")`
reports `False` for it.

Transactions: a firing that fails commits neither an output nor a memory
transition. Outputs are staged until the superstep barrier; memory is
copied before each firing (`_memory_checkpoint`) and restored by `Session`
when the superstep fails (`_restore_memory`). `Session.push()` decides
when a node fires; `NodeSession` only owns these operations. Design record:
docs/history/node_context_decision.md, "Transaction Semantics".
"""

from __future__ import annotations

import copy
import threading
from typing import TYPE_CHECKING

from reed.composition.node.node_context import NodeContext
from reed.execution.artifact_record import ArtifactOrigin, ArtifactRecord
from reed.observability.identity import NodeExecutionIdentity
from reed.observability.instrument import Instrument, InstrumentKind
from reed.observability.recording import Recording, ScalarValue

from reed.execution.instance_key import InstanceKey

# Marks a checkpoint taken before a node's memory existed (issue #34).
_NO_MEMORY = object()

if TYPE_CHECKING:
    from reed.composition.flow.flow_node import FlowNode
    from reed.execution.session import Session


class NodeSession:
    """
    One node participation (`FlowNode`) materialized inside one `Session`
    (Slice 2B; `ArtifactRecord` unwrap boundary added by Slice 2C; memory
    and `.context` construction added by Slice 2D; wrap/commit added by
    Slice 2E).

    See module docstring for the exact scope: an identity/ownership
    boundary, a pure unwrap operation, a private, node-local memory
    instance plus a `.context` snapshot, and now the wrap/commit
    operations `Session.push()` uses to complete one firing.
    `NodeSession` still owns no execution-eligibility policy and no
    callback dispatch -- it exists so that later slices (2F-2G) have
    somewhere correct to attach callback dispatch and stateful-firing
    serialization, without any of that state ever being stored on
    `FlowNode` (which remains reusable Flow-local composition metadata)
    or on `Flow` itself.
    """

    def __init__(self, session: Session, flow_node: FlowNode) -> None:
        self._session = session
        self._flow_node = flow_node
        # Slice MI-F: NodeMemory and last_output are keyed by InstanceKey
        # (R4 decision, docs/refactor/multi_instance_execution_plan.md --
        # per-instance is the resolved scope, consistent with the same
        # generalization already applied to repository storage (MI-B),
        # provenance alignment (MI-C), external feeding (MI-D), and
        # eligibility/firing (MI-E)). The zero-argument `.memory` /
        # `.last_output` / `.context` properties below read through
        # InstanceKey.singleton() so every pre-multi-instance call site
        # is completely unaffected.
        self._memory: dict["InstanceKey", object] = {}
        self._last_output: dict["InstanceKey", object] = {}
        # firing_lock deliberately stays scoped to (Session, NodeSession)
        # only, not split per instance -- concurrent execution of
        # instance-level firings is out of scope for this whole issue
        # (plan document Section 4; roadmap #9 / issue #23), so there is
        # nothing today for a per-instance lock to protect beyond what
        # this single lock already protects.
        self._firing_lock: threading.Lock | None = None
        # Milestone O2, Slice O2c/O2d: in-memory Recording buffer (Level 2
        # precursor -- Milestone O3 gives it a durable store) plus the
        # lazy-mode registry that makes "first observed kind/unit wins"
        # enforceable (docs/refactor/observability_goals.md Section 2.3).
        self._recordings: list[Recording] = []
        # Milestone O7, Slice O7i: Instruments are discovered dynamically
        # -- there is nothing to pre-populate here anymore (no more
        # `flow_node.instruments`). `_observed_instruments` remembers
        # every distinct Instrument subclass this NodeSession has already
        # seen this Session, keyed by `instrument_name()`, purely so a
        # second `ctx.record(SomeInstrument, ...)` call for the same
        # Instrument does not repeat the (cheap, but non-zero) manifest
        # bookkeeping done on first discovery -- see `.flush_recordings`.
        self._observed_instruments: dict[str, "type[Instrument]"] = {}
        self._newly_observed_this_firing: list["type[Instrument]"] = []

        # Milestone O7, Slice O7b: a running per-NodeSession
        # `ArtifactProvenance` used to live here, but Slice 22D removes
        # it entirely -- `.wrap(...)` now routes through
        # `Session._commit(...)`, which derives the next version from
        # the repository's own current `ArtifactRecord` for the type
        # (invariant #28) instead of a private, per-node running
        # counter. See `.wrap(...)`'s docstring for the corrected
        # mechanics.
        # Milestone O7, Slice O7c: per-NodeExecution Recording batch,
        # keyed by node_execution_id -- accumulated in memory during a
        # firing and flushed as one batch (one fsync) at that firing's
        # own durability boundary (`.flush_recordings(...)`, called from
        # `Session._run_worker`'s `finally` block), not written through to the
        # store on every individual `ctx.record()` call.
        self._pending_recordings: dict[str, list[Recording]] = {}

    @property
    def session(self) -> Session:
        """The `Session` this `NodeSession` was materialized inside."""
        return self._session

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

    def wrap(
        self,
        domain_value: object,
        *,
        instance: "InstanceKey | None" = None,
    ) -> "ArtifactRecord":
        """
        Wrap `domain_value` -- a node function's returned domain value --
        into a committed `ArtifactRecord` (Slice 2E; version mechanics
        fixed at Milestone O7, Slice O7b; unified onto the shared
        `Session._commit(...)` path at Slice 22D).

        Slice 22D (docs/refactor/session_snapshot_decision.md section 6
        "Unified versioning and ArtifactOrigin"): this NodeSession no
        longer owns a private, per-node running `ArtifactProvenance`
        counter (`self._provenance`, removed this slice). Instead it
        delegates to `self._session._commit(domain_value,
        origin=ArtifactOrigin.NODE, producer=self)`, which reads this
        domain type's *current* `ArtifactRecord` straight from the
        repository (`self.session.repository`) and advances it in place
        if one exists, or constructs a fresh one at
        `ArtifactVersion.initial()` if this is the type's first commit
        (architectural_invariants.md #28). This is the same version
        source `Session.feed()` (Slice 22E) will use, so repeated
        firings of the same Node keep producing monotonically
        increasing, causally distinct versions -- now derived from one
        shared, type-keyed source instead of two parallel per-path
        counters.

        Unlike the pre-22D implementation, the returned `ArtifactRecord`
        is the *same* object the repository holds for this domain type
        (an aliased reference per Slice 22C's in-place-mutation model,
        docs/refactor/session_snapshot_decision.md section 7), not an
        independent snapshot -- `.commit(...)` re-storing it under the
        same key is therefore idempotent. This is the "wrap" half of
        docs/history/parcel_boundary_decision.md's boundary diagram (`U -> wrap
        -> Parcel[U]`, read here as `ArtifactRecord`); it does not
        change what `.commit(...)` is responsible for (updating
        `self._last_output`).
        """
        return self._session._commit(
            domain_value, origin=ArtifactOrigin.NODE, producer=self, instance=instance
        )

    def commit(
        self,
        record: "ArtifactRecord",
        *,
        instance: "InstanceKey | None" = None,
    ) -> None:
        """
        Commit `record` -- the successful-commit path only (Slice 2E).

        Stores `record` into `self.session.repository`'s additive,
        domain-type-keyed `ArtifactRecord` storage
        (`ArtifactRepository.set_artifact_record`,
        docs/history/parcel_boundary_decision.md's "Addendum: Slice 2E
        ArtifactRecord Commit Storage") and updates `self._last_output`
        to `record.value`, so that both the repository commit and the
        local `last_output` transition happen together
        (docs/history/node_context_decision.md, "Transaction Semantics":
        "successful firing -> memory transition and output publication
        commit together"). Only the successful path is implemented here
        -- a firing that raises before reaching `.commit(...)` leaves
        both untouched, which already satisfies "failed firing -> no
        committed memory transition and no committed output" for that
        case; a firing that fails *partway through* wrap/commit is
        explicitly out of scope (see module docstring and the
        SliceContract's stop_conditions).
        """
        self._session.repository.set_artifact_record(record, instance=instance)
        key = instance if instance is not None else InstanceKey.singleton()
        self._last_output[key] = record.value

    def _memory_checkpoint(self, instance: "InstanceKey") -> object:
        """
        A copy of this node's memory for `instance`, taken before a firing so
        that a failed superstep can restore it (issue #34). Returns
        `_NO_MEMORY` when the memory has not been created yet.

        Raises `TypeError` if the memory cannot be copied with
        `copy.deepcopy`.
        """
        if instance not in self._memory:
            return _NO_MEMORY
        try:
            return copy.deepcopy(self._memory[instance])
        except Exception as exc:
            raise TypeError(
                f"The memory of {self._flow_node.definition.function!r} cannot "
                "be copied with copy.deepcopy; Reed copies node memory before "
                "each firing so that a failed superstep can restore it."
            ) from exc

    def _restore_memory(self, instance: "InstanceKey", checkpoint: object) -> None:
        """Put back the memory saved by `_memory_checkpoint` (issue #34)."""
        if checkpoint is _NO_MEMORY:
            self._memory.pop(instance, None)
        else:
            self._memory[instance] = checkpoint

    def _memory_for(self, instance: "InstanceKey") -> object:
        """
        This `NodeSession`'s private memory instance for `instance`
        (Slice 2D; keyed per `InstanceKey` at Slice MI-F, R4 decision),
        lazily instantiated from its `FlowNode`'s declared `MemoryType`
        and memoized per instance: the same object is returned -- and
        can be mutated in place -- on every subsequent access to the
        same instance, for as long as this `NodeSession` (one per
        (`Session`, `FlowNode`) pair, Slice 2B) lives. A different
        `instance` gets its own independently constructed, independently
        mutated memory object.

        Raises `AttributeError` if this `NodeSession`'s node function
        does not declare a `NodeContext` parameter -- there is no
        `MemoryType` to construct from.
        """
        if self._flow_node.context is None:
            raise AttributeError(
                f"{self._flow_node.definition.function!r} does not "
                "declare a NodeContext parameter; it has no memory."
            )

        if instance not in self._memory:
            self._memory[instance] = self._flow_node.context.memory_type()

        return self._memory[instance]

    @property
    def memory(self) -> object:
        """
        This `NodeSession`'s private memory instance for the singleton
        instance (Slice 2D; per-instance generalization added at Slice
        MI-F -- see `._memory_for(...)`). Kept as a zero-argument
        property, reading through `InstanceKey.singleton()`, so every
        pre-multi-instance call site is completely unaffected.

        Raises `AttributeError` if this `NodeSession`'s node function
        does not declare a `NodeContext` parameter -- there is no
        `MemoryType` to construct from.
        """
        return self._memory_for(InstanceKey.singleton())

    def _last_output_for(self, instance: "InstanceKey") -> object | None:
        """
        The latest successfully committed domain output for `instance`
        on this `NodeSession` (Slice 2D representation; wired to a real
        committed value by `.commit(...)`, Slice 2E; keyed per
        `InstanceKey` at Slice MI-F). `None` until this `NodeSession` has
        completed its first successful commit for `instance`.

        Raises `AttributeError` for the same reason and under the same
        condition as `._memory_for(...)` -- see its docstring.
        """
        if self._flow_node.context is None:
            raise AttributeError(
                f"{self._flow_node.definition.function!r} does not "
                "declare a NodeContext parameter; it has no last_output."
            )

        return self._last_output.get(instance)

    @property
    def last_output(self) -> object | None:
        """
        The latest successfully committed domain output for the
        singleton instance (Slice 2D; per-instance generalization added
        at Slice MI-F -- see `._last_output_for(...)`). Kept as a
        zero-argument property, reading through
        `InstanceKey.singleton()`, so every pre-multi-instance call site
        is completely unaffected.

        Raises `AttributeError` for the same reason and under the same
        condition as `.memory` -- see its docstring.
        """
        return self._last_output_for(InstanceKey.singleton())

    @property
    def firing_lock(self) -> "threading.Lock | None":
        """
        This `NodeSession`'s own mutual-exclusion primitive (Slice 2G;
        architectural_invariants.md #17, "Stateful NodeSession firings
        are serialized").

        Lazily instantiated and memoized exactly like `.memory`, and
        gated by the same state-awareness signal `.memory`/`.last_output`
        already use (`self.flow_node.context is not None`): a
        `NodeSession` whose node function declares no `NodeContext`
        parameter has nothing to race on and gets no `Lock` at all --
        this property returns `None` for it rather than constructing an
        unnecessary lock.

        For a state-aware `NodeSession`, `Session.push()` acquires
        this `Lock` immediately before calling the node function and
        releases it (via try/finally) immediately after
        `.commit(...)` completes, so that at most one firing of this
        `NodeSession` is ever in flight at the same time -- across
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
        `NodeSession`'s current `.memory` and `.last_output`.

        Raises `AttributeError` (via `.memory`) if this `NodeSession`'s
        node function does not declare a `NodeContext` parameter.
        """
        return NodeContext(memory=self.memory, last_output=self.last_output)

    @property
    def recordings(self) -> tuple[Recording, ...]:
        """
        Every `Recording` accepted on this `NodeSession` so far (Milestone
        O2, Slice O2c/O2d), in acceptance order. In-memory only -- see
        Milestone O3 for durable persistence.
        """
        return tuple(self._recordings)

    def accept_recording(
        self,
        identity: NodeExecutionIdentity,
        instrument: "type[Instrument]",
        value: ScalarValue,
        *,
        attributes: dict[str, ScalarValue] | None = None,
    ) -> Recording:
        """
        Validate and accept one `ctx.record(instrument, value)` call
        (Milestone O2, Slice O2c/O2d; redesigned at Milestone O7, Slice
        O7i for typed Instrument Definitions), bound (via
        `functools.partial`) into the `NodeContext.record`-facing
        recorder built by `Session._build_call_kwargs` for one firing's
        `identity`.

        `instrument` must be an `Instrument` subclass (never an
        instance) -- see `reed.observability.instrument`'s module
        docstring. There is no more declared-vs-lazy distinction: every
        Instrument is discovered dynamically, the first time a Node
        actually calls `ctx.record(instrument, value)`, never
        prospectively declared through `Flow.add(...)` (which no longer
        accepts an `instruments=` parameter at all).

        `value` must be scalar (`str | int | float | bool`) --
        docs/refactor/observability_non_goals.md Section 3.
        """
        if not isinstance(value, (str, int, float, bool)):
            raise TypeError(
                f"Recording value must be scalar (str | int | float | bool), "
                f"got {type(value).__name__!r} (docs/refactor/observability_non_goals.md "
                "Section 3 -- no mappings, dataclasses, lists, or nested "
                "structures; flatten a compound fact into multiple explicit "
                "ctx.record(...) calls with dot-segmented names instead)."
            )

        name, kind, resolved_unit, description = self._resolve_instrument(instrument)
        self._newly_observed_this_firing_note(instrument, name)

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
        try:
            self._session.presenter.on_recording(recording)
        except BaseException:  # noqa: BLE001 -- O7g: isolate presenter failures (invariant #25)
            pass
        if self._session.recording_store is not None:
            # Milestone O7, Slice O7c: buffer in memory for this firing;
            # `.flush_recordings(...)` writes the whole batch, with one
            # fsync, at this firing's own NodeExecution durability
            # boundary -- not on every individual ctx.record() call (see
            # storage.py's module docstring for the corrected contract).
            self._pending_recordings.setdefault(
                identity.node_execution_id, []
            ).append(recording)
        return recording

    def flush_recordings(self, node_execution_id: str) -> None:
        """
        Flush and durably persist every `Recording` buffered for
        `node_execution_id` as one batch (Milestone O7, Slice O7c) --
        the NodeExecution durability boundary (docs/refactor/observability_goals.md
        Section 5; architectural invariants #20/#21). Called from
        `Session._run_worker`'s `finally` block, so it runs whether the firing
        succeeded or raised. A no-op if this firing made no
        `ctx.record(...)` calls (nothing buffered) or if no
        `recording_store` is configured (`storage_root` was not passed
        to `Flow.session(...)`).

        Milestone O7, Slice O7i: also flushes any newly-*discovered*
        Instrument bindings observed during this firing into the Flow's
        `instruments.json` manifest (`Session.record_discovered_instruments`),
        at the same durability boundary -- proportional only to how many
        genuinely new (node_id, Instrument) bindings this firing
        introduced (usually zero after the first firing of a given
        Node/Instrument pair), never once per `ctx.record(...)` call, so
        this stays off the hot path the same way Recording persistence
        does (architectural invariant #26).
        """
        newly_observed = self._newly_observed_this_firing
        self._newly_observed_this_firing = []
        if newly_observed and self._session.recording_store is not None:
            self._session.record_discovered_instruments(
                node_id=self._flow_node.node_id,
                node_name=self._flow_node.node_name,
                instruments=newly_observed,
            )

        batch = self._pending_recordings.pop(node_execution_id, None)
        if not batch or self._session.recording_store is None:
            return
        self._session.recording_store.append_batch(batch)

    def _newly_observed_this_firing_note(
        self, instrument: "type[Instrument]", name: str
    ) -> None:
        """Record that `instrument` was newly discovered this Session, if it was."""
        if name not in self._observed_instruments:
            self._observed_instruments[name] = instrument
            self._newly_observed_this_firing.append(instrument)

    def _resolve_instrument(
        self, instrument: "type[Instrument]"
    ) -> tuple[str, str, str, str]:
        """
        Returns `(name, kind, unit, description)` for `instrument`
        (Milestone O7, Slice O7i -- typed Instrument Definitions,
        discovered dynamically; see `reed.observability.instrument`'s
        module docstring).

        `instrument` must be an `Instrument` **subclass** with `kind`/
        `unit` class attributes -- both are validated eagerly by
        `Instrument.__init_subclass__` for the common case (a concrete
        leaf class with a typo'd or missing attribute), but that check is
        skipped for an intermediate subclass that itself sets neither;
        this is the fallback that catches such a class if it is ever
        actually passed to `ctx.record(...)`.
        """
        if not (isinstance(instrument, type) and issubclass(instrument, Instrument)):
            raise TypeError(
                "ctx.record(...) expects an Instrument *subclass* (the "
                "Instrument Definition itself, e.g. ctx.record(Temperature, "
                "value) -- not an instance, and not a plain string). Got "
                f"{instrument!r}."
            )
        if not hasattr(instrument, "kind") or not isinstance(
            instrument.kind, InstrumentKind
        ):
            raise TypeError(
                f"{instrument.__name__} must declare kind: InstrumentKind as "
                "a class attribute (docs/refactor/observability_non_goals.md Section "
                "2 -- no Histogram, no arbitrary kind values)."
            )
        if not hasattr(instrument, "unit") or not isinstance(instrument.unit, str):
            raise TypeError(
                f"{instrument.__name__} must declare unit: str as a class "
                "attribute."
            )

        name = instrument.instrument_name()
        return name, instrument.kind.value, instrument.unit, instrument.description

    def build_context(
        self,
        identity: NodeExecutionIdentity,
        recorder: "object | None" = None,
        *,
        instance: "InstanceKey | None" = None,
    ) -> NodeContext:
        """
        A fresh `NodeContext` snapshot carrying an observability identity
        bundle (Milestone O1, Slice O1f) and, since Slice MI-F, reading
        memory/last_output for `instance` specifically (defaulting to
        `InstanceKey.singleton()`, same as every other `instance`
        keyword-only parameter added since Slice MI-E).

        Identical to `.context` except for the added `identity=...` and
        `instance=...` arguments -- used exclusively by
        `Session._build_call_kwargs(...)` to build the `NodeContext` that
        is actually injected into a real firing, once
        `Session._begin_node_execution(...)` has minted that firing's
        identity. Kept as a separate method rather than optional
        parameters on `.context` because `.context` is a property (called
        without parentheses throughout the existing, regression-protected
        call sites) and properties cannot take arguments.

        Raises `AttributeError` (via `._memory_for(...)`) if this
        `NodeSession`'s node function does not declare a `NodeContext`
        parameter -- same as `.context`.
        """
        key = instance if instance is not None else InstanceKey.singleton()
        return NodeContext(
            memory=self._memory_for(key),
            last_output=self._last_output_for(key),
            identity=identity,
            recorder=recorder,
        )
