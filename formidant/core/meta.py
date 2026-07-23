from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from formidant.core.widgets import Widget


@dataclass(frozen=True)
class Meta:
    """Presentation metadata for a form field, attached via Annotated.

    Validation-inert: pydantic carries it in FieldInfo.metadata and ignores it,
    so the model's validation, serialization, and JSON schema are untouched.
    `messages` overrides error text per pydantic error type, e.g.
    {"string_too_short": "Too short"}.
    """

    label: str | None = None
    help_text: str | None = None
    placeholder: str | None = None
    widget: "Widget | None" = None
    attrs: Mapping[str, str] = field(default_factory=dict)
    messages: Mapping[str, str] = field(default_factory=dict)
