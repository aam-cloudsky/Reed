from __future__ import annotations


from typing import Generic, TypeVar

from reed.activation.dependency_descriptor import DependencyDescriptor
from reed.activation.status.repository_adapter_dirty_flags import (
    RepositoryAdapterDirtyFlag,
)
from reed.activation.status.repository_adapter_status import RepositoryAdapterStatus




TElement = TypeVar("TElement")


class RepositoryAdapterStatusManager(Generic[TElement]):

    def __init__(
        self,
        descriptors: dict[TElement, DependencyDescriptor[TElement]],
    ) -> None:

        flags: dict[TElement, RepositoryAdapterDirtyFlag] = {
            element: RepositoryAdapterDirtyFlag.CLEAN for element in descriptors
        }

        dependency_flags: dict[
            TElement,
            dict[TElement, RepositoryAdapterDirtyFlag],
        ] = {}

        for produced, descriptor in descriptors.items():

            if not descriptor.depends_on:
                continue

            dependency_flags[produced] = {
                dependency: RepositoryAdapterDirtyFlag.CLEAN
                for dependency in descriptor.depends_on
            }

        self.status = RepositoryAdapterStatus(
            flags=flags,
            dependency_flags=dependency_flags,
        )

    # -------------------------------------------------------
    # Dirty Flag
    # -------------------------------------------------------

    def mark_dirty(
        self,
        dependency: TElement,
    ) -> bool:
        """
        Performs dirty propagation.
        Marks the given dependency as DIRTY and propagates this state to every
        produced element that depends on it.

        Returns:
            True if the global status changed (CLEAN → DIRTY),
            False otherwise.

        """

        changed = False

        if self.status.flags[dependency] is RepositoryAdapterDirtyFlag.CLEAN:
            self.status.flags[dependency] = RepositoryAdapterDirtyFlag.DIRTY
            changed = True

        for produced, flags in self.status.dependency_flags.items():

            if dependency not in flags:
                continue

            if flags[dependency] is RepositoryAdapterDirtyFlag.CLEAN:
                flags[dependency] = RepositoryAdapterDirtyFlag.DIRTY

            self.status.flags[produced] = RepositoryAdapterDirtyFlag.DIRTY

        return changed

    def mark_clean(
        self,
        produced: TElement,
    ) -> None:
        """
        Performs clean backpropagation.

        Marks the given produced element as CLEAN and propagates the cleanup
        back through its dependencies.

        A dependency is marked CLEAN only if no other produced element still
        depends on a DIRTY version of it.
        """

        self.status.flags[produced] = RepositoryAdapterDirtyFlag.CLEAN
        self._clean_dependencies(produced)

    def _clean_dependencies(self, produced):
        if produced not in self.status.dependency_flags:
            return

        flags = self.status.dependency_flags[produced]

        for dependency in flags:

            flags[dependency] = RepositoryAdapterDirtyFlag.CLEAN

            dependency_still_dirty = any(
                dependency in produced_flags
                and produced_flags[dependency] is RepositoryAdapterDirtyFlag.DIRTY
                for produced_flags in self.status.dependency_flags.values()
            )

            self.status.flags[dependency] = (
                RepositoryAdapterDirtyFlag.DIRTY
                if dependency_still_dirty
                else RepositoryAdapterDirtyFlag.CLEAN
            )

    # -------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------

    def clear(self) -> None:

        for element in self.status.flags:
            self.status.flags[element] = RepositoryAdapterDirtyFlag.CLEAN

        for flags in self.status.dependency_flags.values():
            for dependency in flags:
                flags[dependency] = RepositoryAdapterDirtyFlag.CLEAN
