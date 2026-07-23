import pytest
from django.test import Client
from django.test.utils import override_settings
from pydantic import BaseModel, ConfigDict

from formidant import bind
from tests.utils import FakeMultidict

pytestmark = pytest.mark.usefixtures("demo_urlconf")


@pytest.fixture
def demo_urlconf():
    with override_settings(ROOT_URLCONF="demo.urls"):
        yield


def test_extra_keys_are_ignored_not_bound() -> None:
    class Profile(BaseModel):
        name: str

    form = bind(Profile, FakeMultidict([("name", "Ada"), ("is_admin", "true")]))
    assert form.valid
    assert not hasattr(form.instance, "is_admin")


def test_extra_forbid_is_form_error_not_exception() -> None:
    class Strict(BaseModel):
        model_config = ConfigDict(extra="forbid")
        name: str

    form = bind(Strict, FakeMultidict([("name", "Ada"), ("is_admin", "true")]))
    assert not form.valid
    assert "is_admin" in form.errors


def test_hostile_input_escaped_through_full_stack() -> None:
    payload = {
        "email": '"><script>alert(1)</script>',
        "display_name": "<img src=x onerror=alert(1)>",
        "password": "short",
        "accept_tos": "on",
    }
    body = Client().post("/", payload).content.decode()
    assert "<script>alert(1)</script>" not in body
    assert "<img src=x" not in body
    assert "&lt;script&gt;" in body or "&lt;img" in body
