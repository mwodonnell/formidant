from collections.abc import Sequence
from datetime import date, datetime, time
from enum import Enum
from pathlib import Path as FsPath
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PackageLoader
from markupsafe import Markup
from pydantic import BaseModel

from formidant.core.constants import NON_FIELD_KEY
from formidant.core.flatten import path_to_name
from formidant.core.form_types import Path
from formidant.core.widgets import (
    Checkbox,
    CheckboxGroup,
    FieldSpec,
    Fieldset,
    Input,
    Repeat,
    Select,
    resolve_fields,
)

if TYPE_CHECKING:
    from formidant.core.bound import BoundForm


@runtime_checkable
class TemplateEngine(Protocol):
    """Renders a named template with a context to an HTML string."""

    def render(self, name: str, context: dict[str, Any]) -> str: ...


class Jinja2Engine:
    """The default engine: user template dirs first, packaged defaults as fallback.

    Autoescape is always on and not configurable.
    """

    def __init__(self, template_dirs: Sequence[str | FsPath] = ()):
        loaders = []
        if template_dirs:
            loaders.append(FileSystemLoader([str(d) for d in template_dirs]))
        loaders.append(PackageLoader("formidant.core", "templates"))
        self._environment = Environment(loader=ChoiceLoader(loaders), autoescape=True)

    def render(self, name: str, context: dict[str, Any]) -> str:
        return self._environment.get_template(name).render(context)


default_engine = Jinja2Engine()


def render_form(
    form: "BoundForm[Any]",
    engine: TemplateEngine | None = None,
    hidden_inputs: str = "",
) -> str:
    """Render the full form body: form-level errors, hidden inputs, every field.

    `hidden_inputs` is inserted verbatim as trusted HTML - the adapter's CSRF slot.
    """
    return _Renderer(form, engine or default_engine).form_html(hidden_inputs)


def render_field(
    form: "BoundForm[Any]",
    name: str,
    engine: TemplateEngine | None = None,
    index: int | None = None,
) -> str:
    """Render one top-level field in isolation, or one row of a repeat field.

    With `index`, the field must be a list-of-models field; the single row is
    rendered exactly as it appears inside the full form (htmx partial swaps).
    """
    renderer = _Renderer(form, engine or default_engine)
    spec = renderer.spec_for(name)
    if index is not None:
        return renderer.repeat_row_html(spec, (name,), index)
    return renderer.field_html(spec, (name,))


class _Renderer:
    def __init__(self, form: "BoundForm[Any]", engine: TemplateEngine):
        self.form = form
        self.engine = engine
        self.initial: dict[str, Any] = (
            form.initial.model_dump(mode="json")
            if form.initial is not None
            else _default_tree(form.model)
        )

    def spec_for(self, name: str) -> FieldSpec:
        specs = {spec.name: spec for spec in resolve_fields(self.form.model)}
        return specs[name]

    def form_html(self, hidden_inputs: str) -> str:
        fields = [
            Markup(self.field_html(spec, (spec.name,)))
            for spec in resolve_fields(self.form.model)
        ]
        return self.engine.render(
            "form.html",
            {
                "form_errors": self.form.errors.get(NON_FIELD_KEY, []),
                "hidden_inputs": Markup(hidden_inputs),
                "fields": fields,
            },
        )

    def field_html(self, spec: FieldSpec, path: Path) -> str:
        full_name = path_to_name(path)
        container = isinstance(spec.widget, Fieldset | Repeat)
        return self.engine.render(
            "field.html",
            {
                "label": spec.label,
                "id": f"id_{full_name}",
                "container": container,
                "widget_html": Markup(self.widget_html(spec, path)),
                "errors": self.form.errors.get(full_name, []),
                "help_text": spec.help_text,
            },
        )

    def widget_html(self, spec: FieldSpec, path: Path) -> str:
        full_name = path_to_name(path)
        widget = spec.widget
        context: dict[str, Any] = {
            "name": full_name,
            "id": f"id_{full_name}",
            "required": spec.required,
            "attrs": spec.attrs,
            "placeholder": spec.placeholder,
            "label": spec.label,
        }
        if isinstance(widget, Checkbox):
            context["checked"] = self._checked(spec, path)
        elif isinstance(widget, Select | CheckboxGroup):
            context["choices"] = widget.choices
            context["selected"] = self._values(spec, path)
        elif isinstance(widget, Fieldset):
            context["children_html"] = Markup(
                "".join(
                    self.field_html(child, (*path, child.name))
                    for child in spec.children
                )
            )
        elif isinstance(widget, Repeat):
            context["rows"] = [
                Markup(self.repeat_row_html(spec, path, index))
                for index in range(self._row_count(path))
            ]
        else:
            context["input_type"] = (
                widget.input_type if isinstance(widget, Input) else "text"
            )
            context["value"] = self._value(spec, path)
        return self.engine.render(widget.template, context)

    def repeat_row_html(self, spec: FieldSpec, path: Path, index: int) -> str:
        children_html = Markup(
            "".join(
                self.field_html(child, (*path, index, child.name))
                for child in spec.children
            )
        )
        return self.engine.render(
            "widgets/repeat_row.html", {"children_html": children_html}
        )

    def _value(self, spec: FieldSpec, path: Path) -> str:
        if isinstance(spec.widget, Input) and spec.widget.input_type == "password":
            return ""
        if self.form.bound:
            values = self.form.raw.get(path_to_name(path), [])
            return values[-1] if values else ""
        initial = self._initial_at(path)
        if initial is not None:
            return _display_value(initial)
        return _display_value(spec.default)

    def _values(self, spec: FieldSpec, path: Path) -> list[str]:
        if self.form.bound:
            return self.form.raw.get(path_to_name(path), [])
        initial = self._initial_at(path)
        source = initial if initial is not None else spec.default
        if isinstance(source, list | tuple | set | frozenset):
            return [_display_value(item) for item in source]
        return [_display_value(source)] if source is not None else []

    def _checked(self, spec: FieldSpec, path: Path) -> bool:
        if self.form.bound:
            return path_to_name(path) in self.form.raw
        initial = self._initial_at(path)
        return bool(initial) if initial is not None else bool(spec.default)

    def _row_count(self, path: Path) -> int:
        if self.form.bound:
            prefix = path_to_name(path) + "["
            indexes = [
                int(key[len(prefix) :].split("]", 1)[0])
                for key in self.form.raw
                if key.startswith(prefix)
                and key[len(prefix) :].split("]", 1)[0].isdigit()
            ]
            return max(indexes) + 1 if indexes else 0
        initial = self._initial_at(path)
        return len(initial) if isinstance(initial, list) else 0

    def _initial_at(self, path: Path) -> Any:
        node: Any = self.initial
        for segment in path:
            if isinstance(segment, int):
                if not isinstance(node, list) or segment >= len(node):
                    return None
                node = node[segment]
            else:
                if not isinstance(node, dict) or segment not in node:
                    return None
                node = node[segment]
        return node


def _default_tree(model: type[BaseModel]) -> dict[str, Any]:
    tree: dict[str, Any] = {}
    for spec in resolve_fields(model):
        default = spec.default
        if default is None:
            continue
        if isinstance(default, BaseModel):
            tree[spec.name] = default.model_dump(mode="json")
        elif isinstance(default, list):
            tree[spec.name] = [
                item.model_dump(mode="json") if isinstance(item, BaseModel) else item
                for item in default
            ]
        else:
            tree[spec.name] = default
    return tree


def _display_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, date | datetime | time):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return ""
    return str(value)
