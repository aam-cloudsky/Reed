from dataclasses import dataclass, field
from uuid import UUID, uuid4
from abc import ABC


@dataclass(frozen=True, slots=True)
class Identity(ABC):

    name: str
    uuid: UUID = field(
        init=False,
        default_factory=uuid4,
    )

    def __str__(self):
        return self.name


@dataclass(frozen=True)
class BusId(Identity):
    pass


@dataclass(frozen=True)
class ArtifactRepositoryId(Identity):
    bus: BusId
