from enum import StrEnum
from pathlib import Path
from typing import Annotated, Optional

from pydantic import BaseModel, Field, SecretStr, model_validator

from formidant import BoundForm, Jinja2Engine, Meta, bind
from tests.utils import FakeMultidict


class Color(StrEnum):
    RED = "red"
    BLUE = "blue"


class Address(BaseModel):
    city: str


class Item(BaseModel):
    sku: str


class Wide(BaseModel):
    name: str = Field(max_length=40)
    age: Optional[int] = None
    color: Color = Color.RED
    tags: list[Color] = []
    subscribed: bool = False
    password: SecretStr = SecretStr("keep")
    address: Address = Address(city="Oslo")
    items: list[Item] = []

    @model_validator(mode="after")
    def not_bob(self) -> "Wide":
        if self.name == "bob":
            raise ValueError("no bobs")
        return self


def field_block(html: str, input_name: str) -> str:
    blocks = html.split('<div class="fd-field')
    for block in blocks[1:]:
        if f'name="{input_name}"' in block:
            return block
    raise AssertionError(f"no field block for {input_name}")


def test_unbound_render_shows_defaults() -> None:
    html = BoundForm.unbound(Wide).render()
    assert '<option value="red" selected>' in html
    assert 'name="name"' in html
    assert 'maxlength="40"' in html


def test_unbound_render_from_instance_populates_values() -> None:
    instance = Wide(name="Ada", age=7, color=Color.BLUE, subscribed=True)
    html = BoundForm.unbound(Wide, instance).render()
    assert 'value="Ada"' in html
    assert 'value="7"' in html
    assert '<option value="blue" selected>' in html
    assert "checked" in field_block(html, "subscribed")


def test_bound_rerender_shows_raw_invalid_input() -> None:
    form = bind(Wide, FakeMultidict([("name", "Ada"), ("age", "abc")]))
    html = form.render()
    assert 'value="abc"' in html


def test_field_errors_render_adjacent() -> None:
    form = bind(Wide, FakeMultidict([("name", "Ada"), ("age", "abc")]))
    block = field_block(form.render(), "age")
    assert "fd-invalid" in form.render()
    assert '<p class="fd-error">' in block


def test_model_errors_render_at_form_level() -> None:
    form = bind(Wide, FakeMultidict([("name", "bob")]))
    html = form.render()
    assert '<ul class="fd-form-errors">' in html
    assert "no bobs" in html


def test_nested_list_error_targets_row() -> None:
    class Line(BaseModel):
        qty: int

    class Order(BaseModel):
        items: list[Line] = []

    form = bind(Order, FakeMultidict([("items[0][qty]", "3"), ("items[1][qty]", "x")]))
    html = form.render()
    assert '<p class="fd-error">' in field_block(html, "items[1][qty]")
    assert '<p class="fd-error">' not in field_block(html, "items[0][qty]")


def test_required_attr_renders() -> None:
    class M(BaseModel):
        name: str
        age: Optional[int] = None

    html = BoundForm.unbound(M).render()
    assert "required" in field_block(html, "name")
    assert "required" not in field_block(html, "age")


def test_checkbox_bound_state() -> None:
    checked = bind(Wide, FakeMultidict([("name", "Ada"), ("subscribed", "on")]))
    unchecked = bind(Wide, FakeMultidict([("name", "Ada")]))
    assert "checked" in field_block(checked.render(), "subscribed")
    assert "checked" not in field_block(unchecked.render(), "subscribed")


def test_checkbox_group_selected_state() -> None:
    instance = Wide(name="Ada", tags=[Color.BLUE])
    html = BoundForm.unbound(Wide, instance).render()
    block = field_block(html, "tags")
    assert 'value="blue" checked' in block
    assert 'value="red" checked' not in block


def test_password_never_renders_value() -> None:
    form = bind(Wide, FakeMultidict([("name", "Ada"), ("password", "hunter2hunter2")]))
    assert "hunter2" not in form.render()


def test_fieldset_renders_legend_and_nested_names() -> None:
    html = BoundForm.unbound(Wide).render()
    assert "<legend>Address</legend>" in html
    assert 'name="address[city]"' in html
    assert 'value="Oslo"' in html


def test_repeat_renders_row_per_item() -> None:
    instance = Wide(name="Ada", items=[Item(sku="A1"), Item(sku="B2")])
    html = BoundForm.unbound(Wide, instance).render()
    assert html.count('<div class="fd-row">') == 2
    assert 'name="items[0][sku]"' in html
    assert 'name="items[1][sku]"' in html
    assert 'value="A1"' in html


def test_render_field_matches_full_form() -> None:
    form = BoundForm.unbound(Wide, Wide(name="Ada"))
    assert form.render_field("name") in form.render()


def test_render_field_repeat_row_partial() -> None:
    instance = Wide(name="Ada", items=[Item(sku="A1")])
    form = BoundForm.unbound(Wide, instance)
    row = form.render_field("items", index=0)
    assert row.startswith('<div class="fd-row">')
    assert row in form.render()


def test_hidden_inputs_slot_renders_verbatim() -> None:
    token = '<input type="hidden" name="csrfmiddlewaretoken" value="tok">'
    html = BoundForm.unbound(Wide).render(hidden_inputs=token)
    assert token in html


def test_hostile_values_escaped() -> None:
    form = bind(
        Wide, FakeMultidict([("name", '<script>alert(1)</script>" onmouseover="pwn')])
    )
    html = form.render()
    assert "<script>" not in html
    assert 'onmouseover="pwn"' not in html
    assert "&lt;script&gt;" in html


def test_hostile_error_messages_escaped() -> None:
    class M(BaseModel):
        name: Annotated[str, Meta(messages={"string_too_short": "<b>bad</b>"})] = Field(
            min_length=5
        )

    form = bind(M, FakeMultidict([("name", "x")]))
    assert "<b>bad</b>" not in form.render()
    assert "&lt;b&gt;bad&lt;/b&gt;" in form.render()


def test_user_template_overrides(tmp_path: Path) -> None:
    (tmp_path / "widgets").mkdir()
    (tmp_path / "widgets" / "input.html").write_text("WIDGET-OVERRIDE {{ name }}")
    engine = Jinja2Engine([tmp_path])
    html = BoundForm.unbound(Wide).render(engine=engine)
    assert "WIDGET-OVERRIDE name" in html
    assert "<select" in html


def test_user_form_template_override(tmp_path: Path) -> None:
    (tmp_path / "form.html").write_text("FORM-OVERRIDE {{ fields | length }}")
    engine = Jinja2Engine([tmp_path])
    html = BoundForm.unbound(Wide).render(engine=engine)
    assert html.startswith("FORM-OVERRIDE")


def test_user_field_template_override(tmp_path: Path) -> None:
    (tmp_path / "field.html").write_text("<p>F:{{ label }}</p>")
    engine = Jinja2Engine([tmp_path])
    html = BoundForm.unbound(Wide).render(engine=engine)
    assert "<p>F:Name</p>" in html
