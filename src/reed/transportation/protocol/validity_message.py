from dataclasses import dataclass

from reed.synchronization.validity.repository_adapter_validity_transition import (
    RepositoryAdapterValidityTransition,
)
from reed.transportation.protocol.base_message import BaseMessage
from reed.transportation.publisher_manager import PublisherID


@dataclass(frozen=True)
class ValidityMessage(BaseMessage):
    validity_transition: RepositoryAdapterValidityTransition
    validity_source_id: PublisherID
