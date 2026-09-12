# src/reed/synchronization/artifact_repository.py


from typing import TYPE_CHECKING, Any, Dict, Optional, cast

import warnings

from reed.activation.identifier.identifier import ArtifactRepositoryId
from reed.synchronization.artifact_repository_messages import (
    ArtifactRepositoryGet,
    ArtifactRepositoryRegistry,
    ArtifactRepositorySet,
    ArtifactRepositoryUpdate,
)
from reed.synchronization.lifecycle import LifecycleState, LifecycleStateMessage
from reed.synchronization.parcel.parcel import Parcel
from reed.synchronization.validity.sentinel import Sentinel
from reed.synchronization.validity.validity_transition import ValidityTransition
from reed.transportation.bus import Bus
from reed.transportation.enums.topics_enum import TopicsEnum
from reed.transportation.protocol.base_message import BaseMessage
from reed.transportation.protocol.message_context import MessageContext
from reed.transportation.protocol.validity_message import ValidityMessage
from reed.transportation.publisher_manager import PublisherReservedIDs

if TYPE_CHECKING:
    from reed.execution.artifact_record import ArtifactRecord


class ArtifactRepository:
    # self declared reserved
    __bus_id__ = PublisherReservedIDs.DEPOT

    def __init__(
        self,
        bus: Bus,
    ):

        self._bus = bus
        self.identity = ArtifactRepositoryId(self.__class__.__name__, bus.identity)
        self.sentinel = Sentinel()
        self._setup_ports()
        self._setup_storage()
        self._notify(LifecycleState.ACTIVE)

    def _setup_ports(self) -> None:
        self._registry_port = self._bus.port(
            owner=self,
            topic=TopicsEnum.DEPOT_REGISTRY,
            on_arrive=self._on_registry_request,
            on_end_arrive=self._on_end_registry_request,
        )

        self._get_port = self._bus.port(
            owner=self,
            topic=TopicsEnum.DEPOT_GET,
            on_arrive=self._on_get_request,
            on_end_arrive=self._on_end_get_request,
        )

        self._set_port = self._bus.port(
            owner=self,
            topic=TopicsEnum.DEPOT_SET,
            on_arrive=self._on_set_request,
            on_end_arrive=self._on_end_set_request,
        )

        self._validity_port = self._bus.port(
            owner=self,
            topic=TopicsEnum.VALIDITY,
        )

        self._lifecycle_port = self._bus.port(
            owner=self,
            topic=TopicsEnum.LIFECYCLE,
        )

    # ------------------------------------------------------------------
    # Lifecycle Management
    # ------------------------------------------------------------------

    def _notify(self, state: LifecycleState):
        if getattr(self, "_last_lifecycle_state", None) != state:

            self._lifecycle_port.send(LifecycleStateMessage(state=state))
            self._last_lifecycle_state = state

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _on_registry_request(self, message: BaseMessage, context: MessageContext):
        depot_registry = cast(ArtifactRepositoryRegistry, message)
        self.sentinel.register(message=depot_registry, context=context)

        return depot_registry, context.from_id, context.trace_id

    def _on_end_registry_request(self, result: Any):
        depot_registry, to_id, trace_id = result
        self._registry_port.send(
            message=ArtifactRepositoryRegistry(
                outpost_type=depot_registry.outpost_type,
                parcels_by_role=depot_registry.parcels_by_role,
                registered=True,
            ),
            to_id=to_id,
            reply_to=trace_id,
        )

    # ------------------------------------------------------------------

    def _on_get_request(self, message: BaseMessage, context: MessageContext):

        if not isinstance(message, ArtifactRepositoryGet):
            return

        mes: ArtifactRepositoryGet = cast(ArtifactRepositoryGet, message)
        parcel_types = mes.types
        return (self.get_pallet(parcel_types), context.from_id, context.trace_id)

    def _on_end_get_request(self, result: Any):
        pallet, to_id, trace_id = result
        self._get_port.send(ArtifactRepositoryUpdate(pallet=pallet), to_id=to_id, reply_to=trace_id)

    def _on_set_request(self, message: BaseMessage, context: MessageContext):
        if not isinstance(message, ArtifactRepositorySet):
            return

        validity_transition: ValidityTransition = self.sentinel.verify_validity(
            message=cast(ArtifactRepositorySet, message), context=context
        )

        # TODO: Can ONLY mutate if valid! dismiss otherwise

        mes: ArtifactRepositorySet = cast(ArtifactRepositorySet, message)
        pallet = mes.pallet

        confirmed_parcels: Dict[type, Parcel] = {}
        for parcel in pallet.values():
            change_status = self.set_parcel(parcel)
            if change_status:
                confirmed_parcels[type(parcel)] = parcel
        return confirmed_parcels, validity_transition, context.from_id

    def _on_end_set_request(self, result: Any):
        confirmed_parcels, validity_transition, validity_source_id = result
        if validity_transition.became_valid or validity_transition.became_invalid:
            self._validity_port.send(
                ValidityMessage(
                    validity_transition=validity_transition,
                    validity_source_id=validity_source_id,
                )
            )

        self._set_port.send(
            ArtifactRepositoryUpdate(pallet=confirmed_parcels),
            to_id=PublisherReservedIDs.BROADCAST,
        )

    # ------------------------------------------------------------------
    # Parcel Management
    # ------------------------------------------------------------------

    def _setup_storage(self):
        self._storage: Dict[type, Parcel] = {}
        # Slice 2E addition (docs/parcel_boundary_decision.md, "Addendum:
        # Slice 2E ArtifactRecord Commit Storage"): a wholly separate,
        # additive, domain-type-keyed storage path for committed
        # `ArtifactRecord`s. This dict, and the two methods below that
        # read/write it, are independent of `_storage`/`get_parcel`/
        # `set_parcel` above -- neither reads nor writes the other, and
        # `set_parcel`'s existing `isinstance(parcel, Parcel)` type check
        # is untouched.
        self._artifact_records: Dict[type, "ArtifactRecord"] = {}

    def get_pallet(self, parcel_types: list[type[Parcel]]) -> Dict[type, Parcel]:
        """
        Only return registered parcels.
        """
        pallet: Dict[type, Parcel] = {}
        for ptype in parcel_types:
            parcel = self.get_parcel(ptype)
            if parcel:
                pallet[ptype] = parcel
        return pallet

    def get_parcel(self, parcel_type: type[Parcel]) -> Optional[Parcel]:
        return self._storage.get(parcel_type)

    def set_parcel(self, parcel: Parcel) -> bool:
        if not isinstance(parcel, Parcel):
            raise TypeError("Only Parcel instances can be registered")

        self._storage[type(parcel)] = parcel
        return True

    # ------------------------------------------------------------------
    # ArtifactRecord Management (Slice 2E, additive)
    # ------------------------------------------------------------------

    def set_artifact_record(self, record: "ArtifactRecord") -> None:
        """
        Commit `record` into this ArtifactRepository's additive, domain-type-keyed
        `ArtifactRecord` storage (Slice 2E; docs/parcel_boundary_decision.md,
        "Addendum: Slice 2E ArtifactRecord Commit Storage").

        Keyed by `type(record.value)` -- the artifact's domain semantic
        type -- exactly as the accepted addendum describes. Completely
        separate from `_storage`/`get_parcel`/`set_parcel`: this method
        never reads or writes `_storage`, never touches a `Parcel`, and
        does not go through the bus (`ArtifactRepositoryGet`/`ArtifactRepositorySet`/`ArtifactRepositoryUpdate`
        are untouched).
        """
        self._artifact_records[type(record.value)] = record

    def get_artifact_record(self, domain_type: type) -> Optional["ArtifactRecord"]:
        """
        Return the committed `ArtifactRecord` for `domain_type`, or
        `None` if nothing has been committed for that domain type yet
        (Slice 2E). See `set_artifact_record` for the storage this reads.
        """
        return self._artifact_records.get(domain_type)

    def get(self, domain_type: type) -> Optional["ArtifactRecord"]:
        """
        Thin, additive alias for `get_artifact_record(domain_type)`
        (Slice 2F; docs/refactor_priority_order.md's Slice 2A row: "no
        domain-facing `repository.get(domain_type)` API on `Run` itself"
        deferred exactly this to Slice 2F).

        Exists only because `test_on_output_runs_after_commit_and_receives_domain_value`
        and `test_callback_failure_does_not_undo_committed_output` read
        committed output through `run.repository.get(<domain_type>)`
        rather than `get_artifact_record(<domain_type>)`. Delegates
        entirely to `get_artifact_record`; not a rename, not a new
        behavior, not a change to the existing Parcel storage path.
        """
        return self.get_artifact_record(domain_type)

    def show_validity(self) -> None:

        from rich.console import Console
        from rich.table import Table

        """
        Show validity of parcels tracked by Sentinel.
        """
        console = Console()
        table = Table(title="Depot Validity (Sentinel)")

        table.add_column("Parcel", style="bold")
        table.add_column("Status", justify="center")

        validity = self.sentinel._parcel_validity  # {ParcelType: bool}

        for parcel_type, ok in sorted(validity.items(), key=lambda x: x[0].__name__):
            status = "[green]VALID[/green]" if ok else "[red]INVALID[/red]"
            table.add_row(parcel_type.__name__, status)

        console.print(table)

    def close(self) -> None:
        """
        TODO:
            - Unsubscribe all Ports.
            - Remove Publisher from MessageHub.
            - Emit LifecycleState.TERMINATED.
            - Release runtime resources.
        """

        warnings.warn(
            f"{type(self).__name__}.close() is not implemented yet.",
            RuntimeWarning,
            stacklevel=2,
        )
