from typing import TypeVar

from reed.activation.identifier.identifier import LogisticsId, NodeId
from reed.synchronization.artifact_repository import ArtifactRepository
from reed.transportation.bus import Bus
from reed.synchronization.repository_adapter import RepositoryAdapter

RepositoryAdapterT = TypeVar("RepositoryAdapterT", bound=RepositoryAdapter)


class Logistics:
    def __init__(self) -> None:
        self._bus = Bus.create()
        self._depot = ArtifactRepository(bus=self._bus)
        self.identity: LogisticsId = LogisticsId(
            self.__class__.__name__, self._depot.identity
        )

    @property
    def depot(self) -> ArtifactRepository:
        return self._depot

    def create_outpost(
        self,
        outpost_type: type[RepositoryAdapterT],
        node_id: NodeId,
    ) -> RepositoryAdapterT:

        return outpost_type(bus=self._bus, node_id=node_id, logistics_id=self.identity)
