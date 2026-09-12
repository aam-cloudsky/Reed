

from ast import Module
from dataclasses import dataclass
from typing import Dict, Set, Type

from reed.synchronization.parcel.parcel import Parcel


@dataclass(frozen=True)
class RepositoryAdapterValidityTransition:
    # Estado
    before: Dict[Type[Parcel], bool]
    after: Dict[Type[Parcel], bool]

    # Diferença semântica
    became_invalid: Set[Type[Parcel]]
    became_valid: Set[Type[Parcel]]

    # Origem causal
    origin_pallet: Set[Type[Parcel]]

    # Contexto operacional
    affected_modules: Set[Type["Module"]]
    execution_order: list[Type["Module"]]

    def __str__(self) -> str:

        def names(types: Set[Type]) -> str:
            return ", ".join(t.__name__ for t in types) or "∅"

        def state(mapping: Dict[Type, bool]) -> str:
            if not mapping:
                return "∅"
            return ", ".join(
                f"{t.__name__}={'VALID' if v else 'INVALID'}"
                for t, v in sorted(mapping.items(), key=lambda x: x[0].__name__)
            )

        return (
            "\n[RepositoryAdapterValidityTransition]\n"
            f"  Origin parcels : {names(self.origin_pallet)}\n"
            f"  Became VALID   : {names(self.became_valid)}\n"
            f"  Became INVALID : {names(self.became_invalid)}\n"
            f"  Affected mods  : {names(self.affected_modules)}\n"
            f"  Exec order     : "
            f"{' → '.join(m.__name__ for m in self.execution_order) or '∅'}\n"
            f"  AFTER state    : {state(self.after)}"
        )
