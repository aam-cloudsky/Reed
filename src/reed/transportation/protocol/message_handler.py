from typing import Any, Callable

from reed.transportation.protocol.base_message import BaseMessage
from reed.transportation.protocol.message_context import MessageContext


class MessageHandler:
    def __init__(
        self,
        accept: Callable[[BaseMessage, MessageContext], Any],
        react: Callable[[Any], None],
    ):
        self._accept = accept
        self._react = react

    def __call__(self, message: BaseMessage, context: MessageContext):
        # if context._closed:
        #    raise RuntimeError("Context already closed")

        result = self._accept(message, context)
        context.defer(self._react, result)
        context.close_transaction(result)
