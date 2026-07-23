from collections.abc import Iterable, Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class UploadedFile(Protocol):
    """A submitted file. Django's UploadedFile conforms structurally."""

    name: str
    size: int
    content_type: str | None

    def read(self) -> bytes: ...


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
