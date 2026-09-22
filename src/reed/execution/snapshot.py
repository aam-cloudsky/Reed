"""
Snapshot (Slice 22G, GitHub issue #22 --
docs/refactor/session_snapshot_decision.md section 5 "`push()` and
`snapshot()`" and section 8 "Target public API"; architectural_invariants.md
#24, #25, #33).

    session.feed(...)
    session.push()
    snapshot = session.snapshot()   # -> Snapshot: full current repository state
    snapshot.get(SomeDomainType)                 # -> value or None
    snapshot.get(SomeDomainType, default_value)   # -> value or default_value
    snapshot[SomeDomainType]                      # -> value, or KeyError if absent

`Snapshot` is a read-only view over one `Session`'s `ArtifactRepository`,
captured at the moment `Session.snapshot()` constructs it. It answers "what
does the repository look like right now" -- the *full* current state, every
domain type currently committed, not scoped to whatever the most recent
`push()` happened to touch. It has no automatic history: a later commit
into the repository never changes a `Snapshot` already handed to a caller
(invariant #33), and a later `session.snapshot()` call builds an entirely
new, independent `Snapshot` rather than updating this one in place.

Per invariants #24/#25 ("User Nodes consume and produce domain values";
"Reed owns wrapping and unwrapping of internal artifact records"),
`Snapshot`'s public surface exposes plain domain values only -- the same
values a node itself would receive or return -- and never an
`ArtifactRecord` (Reed's internal, version/provenance-carrying envelope
around a domain value, `reed/execution/artifact_record.py`). `.get(...)`
and `__getitem__` both unwrap `ArtifactRecord.value` before returning.

`ArtifactRepository` (`reed/synchronization/artifact_repository.py`)
exposes only per-type reads (`get_artifact_record(domain_type)`) -- there
is no public bulk-enumeration accessor for "every type currently
committed" (verified by reading that module directly, per this slice's
`SliceContract` stop condition, rather than assumed). Building a *full*
snapshot therefore requires reading `ArtifactRepository`'s private
`_artifact_records` storage once, at construction time; `from_repository`
below is the one place in this codebase that does so, so that reaching
past `ArtifactRepository`'s public interface stays contained to this
module instead of leaking into `Session` or anywhere else. This does not
touch `ArtifactRepository` itself (out of scope for this slice) and adds
no new public method to it.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reed.synchronization.artifact_repository import ArtifactRepository


class Snapshot:
    """
    Immutable, plain-domain-value view over an `ArtifactRepository`'s full
    current state at the moment it was constructed. See module docstring.
    """

    def __init__(self, values: dict[type, object]) -> None:
        self._values: dict[type, object] = dict(values)

    @classmethod
    def from_repository(cls, repository: "ArtifactRepository") -> "Snapshot":
        """
        Build a `Snapshot` capturing `repository`'s full current state: one
        entry per domain type with a committed `ArtifactRecord`, holding
        that record's plain `.value` (never the record itself). See module
        docstring for why this is the one place that reads
        `ArtifactRepository`'s private `_artifact_records` storage directly.
        """
        values = {
            domain_type: record.value
            for domain_type, record in repository._artifact_records.items()
        }
        return cls(values)

    def get(self, domain_type: type, default: object = None) -> object:
        """
        Mirrors `dict.get(k, default)` exactly: never raises. Returns the
        plain domain value committed for `domain_type` at the moment this
        `Snapshot` was constructed, or `default` if nothing was committed
        for that type.
        """
        return self._values.get(domain_type, default)

    def __getitem__(self, domain_type: type) -> object:
        """
        Mirrors `dict[k]` exactly: returns the plain domain value committed
        for `domain_type`, or raises `KeyError` if nothing was committed
        for that type at the moment this `Snapshot` was constructed.
        """
        return self._values[domain_type]
