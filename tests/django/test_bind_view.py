from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory
from pydantic import BaseModel

from formidant import Form
from formidant.django import bind_view


class Item(BaseModel):
    sku: str
    qty: int


@bind_view
def update_item(
    request: HttpRequest, item_id: int, q: str = "", item: Form[Item] = None
) -> HttpResponse:
    return HttpResponse(f"{item_id}|{q}|{item.sku}|{item.qty}")


def test_path_query_form_bind_together(rf: RequestFactory) -> None:
    request = rf.post("/items/7?q=hello", {"sku": "A1", "qty": "2"})
    response = update_item(request, item_id="7")
    assert response.status_code == 200
    assert response.content == b"7|hello|A1|2"


def test_query_default_respected(rf: RequestFactory) -> None:
    request = rf.post("/items/7", {"sku": "A1", "qty": "2"})
    response = update_item(request, item_id="7")
    assert response.content == b"7||A1|2"


def test_path_coercion_failure_is_prefixed_400(rf: RequestFactory) -> None:
    request = rf.post("/items/x", {"sku": "A1", "qty": "2"})
    response = update_item(request, item_id="x")
    assert response.status_code == 400
    assert b"path: item_id:" in response.content


def test_query_coercion_failure_is_prefixed_400(rf: RequestFactory) -> None:
    @bind_view
    def search(request: HttpRequest, limit: int) -> HttpResponse:
        return HttpResponse(str(limit))

    response = search(rf.get("/search?limit=ten"))
    assert response.status_code == 400
    assert b"query: limit:" in response.content


def test_missing_required_query_is_400(rf: RequestFactory) -> None:
    @bind_view
    def search(request: HttpRequest, limit: int) -> HttpResponse:
        return HttpResponse(str(limit))

    response = search(rf.get("/search"))
    assert response.status_code == 400
    assert b"query: limit: Field required" in response.content


def test_form_errors_are_prefixed_400(rf: RequestFactory) -> None:
    request = rf.post("/items/7", {"sku": "A1", "qty": "x"})
    response = update_item(request, item_id="7")
    assert response.status_code == 400
    assert b"form: qty:" in response.content


def test_get_with_form_param_is_400(rf: RequestFactory) -> None:
    response = update_item(rf.get("/items/7"), item_id="7")
    assert response.status_code == 400
    assert b"form: item: No submitted form data" in response.content


def test_on_invalid_override_wins(rf: RequestFactory) -> None:
    def teapot(request: HttpRequest, errors: dict[str, list[str]]) -> HttpResponse:
        return HttpResponse("nope", status=418)

    @bind_view(on_invalid=teapot)
    def search(request: HttpRequest, limit: int) -> HttpResponse:
        return HttpResponse(str(limit))

    response = search(rf.get("/search"))
    assert response.status_code == 418
    assert response.content == b"nope"


def test_form_param_alone(rf: RequestFactory) -> None:
    @bind_view
    def create(request: HttpRequest, item: Form[Item]) -> HttpResponse:
        return HttpResponse(item.sku)

    response = create(rf.post("/items", {"sku": "B2", "qty": "1"}))
    assert response.content == b"B2"
