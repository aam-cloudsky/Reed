from typing import Any, Callable, Optional, Self

from reed.activation.identifier.identifier import BusId
from reed.transportation.enums.topics_enum import TopicsEnum
from reed.transportation.hub import MessageHub
from reed.transportation.port import Port
from reed.transportation.protocol.base_message import BaseMessage
from reed.transportation.protocol.message_context import MessageContext


class Bus:
    def __init__(self, hub: MessageHub) -> None:
        self._hub = hub
        self.identity = BusId(self.__class__.__name__)

    @classmethod
    def create(cls) -> Self:
        return cls(hub=MessageHub())

    def port(
        self,
        *,
        topic: TopicsEnum,
        owner: object,
        on_arrive: Callable[
            [BaseMessage, MessageContext],
            Any,
        ] = lambda message, context: None,
        on_end_arrive: Callable[
            [Optional[Any]],
            Any,
        ] = lambda result: None,
    ) -> Port:
        return Port(
            message_hub=self._hub,
            topic=topic,
            owner=owner,
            on_arrive=on_arrive,
            on_end_arrive=on_end_arrive,
        )
