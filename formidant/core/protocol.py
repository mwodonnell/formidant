from collections.abc import Iterable, Mapping
from typing import Protocol, runtime_checkable

from formidant.core.files import UploadedFile


@runtime_checkable
class Multidict(Protocol):
    """The shape of urlencoded key-value data - a form body or a query string.

    Matches Django's QueryDict; any multidict with keys()/getlist() conforms.
    """

    def keys(self) -> Iterable[str]: ...

    def getlist(self, key: str) -> list[str]: ...


@runtime_checkable
class FormData(Multidict, Protocol):
    """A complete form submission: urlencoded fields plus uploaded files.

    The only request-shaped thing the core knows; adapters wrap their
    framework's request into this.
    """

    @property
    def files(self) -> Mapping[str, UploadedFile]: ...
