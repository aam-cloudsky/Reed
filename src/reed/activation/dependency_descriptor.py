from dataclasses import dataclass
from typing import Generic, TypeVar

from reed.activation.role import Role

TElement = TypeVar("TElement")


@dataclass(frozen=True)
class DependencyDescriptor(Generic[TElement]):
    type_: TElement
    field_name: str
    depends_on: set[TElement]
