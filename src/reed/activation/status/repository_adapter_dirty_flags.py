from enum import Enum, auto


class RepositoryAdapterDirtyFlag(Enum):
    CLEAN = auto()
    DIRTY = auto()
