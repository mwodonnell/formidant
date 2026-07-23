import ast
from pathlib import Path

import pytest
from django.test import Client
from django.test.utils import override_settings

VALID_SIGNUP = {
    "email": "ada@example.com",
    "display_name": "Ada",
    "password": "long-enough-password",
    "accept_tos": "on",
}

pytestmark = pytest.mark.usefixtures("demo_urlconf")


@pytest.fixture
def demo_urlconf():
    with override_settings(ROOT_URLCONF="demo.urls"):
        yield


@pytest.fixture
def client() -> Client:
    return Client()


def test_signup_get_renders_form(client: Client) -> None:
    response = client.get("/")
    body = response.content.decode()
    assert response.status_code == 200
    assert 'name="csrfmiddlewaretoken"' in body
    assert 'type="email"' in body and 'name="email"' in body
    assert 'placeholder="How you' in body


def test_signup_invalid_post_rerenders_with_errors(client: Client) -> None:
    response = client.post(
        "/", {**VALID_SIGNUP, "email": "not-an-email", "password": "short"}
    )
    body = response.content.decode()
    assert response.status_code == 200
    assert "fd-error" in body
    assert "at least 12 characters" in body
    assert 'value="not-an-email"' in body


def test_signup_valid_post_redirects_to_welcome(client: Client) -> None:
    response = client.post("/", VALID_SIGNUP)
    assert response.status_code == 302
    assert response.headers["Location"] == "/welcome/"


def test_order_page_renders_existing_rows(client: Client) -> None:
    body = client.get("/orders/").content.decode()
    assert 'name="items[0][sku]"' in body and 'value="A1"' in body
    assert 'name="items[1][sku]"' in body and 'value="B2"' in body


def test_order_row_endpoint_returns_indexed_partial(client: Client) -> None:
    body = client.get("/orders/row/", {"index": 2}).content.decode()
    assert body.count("fd-row") == 1
    assert 'name="items[2][sku]"' in body
    assert 'name="items[2][qty]"' in body


def test_order_row_remove_returns_empty(client: Client) -> None:
    response = client.get("/orders/row/remove/")
    assert response.status_code == 200
    assert response.content == b""


def test_signup_module_fits_line_budget() -> None:
    source = (Path(__file__).parents[2] / "demo" / "signup.py").read_text()
    tree = ast.parse(source)
    import_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            import_lines.update(
                range(node.lineno, (node.end_lineno or node.lineno) + 1)
            )
    counted = [
        number
        for number, line in enumerate(source.splitlines(), start=1)
        if line.strip() and number not in import_lines
    ]
    assert len(counted) <= 25, f"D1 budget exceeded: {len(counted)} lines"
