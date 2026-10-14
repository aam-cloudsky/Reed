"""
ArtifactRepository.

Reed's single authoritative store of committed `ArtifactRecord`s for one
`Session` (`Session.repository`, constructed as `ArtifactRepository(bus=Bus.create())`
-- see `reed/execution/session.py`). Each `Session` owns its own `Bus` +
`ArtifactRepository` pair, so two `Session`s never share repository identity
or storage.

This class previously also implemented a Bus-message-driven registration
and validity protocol for the legacy Parcel-based synchronization path
(registry/get/set ports, a `RepositoryAdapterSentinel` validity cascade,
and `get_parcel`/`set_parcel`/`get_pallet`). That protocol belonged
exclusively to the retired decorator/Parcel/`RepositoryAdapter` execution
path -- nothing in the current architecture (`Session`, `NodeSession`,
`FlowNode`) ever read or wrote through it -- and has been removed
alongside the rest of that path (see docs/refactor_state.md). What
remains is exactly what `Session`/`NodeSession` actually use: additive,
domain-type-keyed `ArtifactRecord` storage.

Slice MI-B (issue "Support multiple artifact instances and per-instance
node execution", docs/refactor/multi_instance_execution_plan.md, Section
1.2 Risk R1 and Section 5) generalizes this storage one dimension
further, from `dict[type, ArtifactRecord]` to `dict[type, dict[InstanceKey,
ArtifactRecord]]`. `instance` is keyword-only and defaults to
`InstanceKey.singleton()` on every method below, so every existing call
site (`NodeSession.commit`, `Session._commit`, and every test that calls
`set_artifact_record(record)` or `get_artifact_record(domain_type)` /
`get(domain_type)` with no `instance` argument) keeps its current,
single-instance behavior unchanged: it reads and writes the one record
filed under that type's singleton instance key, exactly as it did before
this slice. No caller outside this file needs to change for this slice to
be safe. Wiring a real, non-singleton instance key through
`Session.feed()`, `NodeSession`, or the eligibility/firing path is
explicitly out of scope here (slices MI-D and MI-E; see the plan
document's Section 5).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Optional, TYPE_CHECKING

from reed.activation.identifier.identifier import ArtifactRepositoryId
from reed.execution.instance_key import InstanceKey
from reed.transportation.bus import Bus

if TYPE_CHECKING:
    from reed.execution.artifact_record import ArtifactRecord


class ArtifactRepository:
    def __init__(
        self,
        bus: Bus,
    ):
        self._bus = bus
        self.identity = ArtifactRepositoryId(self.__class__.__name__, bus.identity)
        self._artifact_records: dict[type, dict[InstanceKey, "ArtifactRecord"]] = {}

    def set_artifact_record(
        self,
        record: "ArtifactRecord",
        *,
        instance: Optional[InstanceKey] = None,
    ) -> None:
        """
        Commit `record` into this ArtifactRepository's domain-type-and-
        instance-keyed `ArtifactRecord` storage, keyed by
        (`type(record.value)`, `instance`) -- the artifact's domain
        semantic type together with which instance of that type this
        commit belongs to.

        `instance` defaults to `InstanceKey.singleton()`, the same
        implicit instance every pre-multiplicity call site is understood
        to address (see module docstring).
        """
        key = instance if instance is not None else InstanceKey.singleton()
        self._artifact_records.setdefault(type(record.value), {})[key] = record

    def get_artifact_record(
        self,
        domain_type: type,
        *,
        instance: Optional[InstanceKey] = None,
    ) -> Optional["ArtifactRecord"]:
        """
        Return the committed `ArtifactRecord` for (`domain_type`,
        `instance`), or `None` if nothing has been committed for that
        (domain type, instance) pair yet.

        `instance` defaults to `InstanceKey.singleton()`, matching
        `set_artifact_record`'s own default (see module docstring).
        """
        key = instance if instance is not None else InstanceKey.singleton()
        return self._artifact_records.get(domain_type, {}).get(key)

    def get(
        self,
        domain_type: type,
        *,
        instance: Optional[InstanceKey] = None,
    ) -> Optional["ArtifactRecord"]:
        """
        Thin alias for `get_artifact_record(domain_type, instance=instance)`.
        """
        return self.get_artifact_record(domain_type, instance=instance)

    def remove_artifact_record(
        self,
        domain_type: type,
        *,
        instance: Optional[InstanceKey] = None,
    ) -> bool:
        """
        Remove the committed `ArtifactRecord` for (`domain_type`,
        `instance`), if one exists (Slice MI-I, Lifecycle -- docs/refactor/
        multi_instance_execution_plan.md, Section 5 item 9).

        Returns whether a record was actually removed. Tolerant of
        "nothing to remove" -- returns `False` rather than raising,
        matching this class's existing style (`get_artifact_record`
        already returns `None` rather than raising for an unknown
        (domain type, instance) pair); a caller that wants to know
        whether the removal did anything can check the return value.

        `instance` defaults to `InstanceKey.singleton()`, matching every
        other method on this class. Scoped to exactly one (domain type,
        instance) pair -- this does not remove any other domain type's
        record for the same `instance` value, even if the caller intends
        `instance` to represent one cross-type "entity" (see
        `Session.remove_instance`'s own docstring for why that binding is
        deliberately left to the caller, not built into this repository).
        """
        key = instance if instance is not None else InstanceKey.singleton()
        records_for_type = self._artifact_records.get(domain_type)

        if records_for_type is None or key not in records_for_type:
            return False

        del records_for_type[key]
        return True

    def get_all_artifact_records(
        self, domain_type: type
    ) -> Mapping[InstanceKey, "ArtifactRecord"]:
        """
        Return every currently committed instance of `domain_type`, keyed
        by `InstanceKey`, as a read-only view. Empty if nothing has been
        committed for `domain_type` yet.

        Under every pre-multiplicity, single-instance call path, this
        returns at most one entry, keyed by `InstanceKey.singleton()` --
        the same record `get_artifact_record(domain_type)` already
        returns. This method exists for the slices that need to see every
        currently known instance of a type at once (docs/refactor/
        multi_instance_execution_plan.md, slice MI-H, `Collection[T]`
        collective dependencies), not for anything in this slice's own
        scope.
        """
        return MappingProxyType(dict(self._artifact_records.get(domain_type, {})))
