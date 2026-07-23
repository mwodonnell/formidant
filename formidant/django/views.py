import functools
import typing
from collections.abc import Callable
from typing import Annotated, Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from pydantic import BaseModel

from formidant.core.bound import BoundContract, BoundForm
from formidant.django.adapter import bind

OnInvalid = Callable[[HttpRequest, BoundForm], HttpResponse | None]
ViewFunc = Callable[..., HttpResponse]


def form_view(
    template: str, on_invalid: OnInvalid | None = None
) -> Callable[[ViewFunc], ViewFunc]:
    """Bind the view's annotated form parameter and own the invalid response.

    A `form: Model` parameter is valid-only: GET renders the template with an
    unbound form, an invalid submission re-renders it with errors (after the
    optional `on_invalid` hook, whose response wins when not None), and the
    body only ever runs with the validated instance. A `form: Bound[Model]`
    parameter always enters the body carrying the BoundForm instead.
    """

    def decorator(view: ViewFunc) -> ViewFunc:
        param, model, always_enter = _form_param(view)

        @functools.wraps(view)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            form = bind(model, request)
            if always_enter:
                return view(request, *args, **{**kwargs, param: form})
            if form.valid:
                return view(request, *args, **{**kwargs, param: form.instance})
            if form.bound and on_invalid is not None:
                response = on_invalid(request, form)
                if response is not None:
                    return response
            return render(request, template, {"form": form})

        return wrapper

    return decorator


def _form_param(view: ViewFunc) -> tuple[str, type[BaseModel], bool]:
    hints = typing.get_type_hints(view, include_extras=True)
    for name, annotation in hints.items():
        if name == "return":
            continue
        if typing.get_origin(annotation) is Annotated:
            contract = next(
                (
                    m
                    for m in typing.get_args(annotation)[1:]
                    if isinstance(m, BoundContract)
                ),
                None,
            )
            if contract is not None:
                return name, contract.model, True
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return name, annotation, False
    raise TypeError(
        f"{view.__qualname__} declares no form parameter "
        "(annotate one as a pydantic model or Bound[Model])"
    )
