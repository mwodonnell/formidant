from typing import Annotated

import pytest
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.test import RequestFactory
from pydantic import BaseModel, Field

from formidant import Bound, BoundForm, Meta
from formidant.django import form_view


class Signup(BaseModel):
    email: Annotated[str, Meta(label="Email")] = Field(min_length=3)
    name: str = "anon"


@form_view(template="test_form.html")
def signup(request: HttpRequest, form: Signup) -> HttpResponse:
    return redirect(f"/welcome/{form.email}")


def test_get_renders_unbound(rf: RequestFactory) -> None:
    response = signup(rf.get("/signup"))
    body = response.content.decode()
    assert response.status_code == 200
    assert "id_email" in body
    assert "fd-invalid" not in body


def test_invalid_post_rerenders_with_errors_and_raw(rf: RequestFactory) -> None:
    response = signup(rf.post("/signup", {"email": "ab", "name": "Ada"}))
    body = response.content.decode()
    assert response.status_code == 200
    assert "at least 3 characters" in body
    assert "ab" in body
    assert "Ada" in body


def test_valid_post_enters_body_and_response_passes_through(rf: RequestFactory) -> None:
    response = signup(rf.post("/signup", {"email": "ada@example.com"}))
    assert response.status_code == 302
    assert response.url == "/welcome/ada@example.com"


def test_on_invalid_response_wins(rf: RequestFactory) -> None:
    def teapot(request: HttpRequest, form: BoundForm) -> HttpResponse:
        return HttpResponse(status=418)

    @form_view(template="test_form.html", on_invalid=teapot)
    def view(request: HttpRequest, form: Signup) -> HttpResponse:
        return HttpResponse("ok")

    assert view(rf.post("/x", {"email": "ab"})).status_code == 418


def test_on_invalid_none_defers_to_rerender(rf: RequestFactory) -> None:
    seen: list[BoundForm] = []

    def observer(request: HttpRequest, form: BoundForm) -> None:
        seen.append(form)

    @form_view(template="test_form.html", on_invalid=observer)
    def view(request: HttpRequest, form: Signup) -> HttpResponse:
        return HttpResponse("ok")

    response = view(rf.post("/x", {"email": "ab"}))
    assert response.status_code == 200
    assert len(seen) == 1
    assert not seen[0].valid


def test_on_invalid_does_not_fire_on_get(rf: RequestFactory) -> None:
    def boom(request: HttpRequest, form: BoundForm) -> HttpResponse:
        raise AssertionError("on_invalid fired for GET")

    @form_view(template="test_form.html", on_invalid=boom)
    def view(request: HttpRequest, form: Signup) -> HttpResponse:
        return HttpResponse("ok")

    assert view(rf.get("/x")).status_code == 200


def test_bound_annotation_always_enters_body(rf: RequestFactory) -> None:
    @form_view(template="test_form.html")
    def view(request: HttpRequest, form: Bound[Signup]) -> HttpResponse:
        return HttpResponse(f"valid={form.valid}")

    assert view(rf.post("/x", {"email": "ab"})).content == b"valid=False"
    assert view(rf.post("/x", {"email": "ada@x.io"})).content == b"valid=True"


def test_view_without_form_parameter_fails_at_decoration() -> None:
    with pytest.raises(TypeError, match="declares no form parameter"):

        @form_view(template="test_form.html")
        def view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("ok")
