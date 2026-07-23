from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, ClassVar
from uuid import UUID

import annotated_types
from pydantic import BaseModel, EmailStr, HttpUrl, SecretStr
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from formidant.core.files import UploadedFile
from formidant.core.introspect import (
    as_model,
    collection_item_type,
    is_optional,
    literal_values,
    unwrap_optional,
)
from formidant.core.meta import Meta

Choices = tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Widget:
    template: ClassVar[str] = "widgets/input.html"


@dataclass(frozen=True)
class Input(Widget):
    input_type: str = "text"


@dataclass(frozen=True)
class Checkbox(Widget):
    template: ClassVar[str] = "widgets/checkbox.html"


@dataclass(frozen=True)
class Select(Widget):
    template: ClassVar[str] = "widgets/select.html"
    choices: Choices = ()


@dataclass(frozen=True)
class CheckboxGroup(Widget):
    template: ClassVar[str] = "widgets/checkbox_group.html"
    choices: Choices = ()


@dataclass(frozen=True)
class FileInput(Widget):
    template: ClassVar[str] = "widgets/file.html"


@dataclass(frozen=True)
class Fieldset(Widget):
    template: ClassVar[str] = "widgets/fieldset.html"


@dataclass(frozen=True)
class Repeat(Widget):
    template: ClassVar[str] = "widgets/repeat.html"


@dataclass(frozen=True)
class FieldSpec:
    """Everything the renderer needs to draw one field."""

    name: str
    label: str
    widget: Widget
    required: bool = True
    help_text: str | None = None
    placeholder: str | None = None
    attrs: Mapping[str, str] = field(default_factory=dict)
    default: Any = None
    messages: Mapping[str, str] = field(default_factory=dict)
    children: tuple["FieldSpec", ...] = ()


WidgetFactory = Callable[[Any], Widget]

_registry: dict[type, WidgetFactory] = {}


def register_widget(*annotations: type) -> Callable[[WidgetFactory], WidgetFactory]:
    """Register a widget factory for one or more field types.

    Public extension point: third-party types plug in through the same
    decorator the built-in matrix uses. Resolution walks the field type's MRO,
    so subclasses inherit their base type's widget unless registered themselves.
    """

    def decorator(factory: WidgetFactory) -> WidgetFactory:
        for annotation in annotations:
            _registry[annotation] = factory
        return factory

    return decorator


def resolve_fields(model: type[BaseModel]) -> tuple[FieldSpec, ...]:
    """Resolve every field of a model to its rendering spec, in declaration order."""
    return tuple(
        _resolve_field(name, info) for name, info in model.model_fields.items()
    )


def resolve_widget(annotation: Any) -> Widget:
    """Resolve a field type to its default widget: structural cases, then the registry."""
    values = literal_values(annotation)
    if values is not None:
        return Select(choices=tuple((str(v), str(v)) for v in values))
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return Select(choices=_enum_choices(annotation))
    for base in getattr(annotation, "__mro__", ()):
        if base in _registry:
            return _registry[base](annotation)
    return Input()


def _resolve_field(name: str, info: FieldInfo) -> FieldSpec:
    meta = next((m for m in info.metadata if isinstance(m, Meta)), Meta())
    annotation = unwrap_optional(info.annotation)
    nested = as_model(annotation)
    item = collection_item_type(annotation)
    item_model = as_model(item) if item is not None else None

    children: tuple[FieldSpec, ...] = ()
    if meta.widget is not None:
        widget: Widget = meta.widget
    elif item_model is not None:
        widget = Repeat()
        children = resolve_fields(item_model)
    elif nested is not None:
        widget = Fieldset()
        children = resolve_fields(nested)
    elif item is not None:
        widget = _scalar_list_widget(item)
    else:
        widget = resolve_widget(annotation)

    required = (
        info.is_required()
        and annotation is not bool
        and not is_optional(info.annotation)
    )
    return FieldSpec(
        name=name,
        label=meta.label or name.replace("_", " ").capitalize(),
        widget=widget,
        required=required,
        help_text=meta.help_text,
        placeholder=meta.placeholder,
        attrs={**_constraint_attrs(info), **meta.attrs},
        default=_default_for(info),
        messages=meta.messages,
        children=children,
    )


def _scalar_list_widget(item: Any) -> Widget:
    values = literal_values(item)
    if values is not None:
        return CheckboxGroup(choices=tuple((str(v), str(v)) for v in values))
    if isinstance(item, type) and issubclass(item, Enum):
        return CheckboxGroup(choices=_enum_choices(item))
    return Input()


def _enum_choices(enum_type: type[Enum]) -> Choices:
    return tuple(
        (str(member.value), member.name.replace("_", " ").capitalize())
        for member in enum_type
    )


def _constraint_attrs(info: FieldInfo) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for constraint in info.metadata:
        if isinstance(constraint, annotated_types.MaxLen):
            attrs["maxlength"] = str(constraint.max_length)
        elif isinstance(constraint, annotated_types.MinLen):
            attrs["minlength"] = str(constraint.min_length)
        elif isinstance(constraint, annotated_types.Ge):
            attrs["min"] = str(constraint.ge)
        elif isinstance(constraint, annotated_types.Le):
            attrs["max"] = str(constraint.le)
    return attrs


def _default_for(info: FieldInfo) -> Any:
    if info.is_required():
        return None
    default = info.get_default(call_default_factory=True)
    return None if default is PydanticUndefined else default


@register_widget(bool)
def _bool_widget(annotation: Any) -> Widget:
    return Checkbox()


@register_widget(EmailStr)
def _email_widget(annotation: Any) -> Widget:
    return Input(input_type="email")


@register_widget(SecretStr)
def _secret_widget(annotation: Any) -> Widget:
    return Input(input_type="password")


@register_widget(HttpUrl)
def _url_widget(annotation: Any) -> Widget:
    return Input(input_type="url")


@register_widget(str, UUID)
def _text_widget(annotation: Any) -> Widget:
    return Input(input_type="text")


@register_widget(int, float, Decimal)
def _number_widget(annotation: Any) -> Widget:
    return Input(input_type="number")


@register_widget(datetime)
def _datetime_widget(annotation: Any) -> Widget:
    return Input(input_type="datetime-local")


@register_widget(date)
def _date_widget(annotation: Any) -> Widget:
    return Input(input_type="date")


@register_widget(time)
def _time_widget(annotation: Any) -> Widget:
    return Input(input_type="time")


@register_widget(UploadedFile)
def _file_widget(annotation: Any) -> Widget:
    return FileInput()
