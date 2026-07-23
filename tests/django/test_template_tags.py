import re

import pytest
from django.template import Context, Template
from django.test import RequestFactory
from pydantic import BaseModel

from formidant import BoundForm
from formidant.core.rendering import render_field, render_form
from formidant.django import bind


class Profile(BaseModel):
    name: str
    age: int


def render_tag(source: str, context: dict) -> str:
    return Template("{% load formidant %}" + source).render(Context(context))


def test_formidant_tag_matches_core_render_byte_identically(
    rf: RequestFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "formidant.django.templatetags.formidant.get_token", lambda request: "fixed"
    )
    request = rf.get("/signup")
    form = BoundForm.unbound(Profile)
    tag_output = render_tag("{% formidant form %}", {"form": form, "request": request})
    hidden = '<input type="hidden" name="csrfmiddlewaretoken" value="fixed">'
    assert tag_output == render_form(form, hidden_inputs=hidden)


def test_formidant_field_tag_matches_render_field(rf: RequestFactory) -> None:
    request = rf.post("/signup", {"name": "Ada", "age": "x"})
    form = bind(Profile, request)
    tag_output = render_tag(
        '{% formidant_field form "age" %}', {"form": form, "request": request}
    )
    assert tag_output == render_field(form, "age")


def test_rendered_form_contains_csrf_token(rf: RequestFactory) -> None:
    request = rf.get("/signup")
    form = BoundForm.unbound(Profile)
    html = render_tag("{% formidant form %}", {"form": form, "request": request})
    match = re.search(
        r'<input type="hidden" name="csrfmiddlewaretoken" value="([^"]+)">', html
    )
    assert match is not None
    assert len(match.group(1)) > 30


def test_tag_without_request_renders_without_csrf(rf: RequestFactory) -> None:
    form = BoundForm.unbound(Profile)
    html = render_tag("{% formidant form %}", {"form": form})
    assert "csrfmiddlewaretoken" not in html
    assert 'name="name"' in html
