from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, HttpUrl, SecretStr

from formidant import Meta, UploadedFile, bind
from formidant.core.widgets import (
    Checkbox,
    CheckboxGroup,
    FieldSpec,
    FileInput,
    Fieldset,
    Input,
    Repeat,
    Select,
    Widget,
    register_widget,
    resolve_fields,
)
from tests.utils import FakeMultidict


class Color(StrEnum):
    DARK_RED = "dark_red"
    BLUE = "blue"


class Address(BaseModel):
    city: str


class Matrix(BaseModel):
    text: str
    flag: bool
    count: int
    ratio: float
    price: Decimal
    day: date
    at: datetime
    when: time
    email: EmailStr
    secret: SecretStr
    site: HttpUrl
    ident: UUID
    color: Color
    size: Literal["s", "m", "l"]
    maybe: Optional[int] = None
    colors: list[Color] = []
    address: Address
    addresses: list[Address] = []
    upload: UploadedFile


def spec(name: str) -> FieldSpec:
    fields = {f.name: f for f in resolve_fields(Matrix)}
    return fields[name]


def test_default_widget_matrix() -> None:
    expected: dict[str, Widget] = {
        "text": Input("text"),
        "flag": Checkbox(),
        "count": Input("number"),
        "ratio": Input("number"),
        "price": Input("number"),
        "day": Input("date"),
        "at": Input("datetime-local"),
        "when": Input("time"),
        "email": Input("email"),
        "secret": Input("password"),
        "site": Input("url"),
        "ident": Input("text"),
        "color": Select(choices=(("dark_red", "Dark red"), ("blue", "Blue"))),
        "size": Select(choices=(("s", "s"), ("m", "m"), ("l", "l"))),
        "maybe": Input("number"),
        "colors": CheckboxGroup(choices=(("dark_red", "Dark red"), ("blue", "Blue"))),
        "address": Fieldset(),
        "addresses": Repeat(),
        "upload": FileInput(),
    }
    for name, widget in expected.items():
        assert spec(name).widget == widget, name


def test_nested_widgets_carry_children() -> None:
    assert [c.name for c in spec("address").children] == ["city"]
    assert [c.name for c in spec("addresses").children] == ["city"]
    assert spec("text").children == ()


def test_required_flags() -> None:
    assert spec("text").required
    assert not spec("maybe").required
    assert not spec("flag").required
    assert not spec("colors").required


def test_constraints_flow_to_attrs() -> None:
    class M(BaseModel):
        name: str = Field(max_length=40, min_length=2)
        qty: int = Field(ge=1, le=99)

    fields = {f.name: f for f in resolve_fields(M)}
    assert fields["name"].attrs == {"maxlength": "40", "minlength": "2"}
    assert fields["qty"].attrs == {"min": "1", "max": "99"}


def test_label_defaults_prettify_field_names() -> None:
    class M(BaseModel):
        display_name: str

    assert resolve_fields(M)[0].label == "Display name"


def test_meta_overrides_presentation() -> None:
    class M(BaseModel):
        name: Annotated[
            str,
            Meta(
                label="Your name",
                placeholder="e.g. Ada",
                help_text="As shown publicly",
                widget=Input("search"),
                attrs={"maxlength": "5", "data-test": "x"},
            ),
        ] = Field(max_length=40)

    resolved = resolve_fields(M)[0]
    assert resolved.label == "Your name"
    assert resolved.placeholder == "e.g. Ada"
    assert resolved.help_text == "As shown publicly"
    assert resolved.widget == Input("search")
    assert resolved.attrs["maxlength"] == "5"
    assert resolved.attrs["data-test"] == "x"


def test_meta_is_validation_inert() -> None:
    class Plain(BaseModel):
        name: str = Field(max_length=10)

    class Decorated(BaseModel):
        name: Annotated[str, Meta(label="Name", messages={"string_too_long": "x"})] = (
            Field(max_length=10)
        )

    plain_schema = Plain.model_json_schema()
    decorated_schema = Decorated.model_json_schema()
    del plain_schema["title"], decorated_schema["title"]
    assert plain_schema == decorated_schema
    assert Decorated.model_validate({"name": "ok"}).name == "ok"


def test_defaults_populate_field_spec() -> None:
    class M(BaseModel):
        name: str = "anon"
        age: int

    fields = {f.name: f for f in resolve_fields(M)}
    assert fields["name"].default == "anon"
    assert fields["age"].default is None


def test_third_party_widget_registration() -> None:
    from pathlib import PurePosixPath

    @register_widget(PurePosixPath)
    def _path_widget(annotation: object) -> Widget:
        return Input("search")

    class M(BaseModel):
        location: PurePosixPath

    assert resolve_fields(M)[0].widget == Input("search")


def test_message_override_hook() -> None:
    class M(BaseModel):
        name: Annotated[str, Meta(messages={"string_too_short": "Too short"})] = Field(
            min_length=5
        )

    form = bind(M, FakeMultidict([("name", "ab")]))
    assert form.errors == {"name": ["Too short"]}


def test_message_override_in_nested_list() -> None:
    class Item(BaseModel):
        qty: Annotated[int, Meta(messages={"int_parsing": "Whole numbers only"})]

    class Order(BaseModel):
        items: list[Item] = []

    form = bind(Order, FakeMultidict([("items[0][qty]", "x")]))
    assert form.errors == {"items[0][qty]": ["Whole numbers only"]}
