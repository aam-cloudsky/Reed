from dataclasses import dataclass

from reed.synchronization.validity.validity_transition import ValidityTransition
from reed.transportation.protocol.base_message import BaseMessage
from reed.transportation.publisher_manager import PublisherID


@dataclass(frozen=True)
class ValidityMessage(BaseMessage):
    validity_transition: ValidityTransition
    validity_source_id: PublisherID
