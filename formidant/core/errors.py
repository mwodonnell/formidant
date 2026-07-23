from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo

from formidant.core.constants import NON_FIELD_KEY
from formidant.core.flatten import path_to_name
from formidant.core.form_types import StructuralError
from formidant.core.introspect import as_model, collection_item_type, unwrap_optional
from formidant.core.meta import Meta


def error_map(
    validation_error: ValidationError | None,
    structural_errors: list[StructuralError] | None = None,
    model: type[BaseModel] | None = None,
) -> dict[str, list[str]]:
    """Merge pydantic and structural errors into one input-name-keyed map.

    Model-level errors (empty loc) key on NON_FIELD_KEY ("__all__", Django's
    non-field-error convention). When `model` is given, per-field
    Meta(messages={...}) overrides replace pydantic's default text by error type.
    """
    merged: dict[str, list[str]] = {}
    for structural in structural_errors or []:
        merged.setdefault(structural.input_name, []).append(structural.message)
    if validation_error is not None:
        for error in validation_error.errors(include_url=False):
            loc = tuple(s for s in error["loc"] if isinstance(s, str | int))
            name = path_to_name(loc) if loc else NON_FIELD_KEY
            message = _override_for(model, loc, error["type"]) or error["msg"]
            merged.setdefault(name, []).append(message)
    return merged


def _override_for(
    model: type[BaseModel] | None, loc: tuple[str | int, ...], error_type: str
) -> str | None:
    if model is None:
        return None
    info: FieldInfo | None = None
    current: type[BaseModel] | None = model
    for segment in loc:
        if isinstance(segment, int):
            continue
        if current is None:
            return None
        info = current.model_fields.get(segment)
        if info is None:
            return None
        annotation = unwrap_optional(info.annotation)
        current = as_model(annotation) or as_model(collection_item_type(annotation))
    if info is None:
        return None
    meta = next((m for m in info.metadata if isinstance(m, Meta)), None)
    return dict(meta.messages).get(error_type) if meta else None
