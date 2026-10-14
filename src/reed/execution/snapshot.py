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
snapshot therefore still reads `ArtifactRepository`'s private
`_artifact_records` storage once, at construction time, for its keys only
(the set of domain types with at least one committed instance);
`from_repository` below is the one place in this codebase that does so,
so that reaching past `ArtifactRepository`'s public interface stays
contained to this module instead of leaking into `Session` or anywhere
else.

Slice MI-B (docs/refactor/multi_instance_execution_plan.md) generalized
`ArtifactRepository`'s storage from `dict[type, ArtifactRecord]` to
`dict[type, dict[InstanceKey, ArtifactRecord]]`; this method was first
adjusted in that slice to read through the public
`get_artifact_record(domain_type)` accessor (defaulting to
`InstanceKey.singleton()`) rather than assuming the private dict's value
was the record itself.

Corrected post-Slice-MI-J (identified during an independent review of
the whole multi-instance feature, after MI-J's own review had already
signed off): that MI-B adjustment was still incomplete. A domain type
committed only via `feed_instances(...)` (never via plain `feed()`) has
entries in `repository._artifact_records` -- so it is a key this method
iterates over -- but has NO record under `InstanceKey.singleton()`
specifically, so `get_artifact_record(domain_type)` returns `None` and
the original `.value` access raised `AttributeError`. This broke
invariant #33 ("full current repository state") outright for exactly the
pure multi-instance use case this whole issue exists to support, and
broke `Session.invoke()` (which calls `snapshot()` internally) the same
way. Fixed by reading every currently known instance via
`get_all_artifact_records(domain_type)` instead of assuming a singleton
record exists; `Snapshot` now stores `dict[type, dict[InstanceKey,
object]]` internally. The zero-argument `.get(domain_type)` /
`snapshot[domain_type]` surface is completely unchanged for every
pre-multi-instance caller (both still address the singleton instance
specifically, exactly as before): `.get(...)` still never raises,
`[...]` still raises `KeyError` if the type has no committed value AT
SINGLETON SCOPE (not "no committed value under any instance" -- a type
committed only under real instances and never under the singleton is
`KeyError` from `[...]`, same as if nothing were committed for it at
all, since `[...]`'s whole contract has only ever addressed one specific
value per type). A new, additive `instance=` keyword on `.get(...)`, and
a new `.instances(domain_type)` accessor returning every currently known
`InstanceKey -> value` mapping for that type, are how the actual
multi-instance state -- invisible through the pre-existing single-value
surface -- becomes reachable, so that "full current repository state"
(invariant #33) is genuinely true rather than silently true-except-for-
non-singleton-only-types.
"""

from typing import TYPE_CHECKING

from reed.execution.instance_key import InstanceKey

if TYPE_CHECKING:
    from reed.synchronization.artifact_repository import ArtifactRepository


class Snapshot:
    """
    Immutable, plain-domain-value view over an `ArtifactRepository`'s full
    current state at the moment it was constructed. See module docstring.
    """

    def __init__(self, values: dict[type, dict[InstanceKey, object]]) -> None:
        self._values: dict[type, dict[InstanceKey, object]] = {
            domain_type: dict(by_instance) for domain_type, by_instance in values.items()
        }

    @classmethod
    def from_repository(cls, repository: "ArtifactRepository") -> "Snapshot":
        """
        Build a `Snapshot` capturing `repository`'s full current state: one
        entry per domain type with at least one committed instance, holding
        every currently known `InstanceKey -> value` pair for it (never an
        `ArtifactRecord` itself). See module docstring for why this is the
        one place that reads `ArtifactRepository`'s private
        `_artifact_records` storage directly (for its keys only --
        `get_all_artifact_records` is the public accessor used for each
        key's actual values).
        """
        values = {
            domain_type: {
                instance: record.value
                for instance, record in repository.get_all_artifact_records(
                    domain_type
                ).items()
            }
            for domain_type in repository._artifact_records
        }
        return cls(values)

    def get(
        self,
        domain_type: type,
        default: object = None,
        *,
        instance: "InstanceKey | None" = None,
    ) -> object:
        """
        Mirrors `dict.get(k, default)` exactly: never raises. Returns the
        plain domain value committed for `domain_type` at `instance`
        (defaulting to `InstanceKey.singleton()`, matching every other
        instance-aware accessor in this codebase) at the moment this
        `Snapshot` was constructed, or `default` if nothing was committed
        for that (domain type, instance) pair -- including when other
        instances of `domain_type` exist but this one does not.
        """
        key = instance if instance is not None else InstanceKey.singleton()
        by_instance = self._values.get(domain_type)
        if by_instance is None:
            return default
        return by_instance.get(key, default)

    def __getitem__(self, domain_type: type) -> object:
        """
        Mirrors `dict[k]` exactly: returns the plain domain value committed
        for `domain_type` AT SINGLETON SCOPE specifically, or raises
        `KeyError` if nothing was committed for that type at singleton
        scope at the moment this `Snapshot` was constructed -- including
        when `domain_type` has real, non-singleton instances committed but
        no singleton-scoped value of its own (use `.instances(domain_type)`
        to reach those). This preserves the exact pre-multi-instance
        contract for every caller that never uses `InstanceKey` at all:
        such a caller's values are always singleton-scoped, so `[...]`'s
        behavior for it is completely unchanged.
        """
        by_instance = self._values.get(domain_type)
        singleton_key = InstanceKey.singleton()
        if by_instance is None or singleton_key not in by_instance:
            raise KeyError(domain_type)
        return by_instance[singleton_key]

    def instances(self, domain_type: type) -> dict["InstanceKey", object]:
        """
        Every currently known instance of `domain_type`, as a fresh
        `{InstanceKey: value}` dict (plain domain values, never
        `ArtifactRecord`) -- empty if nothing was committed for
        `domain_type` at all. This is the multi-instance-aware complement
        to `.get(...)`/`[...]` (which each address exactly one instance):
        it is how `Snapshot` represents "full current repository state"
        (invariant #33) for a domain type with more than one instance, or
        with instances but no singleton-scoped value of its own.
        """
        return dict(self._values.get(domain_type, {}))
