"""
ArtifactRepository.

Reed's single authoritative store of committed `ArtifactRecord`s for one
`Run` (`Run.repository`, constructed as `ArtifactRepository(bus=Bus.create())`
-- see `reed/execution/run.py`). Each `Run` owns its own `Bus` +
`ArtifactRepository` pair, so two `Run`s never share repository identity
or storage.

This class previously also implemented a Bus-message-driven registration
and validity protocol for the legacy Parcel-based synchronization path
(registry/get/set ports, a `RepositoryAdapterSentinel` validity cascade,
and `get_parcel`/`set_parcel`/`get_pallet`). That protocol belonged
exclusively to the retired decorator/Parcel/`RepositoryAdapter` execution
path -- nothing in the current architecture (`Run`, `NodeRuntime`,
`FlowNode`) ever read or wrote through it -- and has been removed
alongside the rest of that path (see docs/refactor_state.md). What
remains is exactly what `Run`/`NodeRuntime` actually use: additive,
domain-type-keyed `ArtifactRecord` storage.
"""

from typing import Optional, TYPE_CHECKING

from reed.activation.identifier.identifier import ArtifactRepositoryId
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
        self._artifact_records: dict[type, "ArtifactRecord"] = {}

    def set_artifact_record(self, record: "ArtifactRecord") -> None:
        """
        Commit `record` into this ArtifactRepository's domain-type-keyed
        `ArtifactRecord` storage, keyed by `type(record.value)` -- the
        artifact's domain semantic type.
        """
        self._artifact_records[type(record.value)] = record

    def get_artifact_record(self, domain_type: type) -> Optional["ArtifactRecord"]:
        """
        Return the committed `ArtifactRecord` for `domain_type`, or
        `None` if nothing has been committed for that domain type yet.
        """
        return self._artifact_records.get(domain_type)

    def get(self, domain_type: type) -> Optional["ArtifactRecord"]:
        """
        Thin alias for `get_artifact_record(domain_type)`.
        """
        return self.get_artifact_record(domain_type)
