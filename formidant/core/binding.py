from typing import Any

from pydantic import BaseModel, ValidationError

from formidant.core.bound import BoundForm
from formidant.core.constants import BRACKET_MAX_DEPTH
from formidant.core.errors import error_map
from formidant.core.flatten import inflate
from formidant.core.form_types import BindResult, ListPath
from formidant.core.introspect import (
    as_model,
    collection_item_type,
    is_str_type,
    unwrap_optional,
)
from formidant.core.protocol import FormData, Multidict


def bind[M: BaseModel](
    model: type[M], data: Multidict, context: dict[str, Any] | None = None
) -> BoundForm[M]:
    """Bind submitted form data to a model, returning the bound form."""
    return BoundForm(model=model, result=bind_data(model, data, context))


def bind_data[M: BaseModel](
    model: type[M], data: Multidict, context: dict[str, Any] | None = None
) -> BindResult[M]:
    """Inflate, normalize, and validate submitted form data against a pydantic model."""
    inflated = inflate(data, list_paths_for(model))
    normalized = _normalize(inflated.data, model)
    _merge_files(normalized, data)

    try:
        instance: M | None = model.model_validate(normalized, context=context)
        validation_error = None
    except ValidationError as exc:
        instance = None
        validation_error = exc

    errors = error_map(validation_error, inflated.errors, model)
    raw = {key: data.getlist(key) for key in data.keys()}
    if errors:
        return BindResult(instance=None, errors=errors, raw=raw)
    return BindResult(instance=instance, errors={}, raw=raw)


def list_paths_for(model: type[BaseModel]) -> frozenset[ListPath]:
    """Collect the numeric-stripped paths of every scalar-collection field in the model tree."""
    paths: set[ListPath] = set()
    _walk_list_paths(model, (), paths, depth=0)
    return frozenset(paths)


def _walk_list_paths(
    model: type[BaseModel], prefix: ListPath, paths: set[ListPath], depth: int
) -> None:
    if depth >= BRACKET_MAX_DEPTH:
        return
    for name, info in model.model_fields.items():
        annotation = unwrap_optional(info.annotation)
        item = collection_item_type(annotation)
        nested = as_model(item) if item is not None else as_model(annotation)
        if item is not None and nested is None:
            paths.add((*prefix, name))
        elif nested is not None:
            _walk_list_paths(nested, (*prefix, name), paths, depth + 1)


def _normalize(data: dict[str, Any], model: type[BaseModel]) -> dict[str, Any]:
    normalized = dict(data)
    for name, info in model.model_fields.items():
        annotation = unwrap_optional(info.annotation)
        if annotation is bool and name not in normalized:
            normalized[name] = False
            continue
        if name not in normalized:
            continue
        value = normalized[name]
        if value == "" and not is_str_type(annotation):
            del normalized[name]
            continue
        nested = as_model(annotation)
        if nested is not None and isinstance(value, dict):
            normalized[name] = _normalize(value, nested)
            continue
        item_model = as_model(collection_item_type(annotation))
        if item_model is not None and isinstance(value, list):
            normalized[name] = [
                _normalize(entry, item_model) if isinstance(entry, dict) else entry
                for entry in value
            ]
    return normalized


def _merge_files(normalized: dict[str, Any], data: Multidict) -> None:
    if not isinstance(data, FormData):
        return
    for name, upload in data.files.items():
        normalized[name] = upload
