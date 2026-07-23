import functools
import inspect
import typing
from collections.abc import Callable
from typing import Annotated, Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from pydantic import BaseModel, TypeAdapter, ValidationError

from formidant.core.bound import BoundContract, BoundForm, FormContract
from formidant.django.adapter import bind

OnInvalid = Callable[[HttpRequest, BoundForm], HttpResponse | None]
OnInvalidSources = Callable[[HttpRequest, dict[str, list[str]]], HttpResponse | None]
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


def bind_view(
    view: ViewFunc | None = None, on_invalid: OnInvalidSources | None = None
) -> Any:
    """Bind path, query, and Form[Model] parameters from one view signature.

    Parameters matching URLconf kwargs bind from the path, Form[Model]
    parameters from the submitted form body (the body receives the validated
    instance), and remaining annotated scalars from the query string -
    coerced with pydantic, respecting signature defaults. Invalid input
    yields a plain 400 listing source-prefixed errors unless `on_invalid`
    returns its own response.
    """

    def decorator(func: ViewFunc) -> ViewFunc:
        params = _source_params(func)

        @functools.wraps(func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            errors: dict[str, list[str]] = {}
            resolved: dict[str, Any] = {}
            for param in params:
                param.resolve(request, kwargs, resolved, errors)
            if errors:
                if on_invalid is not None:
                    response = on_invalid(request, errors)
                    if response is not None:
                        return response
                return _invalid_sources_response(errors)
            return func(request, *args, **{**kwargs, **resolved})

        return wrapper

    return decorator(view) if view is not None else decorator


class _SourceParam:
    def __init__(self, name: str, annotation: Any, default: Any):
        self.name = name
        self.default = default
        self.form_model: type[BaseModel] | None = None
        if typing.get_origin(annotation) is Annotated:
            contract = next(
                (
                    m
                    for m in typing.get_args(annotation)[1:]
                    if isinstance(m, FormContract)
                ),
                None,
            )
            if contract is not None:
                self.form_model = contract.model
                return
        self.adapter: TypeAdapter[Any] = TypeAdapter(annotation)

    def resolve(
        self,
        request: HttpRequest,
        url_kwargs: dict[str, Any],
        resolved: dict[str, Any],
        errors: dict[str, list[str]],
    ) -> None:
        if self.form_model is not None:
            self._resolve_form(request, resolved, errors)
        elif self.name in url_kwargs:
            self._coerce("path", url_kwargs[self.name], resolved, errors)
        elif self.name in request.GET:
            self._coerce("query", request.GET[self.name], resolved, errors)
        elif self.default is not inspect.Parameter.empty:
            resolved[self.name] = self.default
        else:
            errors[f"query: {self.name}"] = ["Field required"]

    def _resolve_form(
        self,
        request: HttpRequest,
        resolved: dict[str, Any],
        errors: dict[str, list[str]],
    ) -> None:
        form = bind(self.form_model, request)
        if form.valid:
            resolved[self.name] = form.instance
        elif not form.bound:
            errors[f"form: {self.name}"] = ["No submitted form data"]
        else:
            for key, messages in form.errors.items():
                errors[f"form: {key}"] = messages

    def _coerce(
        self,
        source: str,
        raw: Any,
        resolved: dict[str, Any],
        errors: dict[str, list[str]],
    ) -> None:
        try:
            resolved[self.name] = self.adapter.validate_python(raw)
        except ValidationError as exc:
            errors[f"{source}: {self.name}"] = [
                error["msg"] for error in exc.errors(include_url=False)
            ]


def _source_params(view: ViewFunc) -> tuple[_SourceParam, ...]:
    hints = typing.get_type_hints(view, include_extras=True)
    signature = inspect.signature(view)
    params = []
    for name, parameter in signature.parameters.items():
        annotation = hints.get(name)
        if annotation is None or annotation is HttpRequest:
            continue
        params.append(_SourceParam(name, annotation, parameter.default))
    return tuple(params)


def _invalid_sources_response(errors: dict[str, list[str]]) -> HttpResponse:
    lines = [
        f"{key}: {message}" for key, messages in errors.items() for message in messages
    ]
    return HttpResponse(
        "\n".join(lines), status=400, content_type="text/plain; charset=utf-8"
    )
