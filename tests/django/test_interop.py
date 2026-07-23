from ninja import NinjaAPI
from ninja.testing import TestClient

from demo.signup import SignupForm


def make_client() -> TestClient:
    api = NinjaAPI()

    @api.post("/signup")
    def create(request, payload: SignupForm) -> dict[str, str]:
        return {"email": payload.email, "display_name": payload.display_name}

    return TestClient(api)


def test_same_schema_works_as_ninja_json_body() -> None:
    response = make_client().post(
        "/signup",
        json={
            "email": "ada@example.com",
            "display_name": "Ada",
            "password": "long-enough-password",
            "accept_tos": True,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"email": "ada@example.com", "display_name": "Ada"}


def test_ninja_rejects_invalid_body_with_422() -> None:
    response = make_client().post(
        "/signup",
        json={
            "email": "nope",
            "display_name": "Ada",
            "password": "x",
            "accept_tos": True,
        },
    )
    assert response.status_code == 422


def test_json_schema_emits_cleanly() -> None:
    schema = SignupForm.model_json_schema()
    assert set(schema["properties"]) == {
        "email",
        "display_name",
        "password",
        "accept_tos",
    }
    assert schema["properties"]["email"]["format"] == "email"
