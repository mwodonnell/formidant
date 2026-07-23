from datetime import date
from decimal import Decimal
from typing import Optional

import pytest
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

from formidant.core.binding import bind_data, list_paths_for
from formidant.core.constants import NON_FIELD_KEY
from formidant.core.form_types import BindResult
from tests.utils import FakeMultidict


def bind_pairs(model: type[BaseModel], pairs: list[tuple[str, str]]) -> BindResult:
    return bind_data(model, FakeMultidict(pairs))


class Profile(BaseModel):
    name: str = Field(max_length=10)
    age: int
    height: float = 1.80
    born: date | None = None


class Item(BaseModel):
    sku: str
    qty: int


class Order(BaseModel):
    customer: str
    items: list[Item] = []

    @model_validator(mode="after")
    def has_items(self) -> "Order":
        if not self.items:
            raise ValueError("order needs at least one item")
        return self


def test_vanilla_model_binds_with_coercion_and_defaults() -> None:
    result = bind_pairs(
        Profile, [("name", "Ada"), ("age", "36"), ("born", "1990-01-02")]
    )
    assert result.valid
    assert result.instance == Profile(
        name="Ada", age=36, height=1.80, born=date(1990, 1, 2)
    )


def test_constraint_violation_is_field_error() -> None:
    result = bind_pairs(Profile, [("name", "far-too-long-name"), ("age", "36")])
    assert not result.valid
    assert result.instance is None
    assert list(result.errors.keys()) == ["name"]


def test_coercion_failure_keys_on_input_name() -> None:
    result = bind_pairs(
        Order, [("customer", "Ada"), ("items[0][sku]", "A1"), ("items[0][qty]", "x")]
    )
    assert not result.valid
    assert list(result.errors.keys()) == ["items[0][qty]"]


def test_model_validator_error_keys_on_non_field_key() -> None:
    result = bind_pairs(Order, [("customer", "Ada")])
    assert not result.valid
    assert NON_FIELD_KEY in result.errors


def test_missing_required_field_is_field_error() -> None:
    result = bind_pairs(Profile, [("name", "Ada")])
    assert list(result.errors.keys()) == ["age"]


def test_repeated_keys_bind_list_without_manual_list_paths() -> None:
    class Post(BaseModel):
        title: str
        tags: list[str]

    result = bind_pairs(Post, [("title", "hi"), ("tags", "red"), ("tags", "blue")])
    assert result.valid
    assert result.instance.tags == ["red", "blue"]


def test_single_value_binds_single_item_list() -> None:
    class Post(BaseModel):
        tags: list[str]

    result = bind_pairs(Post, [("tags", "red")])
    assert result.valid
    assert result.instance.tags == ["red"]


def test_raw_preserves_submitted_values() -> None:
    result = bind_pairs(Profile, [("name", "Ada"), ("age", "not-a-number")])
    assert not result.valid
    assert result.raw == {"name": ["Ada"], "age": ["not-a-number"]}


def test_structural_errors_merge_with_validation_errors() -> None:
    result = bind_pairs(Profile, [("name", "Ada"), ("age[", "1")])
    assert not result.valid
    assert result.errors["age["] == ["malformed bracket syntax"]
    assert "age" in result.errors


def test_validation_context_reaches_validators() -> None:
    seen: dict[str, object] = {}

    class M(BaseModel):
        name: str

        @field_validator("name")
        @classmethod
        def grab(cls, value: str, info) -> str:
            seen["ctx"] = info.context
            return value

    bind_data(M, FakeMultidict([("name", "x")]), context={"request": "sentinel"})
    assert seen["ctx"] == {"request": "sentinel"}


class Quirks(BaseModel):
    accept: bool
    subscribed: bool = True
    nickname: str = ""
    age: Optional[int] = None
    height: float = 1.5
    score: Decimal = Decimal("1")
    password: SecretStr = SecretStr("keep")


@pytest.mark.parametrize(
    ("pairs", "attribute", "expected"),
    [
        ([], "accept", False),
        ([("accept", "on")], "accept", True),
        ([], "subscribed", False),
        ([("nickname", "")], "nickname", ""),
        ([("age", "")], "age", None),
        ([("height", "")], "height", 1.5),
        ([("score", "")], "score", Decimal("1")),
        ([("password", "")], "password", SecretStr("keep")),
    ],
)
def test_quirk_normalization(
    pairs: list[tuple[str, str]], attribute: str, expected: object
) -> None:
    result = bind_pairs(Quirks, pairs)
    assert result.valid, result.errors
    assert getattr(result.instance, attribute) == expected


def test_empty_string_on_required_non_str_field_is_missing_error() -> None:
    class M(BaseModel):
        age: int

    result = bind_pairs(M, [("age", "")])
    assert not result.valid
    assert list(result.errors.keys()) == ["age"]


def test_quirks_normalize_inside_nested_models() -> None:
    class Inner(BaseModel):
        flag: bool
        note: Optional[int] = None

    class Outer(BaseModel):
        inner: Inner
        entries: list[Inner]

    result = bind_pairs(
        Outer,
        [("inner[note]", ""), ("entries[0][note]", "7"), ("entries[1][note]", "")],
    )
    assert result.valid, result.errors
    assert result.instance.inner == Inner(flag=False, note=None)
    assert result.instance.entries == [
        Inner(flag=False, note=7),
        Inner(flag=False, note=None),
    ]


def test_file_field_binds_from_formdata_files() -> None:
    from formidant.core.files import UploadedFile
    from tests.utils import FakeFormData, FakeUpload

    class Doc(BaseModel):
        title: str
        attachment: UploadedFile

    upload = FakeUpload("notes.txt", b"hello", "text/plain")
    result = bind_data(Doc, FakeFormData([("title", "hi")], {"attachment": upload}))
    assert result.valid, result.errors
    assert result.instance.attachment is upload
    assert result.instance.attachment.read() == b"hello"


def test_missing_file_field_is_field_error() -> None:
    from formidant.core.files import UploadedFile
    from tests.utils import FakeFormData

    class Doc(BaseModel):
        attachment: UploadedFile

    result = bind_data(Doc, FakeFormData([]))
    assert not result.valid
    assert list(result.errors.keys()) == ["attachment"]


def test_list_paths_for_walks_the_model_tree() -> None:
    class Inner(BaseModel):
        tags: list[str]

    class Outer(BaseModel):
        names: list[str]
        counts: set[int]
        inner: Inner
        entries: list[Inner]
        single: str

    assert list_paths_for(Outer) == frozenset(
        {("names",), ("counts",), ("inner", "tags"), ("entries", "tags")}
    )
