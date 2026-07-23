from typing import Any

from django.http import HttpRequest
from pydantic import BaseModel

from formidant.core import binding
from formidant.core.bound import BoundForm
from formidant.core.files import UploadedFile

_UNBOUND_METHODS = ("GET", "HEAD")


class DjangoFormData:
    """Adapts an HttpRequest to the core FormData protocol."""

    def __init__(self, request: HttpRequest):
        self._request = request

    def keys(self) -> Any:
        return self._request.POST.keys()

    def getlist(self, key: str) -> list[str]:
        return self._request.POST.getlist(key)

    @property
    def files(self) -> dict[str, UploadedFile]:
        return {name: upload for name, upload in self._request.FILES.items()}


def bind[M: BaseModel](
    model: type[M], request: HttpRequest, context: dict[str, Any] | None = None
) -> BoundForm[M]:
    """Method-aware bind: GET/HEAD yield an unbound form, submissions validate.

    The validation context always carries the request under "request".
    """
    if request.method in _UNBOUND_METHODS:
        return BoundForm.unbound(model)
    return binding.bind(
        model, DjangoFormData(request), context={**(context or {}), "request": request}
    )
