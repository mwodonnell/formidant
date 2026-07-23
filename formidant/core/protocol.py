from collections.abc import Iterable, Mapping
from typing import Any, Protocol, runtime_checkable

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


@runtime_checkable
class UploadedFile(Protocol):
    """A submitted file, usable directly as a pydantic field type.

    Django's UploadedFile conforms structurally.
    """

    name: str
    size: int
    content_type: str | None

    def read(self) -> bytes: ...


def _validate_uploaded_file(value: Any) -> "UploadedFile":
    if not isinstance(value, UploadedFile):
        raise ValueError("expected an uploaded file")
    return value


def _uploaded_file_core_schema(
    cls: type, source: Any, handler: GetCoreSchemaHandler
) -> core_schema.CoreSchema:
    return core_schema.no_info_plain_validator_function(_validate_uploaded_file)


# Attached after class creation: a hook declared in the Protocol body becomes a
# protocol member, breaking isinstance for structural conformers like Django's
# UploadedFile. __protocol_attrs__ is frozen at class creation, so this is safe.
UploadedFile.__get_pydantic_core_schema__ = classmethod(  # type: ignore[attr-defined]
    _uploaded_file_core_schema
)


@runtime_checkable
class Multidict(Protocol):
    """Read access to multi-valued form/query data (the shape of a QueryDict)."""

    def keys(self) -> Iterable[str]: ...

    def getlist(self, key: str) -> list[str]: ...


@runtime_checkable
class FormData(Multidict, Protocol):
    """A submitted form: multi-valued fields plus uploaded files.

    The only request-shaped thing the core knows; adapters wrap their
    framework's request into this.
    """

    @property
    def files(self) -> Mapping[str, UploadedFile]: ...
