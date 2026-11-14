"""
ArtifactRecord (Slice 2C, Priorities 6 and 7 -- `ArtifactRecord`;
`ParcelProvenance`/`ParcelVersion` mechanics carried forward as
`ArtifactProvenance`/`ArtifactVersion`).

Scope for this slice (docs/history/refactor_priority_order.md, Milestone 2, Slice
2C row; Priority 6 "Create `ArtifactRecord`"; Priority 7 "`ParcelProvenance`
/ `ParcelVersion`"; docs/history/parcel_boundary_decision.md, "Parcel As Internal
Envelope"; docs/refactor/architectural_invariants.md #7-11):

    public / node-facing                Reed execution infrastructure

    DomainValue        <----------->    ArtifactRecord[DomainValue]
                                          |-- value
                                          |-- version   (via provenance)
                                          |-- provenance
                                          `-- dependencies (via provenance)

`Domain Value != ArtifactRecord` (architectural_invariants.md #7) is made
concrete here as a genuine composition boundary, not an inheritance one:
`ArtifactRecord.value` holds a plain instance of the user's own domain
type, with zero Reed coupling. This is a deliberate structural departure
from the legacy `Parcel` model (`src/reed/synchronization/parcel/parcel.py`),
where a domain type is instead defined by *subclassing* `Parcel` directly
(`class RawImage(Parcel): ...`) -- so the domain data and Reed's envelope
are the same object there. `ArtifactRecord` wraps a domain value instead of
being subclassed by it, matching docs/history/parcel_boundary_decision.md's target
boundary diagram (`unwrap: Parcel[T] -> T`, `wrap: U -> Parcel[U]`) and the
conceptual mapping in docs/history/implementation_refactor_assessment.md #8:
"ArtifactRecord[DomainType]: Reed-managed committed record containing
value, version, provenance, and dependencies."

Preserved mechanics (docs/history/refactor_priority_order.md, Priority 7,
"preserve current versioning behavior" / "preserve current provenance
behavior"): `ArtifactVersion` and `ArtifactProvenance` mirror
`ParcelVersion`/`ParcelProvenance`'s existing, regression-tested shape and
behavior (`src/reed/synchronization/parcel/provenance.py`,
`tests/test_current_regression_artifacts_repository.py`) --
`ArtifactVersion.pending()`/`.initial()`/`.next()`, and
`ArtifactProvenance.advance(...)` mutating version/producer/dependencies
in place. Priority 7's item 4 ("update dependency mappings from Parcel
type to domain artifact type") is carried forward too:
`ArtifactProvenance.dependencies` is keyed by domain type, not by
`Parcel` subclass type.

Deliberately NOT carried forward (Priority 7 item 3, "rename after
`ArtifactRecord` exists", and the live Slice 2C task instruction's own,
narrower constraint, "Do not perform the broad Parcel -> Artifact rename
scheduled for later slices merely because the new `ArtifactRecord`
exists"): `Parcel`, `ParcelVersion`, and `ParcelProvenance` are left
completely untouched, byte-for-byte, regression-protected. `ArtifactRecord`
et al. are new, additive classes -- exactly the same pattern already used
for `TriggerPolicy` alongside the untouched `PropagationPolicy` (Slice 1E)
and `ArtifactDependencyGraph` alongside the untouched `DependencyRegistry`
(Slice 1D). This is a deliberate, narrower reading of Priority 7 item 3
than a literal in-place rename, reported rather than silently chosen --
see docs/history/refactor_state.md's Slice 2C record for the full reasoning.

Explicitly out of scope for this slice (Milestone 2, later slices):

    - No `wrap(domain_value) -> ArtifactRecord` operation tied to a real
      node firing. The task's own conceptual boundary diagram marks the
      wrap direction ("DomainValue -> wrap -> ArtifactRecord ->
      repository") as "eventual", not this slice -- that is 2E's
      "commit ArtifactRecord" responsibility
      (docs/history/refactor_priority_order.md, Slice 2E row). Constructing an
      `ArtifactRecord` directly (`ArtifactRecord(value=...)`) is plain
      object construction, not a firing-tied "wrap"; it is what this
      slice's own tests use to build fixtures.
    - No repository storage of `ArtifactRecord`s. `session.repository`
      (`reed.execution.session.Session.repository`, Slice 2A follow-up) remains
      backed directly by `ArtifactRepository`, whose `get_parcel`/`set_parcel` are
      hard-typed to `Parcel` instances (`ArtifactRepository.set_parcel` raises
      `TypeError` for anything that is not a `Parcel`) -- `ArtifactRepository` cannot
      hold an `ArtifactRecord` without either modifying `ArtifactRepository` itself
      (forbidden: `ArtifactRepository` is regression-protected legacy infrastructure,
      and changing its type contract is exactly the kind of
      "disproportionate migration" this slice's task instruction says to
      report rather than force) or making `ArtifactRecord` a `Parcel`
      subclass (architecturally backwards -- see "ArtifactRecord Is Not
      A Blind Parcel Rename" in docs/history/non-goals.md). This slice does not
      need repository storage to work: nothing commits an
      `ArtifactRecord` anywhere yet (that is 2E's job), so there is
      nothing to store. See docs/history/refactor_state.md's Open Architectural
      Questions for the recorded finding: how `session.repository` will
      actually hold `ArtifactRecord`s is a decision Slice 2E (or 3A)
      must make, not this slice.
    - No `NodeContext` runtime behavior, no `ctx.memory`, no
      `ctx.last_output` (2D).
    - No `NodeMemory` (2D).
    - No `NodeExecution`, no argument construction from descriptors, no
      node-function firing, no transactional commit, no `.publish(...)`
      (2E).
    - No `on_output` dispatch (sync or async, 2F), no
      `callback_failures` (2F), no stateful-firing serialization (2G).
    - No `ArtifactRepository` rename (Milestone 3, slice 3A;
      docs/history/non-goals.md, "Broad Renaming"; see
      docs/history/implementation_refactor_assessment.md #9).
    - No `ArtifactManager`, `RecordFactory`, `RepositoryAdapter`,
      `ExecutionManager`, `ArtifactService`, `StorageProtocol`, or
      equivalent speculative abstraction -- `ArtifactRecord` is a plain,
      concrete container; nothing else was introduced to support it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Generic, Optional, TypeVar

if TYPE_CHECKING:
    from reed.execution.instance_key import InstanceKey
    from reed.execution.node_session import NodeSession

DomainType = TypeVar("DomainType")


class ArtifactOrigin(Enum):
    """
    Where a committed `ArtifactRecord`'s value came from (Slice 22B,
    GitHub issue #22, `docs/refactor/session_snapshot_decision.md`
    section 6 "Unified versioning and `ArtifactOrigin`";
    `docs/refactor/architectural_invariants.md` #29).

    Exactly two members -- `NODE` (a node firing, via
    `NodeSession.wrap()`) and `EXTERNAL` (an externally fed value, via
    the not-yet-implemented `Session.feed()`, Slice 22E). Deliberately
    no third `PENDING`/`UNSET` value: a not-yet-advanced
    `ArtifactProvenance` (`ArtifactVersion.pending()`, version `0`) never
    becomes a reachable, committed `ArtifactRecord` anywhere in the
    system, and every real commit path passes `origin` explicitly the
    moment it advances (`ArtifactProvenance.advance(...)`'s `origin`
    parameter is required, keyword-only, with no default) -- so there is
    no observable state where a committed record's origin is meaningfully
    unset.
    """

    NODE = auto()
    EXTERNAL = auto()


@dataclass(frozen=True, order=True)
class ArtifactVersion:
    """
    An artifact's version identity (Slice 2C).

    Mirrors `reed.synchronization.parcel.provenance.ParcelVersion`
    exactly: a monotonically increasing integer, `0` meaning "not yet
    produced" (`.pending()`) and `1` meaning "first produced version"
    (`.initial()`). Immutable -- `.next()` returns a new instance rather
    than mutating this one.
    """

    number: int

    @classmethod
    def pending(cls) -> ArtifactVersion:
        return cls(number=0)

    @classmethod
    def initial(cls) -> ArtifactVersion:
        return cls(number=1)

    def next(self) -> ArtifactVersion:
        return type(self)(number=self.number + 1)


@dataclass
class ArtifactProvenance:
    """
    An artifact record's lineage (Slice 2C; `origin` field added Slice
    22B).

    Mirrors `reed.synchronization.parcel.provenance.ParcelProvenance`'s
    shape and `.advance(...)` mechanic, with three adaptations:

    1. `producer` references a `NodeSession` (Slice 2B; "one node
       participation materialized inside one session" --
       docs/refactor/architectural_decision.md, "Node Session") instead of the
       legacy `NodeId`, since `ArtifactRecord`s belong to the new
       `Session`/`NodeSession` execution model, not the legacy
       `Bus`/`Outpost` one. Stays `None` until a real firing sets it --
       no firing exists yet (Slice 2E), so this field is always `None`
       in this slice's own tests.
    2. `dependencies` is keyed by domain type, not by `Parcel` subclass
       type (docs/history/refactor_priority_order.md, Priority 7, item 4).
    3. `origin: Optional[ArtifactOrigin]` (Slice 22B,
       docs/refactor/session_snapshot_decision.md section 6; no
       equivalent field exists on legacy `ParcelProvenance`). Stays
       `None` until `.advance(...)` is first called, exactly like
       `producer` -- `ArtifactOrigin` has no third "pending"/"unset"
       member (architectural_invariants.md #29), so `None` here means
       only "never advanced yet", the same thing `version ==
       ArtifactVersion.pending()` already means, not a third enum value.
    """

    producer: Optional["NodeSession"] = None
    version: ArtifactVersion = field(default_factory=ArtifactVersion.pending)
    dependencies: dict[type, ArtifactVersion] = field(default_factory=dict)
    origin: Optional["ArtifactOrigin"] = None
    dependency_instances: dict[type, "InstanceKey"] = field(default_factory=dict)
    """
    Slice MI-C (docs/refactor/multi_instance_execution_plan.md, Section 5):
    which instance of each dependency type this provenance revision was
    aligned against, keyed the same way `dependencies` itself is keyed
    (by domain type). Additive alongside `dependencies`, not a replacement
    for it: `dependencies` records a dependency's version, this field
    records which instance of that dependency type the version belongs
    to. Empty by default, exactly like `dependencies` -- neither field is
    populated by any real node firing yet (Session._commit calls
    `.advance(...)` with neither keyword); both stay unit-level bookkeeping
    until a later slice (MI-E, per-instance firing and eligibility) wires
    them into a real firing's argument resolution, since alignment only
    has real content once a firing can consume more than one instance of
    a dependency.
    """

    def advance(
        self,
        *,
        origin: "ArtifactOrigin",
        producer: Optional["NodeSession"] = None,
        dependencies: Optional[dict[type, ArtifactVersion]] = None,
        dependency_instances: Optional[dict[type, "InstanceKey"]] = None,
    ) -> None:
        """
        Publish a new provenance revision in place.

        Mirrors `ParcelProvenance.advance(...)` exactly for the version/
        producer/dependencies mechanics: the version always moves forward
        by one (`pending` (0) -> `initial` (1) on first call, `.next()`
        after); `producer` and `dependencies` are only overwritten when
        explicitly given.

        `origin` (Slice 22B, docs/refactor/session_snapshot_decision.md
        section 6) has no legacy `ParcelProvenance` equivalent: it is
        required and keyword-only, with no default -- every real commit
        path (`NodeSession.wrap()` today; `Session.feed()`, Slice 22E)
        must state explicitly where the value it is advancing provenance
        for came from, and is always overwritten on every call (unlike
        `producer`/`dependencies`, which are only overwritten when
        given) since a provenance revision always has exactly one origin.
        """

        self.version = self.version.next()
        self.origin = origin

        if producer is not None:
            self.producer = producer

        if dependencies is not None:
            self.dependencies = dict(dependencies)

        if dependency_instances is not None:
            self.dependency_instances = dict(dependency_instances)

    def copy(self) -> ArtifactProvenance:
        return type(self)(
            producer=self.producer,
            version=self.version,
            dependencies=dict(self.dependencies),
            origin=self.origin,
            dependency_instances=dict(self.dependency_instances),
        )


@dataclass
class ArtifactRecord(Generic[DomainType]):
    """
    Reed's internal, execution-side wrapper for one domain value
    (Slice 2C).

    See module docstring for the exact scope and the composition-over-
    inheritance distinction from legacy `Parcel`. `value` is a plain
    instance of the user's own domain type -- node functions never see
    this wrapper, only what `NodeSession.unwrap(...)` returns from it
    (`.value`).
    """

    value: DomainType
    provenance: ArtifactProvenance = field(default_factory=ArtifactProvenance)

    @property
    def version(self) -> ArtifactVersion:
        return self.provenance.version

    @property
    def dependencies(self) -> dict[type, ArtifactVersion]:
        return self.provenance.dependencies

    def advance(
        self,
        value: object,
        *,
        origin: "ArtifactOrigin",
        producer: Optional["NodeSession"] = None,
    ) -> None:
        """
        Publish a new value for this record in place (Slice 22C,
        `docs/refactor/session_snapshot_decision.md` section 7
        "`ArtifactRecord` becomes mutable in place";
        `architectural_invariants.md` #27).

        Unlike plain `ArtifactRecord(value=...)` construction (still how
        `NodeSession.wrap()` produces a record for this slice -- wiring
        `wrap()` to call this method instead is slice 22D, not this one),
        this mutates `self.value` and advances `self.provenance` on the
        *same* object rather than building a new `ArtifactRecord`. Every
        other reference to this record -- e.g. one already returned by
        `ArtifactRepository.get_artifact_record(...)` and held by a
        caller -- is therefore **aliased** to it (in-place mutation) and
        observes the mutation too, rather than retaining
        the independent **value semantics** an `ArtifactRecord` had
        before this slice. A caller that still needs the old guarantee
        -- an independent snapshot unaffected by a later `.advance()` --
        must copy explicitly (e.g. `dataclasses.replace(record,
        provenance=record.provenance.copy())`), the same way
        `ArtifactProvenance.copy()` already exists for that purpose.

        Raises `TypeError` if `type(value) is not type(self.value)`: an
        `ArtifactRecord`'s domain type is fixed at first commit (it is
        the `ArtifactRepository` dict key, keyed by `type(record.value)`
        -- see `ArtifactRepository.set_artifact_record`) and cannot
        change across an in-place advance.
        """

        if type(value) is not type(self.value):
            raise TypeError(
                "ArtifactRecord.advance() cannot change a record's domain "
                f"type: this record holds {type(self.value).__name__}, "
                f"got {type(value).__name__}. A record's domain type is "
                "fixed at first commit -- construct a new ArtifactRecord "
                "for a different type instead."
            )

        self.value = value
        self.provenance.advance(origin=origin, producer=producer)
