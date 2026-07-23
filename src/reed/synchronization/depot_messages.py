# core/logistics/depot_messages.py

from dataclasses import dataclass
from typing import Dict

from reed.activation.role import Role
from reed.synchronization.parcel.parcel import Parcel
from reed.transportation.protocol.base_message import BaseMessage


@dataclass(frozen=True)
class DepotUpdate(BaseMessage):
    pallet: Dict[type, Parcel]


@dataclass(frozen=True)
class DepotGet(BaseMessage):
    types: list[type[Parcel]]


@dataclass(frozen=True)
class DepotSet(BaseMessage):
    pallet: Dict[type, Parcel]


@dataclass(frozen=True)
class DepotRegistry(BaseMessage):
    outpost_type: type
    parcels_by_role: Dict[Role, set[type[Parcel]]]
    registered: bool = False
