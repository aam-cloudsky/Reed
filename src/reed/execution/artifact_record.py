"""
ArtifactRecord (Slice 2C, Priorities 6 and 7 -- `ArtifactRecord`;
`ParcelProvenance`/`ParcelVersion` mechanics carried forward as
`ArtifactProvenance`/`ArtifactVersion`).

Scope for this slice (docs/refactor_priority_order.md, Milestone 2, Slice
2C row; Priority 6 "Create `ArtifactRecord`"; Priority 7 "`ParcelProvenance`
/ `ParcelVersion`"; docs/parcel_boundary_decision.md, "Parcel As Internal
Envelope"; docs/architectural_invariants.md #7-11):

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
being subclassed by it, matching docs/parcel_boundary_decision.md's target
boundary diagram (`unwrap: Parcel[T] -> T`, `wrap: U -> Parcel[U]`) and the
conceptual mapping in docs/implementation_refactor_assessment.md #8:
"ArtifactRecord[DomainType]: Reed-managed committed record containing
value, version, provenance, and dependencies."

Preserved mechanics (docs/refactor_priority_order.md, Priority 7,
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
see docs/refactor_state.md's Slice 2C record for the full reasoning.

Explicitly out of scope for this slice (Milestone 2, later slices):

    - No `wrap(domain_value) -> ArtifactRecord` operation tied to a real
      node firing. The task's own conceptual boundary diagram marks the
      wrap direction ("DomainValue -> wrap -> ArtifactRecord ->
      repository") as "eventual", not this slice -- that is 2E's
      "commit ArtifactRecord" responsibility
      (docs/refactor_priority_order.md, Slice 2E row). Constructing an
      `ArtifactRecord` directly (`ArtifactRecord(value=...)`) is plain
      object construction, not a firing-tied "wrap"; it is what this
      slice's own tests use to build fixtures.
    - No repository storage of `ArtifactRecord`s. `run.repository`
      (`reed.execution.run.Run.repository`, Slice 2A follow-up) remains
      backed directly by `ArtifactRepository`, whose `get_parcel`/`set_parcel` are
      hard-typed to `Parcel` instances (`ArtifactRepository.set_parcel` raises
      `TypeError` for anything that is not a `Parcel`) -- `ArtifactRepository` cannot
      hold an `ArtifactRecord` without either modifying `ArtifactRepository` itself
      (forbidden: `ArtifactRepository` is regression-protected legacy infrastructure,
      and changing its type contract is exactly the kind of
      "disproportionate migration" this slice's task instruction says to
      report rather than force) or making `ArtifactRecord` a `Parcel`
      subclass (architecturally backwards -- see "ArtifactRecord Is Not
      A Blind Parcel Rename" in docs/non-goals.md). This slice does not
      need repository storage to work: nothing commits an
      `ArtifactRecord` anywhere yet (that is 2E's job), so there is
      nothing to store. See docs/refactor_state.md's Open Architectural
      Questions for the recorded finding: how `run.repository` will
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
      docs/non-goals.md, "Broad Renaming"; see
      docs/implementation_refactor_assessment.md #9).
    - No `ArtifactManager`, `RecordFactory`, `RepositoryAdapter`,
      `ExecutionManager`, `ArtifactService`, `StorageProtocol`, or
      equivalent speculative abstraction -- `ArtifactRecord` is a plain,
      concrete container; nothing else was introduced to support it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Generic, Optional, TypeVar

if TYPE_CHECKING:
    from reed.execution.node_runtime import NodeRuntime

DomainType = TypeVar("DomainType")


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
    An artifact record's lineage (Slice 2C).

    Mirrors `reed.synchronization.parcel.provenance.ParcelProvenance`'s
    shape and `.advance(...)` mechanic, with two adaptations:

    1. `producer` references a `NodeRuntime` (Slice 2B; "one node
       participation materialized inside one run" --
       docs/architectural_decision.md, "Node Runtime") instead of the
       legacy `NodeId`, since `ArtifactRecord`s belong to the new
       `Run`/`NodeRuntime` execution model, not the legacy
       `Bus`/`Outpost` one. Stays `None` until a real firing sets it --
       no firing exists yet (Slice 2E), so this field is always `None`
       in this slice's own tests.
    2. `dependencies` is keyed by domain type, not by `Parcel` subclass
       type (docs/refactor_priority_order.md, Priority 7, item 4).
    """

    producer: Optional["NodeRuntime"] = None
    version: ArtifactVersion = field(default_factory=ArtifactVersion.pending)
    dependencies: dict[type, ArtifactVersion] = field(default_factory=dict)

    def advance(
        self,
        *,
        producer: Optional["NodeRuntime"] = None,
        dependencies: Optional[dict[type, ArtifactVersion]] = None,
    ) -> None:
        """
        Publish a new provenance revision in place.

        Mirrors `ParcelProvenance.advance(...)` exactly: the version
        always moves forward by one (`pending` (0) -> `initial` (1) on
        first call, `.next()` after); `producer` and `dependencies` are
        only overwritten when explicitly given.
        """

        self.version = self.version.next()

        if producer is not None:
            self.producer = producer

        if dependencies is not None:
            self.dependencies = dict(dependencies)

    def copy(self) -> ArtifactProvenance:
        return type(self)(
            producer=self.producer,
            version=self.version,
            dependencies=dict(self.dependencies),
        )


@dataclass
class ArtifactRecord(Generic[DomainType]):
    """
    Reed's internal, execution-side wrapper for one domain value
    (Slice 2C).

    See module docstring for the exact scope and the composition-over-
    inheritance distinction from legacy `Parcel`. `value` is a plain
    instance of the user's own domain type -- node functions never see
    this wrapper, only what `NodeRuntime.unwrap(...)` returns from it
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
