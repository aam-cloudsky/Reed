from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Iterable, TypeVar

from reed.activation.status.repository_adapter_dirty_flags import (
    RepositoryAdapterDirtyFlag,
)


TElement = TypeVar("TElement")


@dataclass
class RepositoryAdapterStatus(Generic[TElement]):

    flags: dict[TElement, RepositoryAdapterDirtyFlag] = field(default_factory=dict)

    dependency_flags: dict[
        TElement,
        dict[TElement, RepositoryAdapterDirtyFlag],
    ] = field(default_factory=dict)

    # -------------------------------------------------------
    # Dependency Queries
    # -------------------------------------------------------

    def any_dependencies_dirty(
        self,
        produced: TElement,
    ) -> bool:

        return any(
            flag is RepositoryAdapterDirtyFlag.DIRTY
            for flag in self.dependency_flags[produced].values()
        )

    def all_dependencies_dirty(
        self,
        produced: TElement,
    ) -> bool:

        flags = self.dependency_flags[produced]

        return len(flags) > 0 and all(
            flag is RepositoryAdapterDirtyFlag.DIRTY for flag in flags.values()
        )

    def dirty_dependencies(
        self,
        produced: TElement,
    ) -> set[TElement]:

        return {
            dependency
            for dependency, flag in self.dependency_flags[produced].items()
            if flag is RepositoryAdapterDirtyFlag.DIRTY
        }

    def any_dirty(
        self,
        produced: Iterable[TElement],
    ) -> bool:

        return any(self.any_dependencies_dirty(p) for p in produced)

    def all_dirty(
        self,
        produced: Iterable[TElement],
    ) -> bool:

        return all(self.all_dependencies_dirty(p) for p in produced)
