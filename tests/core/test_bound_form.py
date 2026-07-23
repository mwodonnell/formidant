import pytest
from pydantic import BaseModel

from formidant import BoundForm, InvalidFormAccessError, bind
from tests.utils import FakeMultidict


class Profile(BaseModel):
    name: str = "anon"
    age: int


def test_valid_submission_exposes_typed_instance() -> None:
    form = bind(Profile, FakeMultidict([("name", "Ada"), ("age", "36")]))
    assert form.bound
    assert form.valid
    assert form.errors == {}
    assert form.instance == Profile(name="Ada", age=36)


def test_invalid_submission_exposes_errors_not_exceptions() -> None:
    form = bind(Profile, FakeMultidict([("age", "not-a-number")]))
    assert form.bound
    assert not form.valid
    assert list(form.errors.keys()) == ["age"]


def test_instance_access_on_invalid_form_raises() -> None:
    form = bind(Profile, FakeMultidict([]))
    with pytest.raises(InvalidFormAccessError, match="Profile form is not valid"):
        form.instance


def test_raw_survives_failed_coercion() -> None:
    form = bind(Profile, FakeMultidict([("age", "abc")]))
    assert form.raw == {"age": ["abc"]}


def test_unbound_from_class() -> None:
    form = BoundForm.unbound(Profile)
    assert not form.bound
    assert not form.valid
    assert form.errors == {}
    assert form.raw == {}
    assert form.initial is None


def test_unbound_from_instance_for_edit_pages() -> None:
    existing = Profile(name="Ada", age=36)
    form = BoundForm.unbound(Profile, existing)
    assert not form.bound
    assert not form.valid
    assert form.initial is existing
    with pytest.raises(InvalidFormAccessError):
        form.instance
