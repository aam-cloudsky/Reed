from dataclasses import field, make_dataclass
from typing import Callable, TypeAlias, cast

from reed.activation.identifier.identifier import NodeId
from reed.activation.role import Role
from reed.composition.node.node_definition import NodeDescription, ParcelType
from reed.synchronization.logistics import Logistics
from reed.synchronization.repository_adapter import RepositoryAdapter
from reed.synchronization.parcel.parcel import Parcel

NodeResult: TypeAlias = Parcel | tuple[Parcel, ...]
NodeFunction: TypeAlias = Callable[..., NodeResult]


ConsumedParameter: TypeAlias = tuple[str, ParcelType]


class RepositoryAdapterBuilder:
    def __init__(
        self,
        description: NodeDescription,
    ) -> None:
        self._description = description
        self._repository_adapter_type = self._build_repository_adapter_type()

    def build(
        self,
        *,
        node_id: NodeId,
        logistics: Logistics,
    ) -> RepositoryAdapter:

        return logistics.create_outpost(self._repository_adapter_type, node_id=node_id)

    def _build_repository_adapter_type(
        self,
    ) -> type[RepositoryAdapter]:
        generated_fields: list[tuple[str, object, object]] = []

        used_names: set[str] = set()

        for parameter_name, parcel_type in self._description.consumed_parameters:
            used_names.add(parameter_name)

            generated_fields.append(
                (
                    parameter_name,
                    parcel_type,
                    field(
                        default=None,
                        metadata={"role": Role.CONSUMED},
                    ),
                )
            )

        for index, parcel_type in enumerate(self._description.produced_types):
            field_name = self._produced_field_name(
                parcel_type=parcel_type,
                index=index,
                used_names=used_names,
            )

            generated_fields.append(
                (
                    field_name,
                    parcel_type,
                    field(
                        default=None,
                        metadata={"role": Role.PRODUCED},
                    ),
                )
            )

        generated_type = make_dataclass(
            cls_name=(f"{self._description.function.__name__}" "RepositoryAdapter"),
            fields=generated_fields,
            bases=(RepositoryAdapter,),
            namespace={
                "__module__": (self._description.function.__module__),
            },
            eq=False,
        )

        return cast(
            type[RepositoryAdapter],
            generated_type,
        )

    @staticmethod
    def _produced_field_name(
        *,
        parcel_type: ParcelType,
        index: int,
        used_names: set[str],
    ) -> str:
        base_name = f"produced_{parcel_type.__name__}"
        candidate = base_name
        suffix = index

        while candidate in used_names:
            candidate = f"{base_name}_{suffix}"
            suffix += 1

        used_names.add(candidate)
        return candidate
