from pydantic import ValidationError

from formidant.core.constants import NON_FIELD_KEY
from formidant.core.flatten import StructuralError, path_to_name


def error_map(
    validation_error: ValidationError | None,
    structural_errors: list[StructuralError] | None = None,
) -> dict[str, list[str]]:
    """Merge pydantic and structural errors into one input-name-keyed map.

    Model-level errors (empty loc) key on NON_FIELD_KEY ("__all__", Django's
    non-field-error convention).
    """
    merged: dict[str, list[str]] = {}
    for structural in structural_errors or []:
        merged.setdefault(structural.input_name, []).append(structural.message)
    if validation_error is not None:
        for error in validation_error.errors(include_url=False):
            loc = tuple(s for s in error["loc"] if isinstance(s, str | int))
            name = path_to_name(loc) if loc else NON_FIELD_KEY
            merged.setdefault(name, []).append(error["msg"])
    return merged
