import types
import typing
from typing import Any

from pydantic import BaseModel

COLLECTION_ORIGINS = (list, set, frozenset, tuple)


def unwrap_optional(annotation: Any) -> Any:
    if (
        isinstance(annotation, types.UnionType)
        or typing.get_origin(annotation) is typing.Union
    ):
        args = [a for a in typing.get_args(annotation) if a is not types.NoneType]
        if len(args) == 1:
            return args[0]
    return annotation


def is_optional(annotation: Any) -> bool:
    return unwrap_optional(annotation) is not annotation


def collection_item_type(annotation: Any) -> Any | None:
    if typing.get_origin(annotation) in COLLECTION_ORIGINS:
        args = typing.get_args(annotation)
        return args[0] if args else str
    return None


def as_model(annotation: Any) -> type[BaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def is_str_type(annotation: Any) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, str)


def literal_values(annotation: Any) -> tuple[Any, ...] | None:
    if typing.get_origin(annotation) is typing.Literal:
        return typing.get_args(annotation)
    return None
