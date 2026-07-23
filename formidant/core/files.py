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
