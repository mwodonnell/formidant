from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from pydantic import BaseModel, field_validator

from formidant import UploadedFile
from formidant.django import DjangoFormData, bind


class Profile(BaseModel):
    name: str
    age: int


class Doc(BaseModel):
    title: str
    attachment: UploadedFile


def test_get_yields_unbound_form(rf: RequestFactory) -> None:
    form = bind(Profile, rf.get("/signup"))
    assert not form.bound
    assert not form.valid
    assert form.errors == {}


def test_valid_post_binds(rf: RequestFactory) -> None:
    form = bind(Profile, rf.post("/signup", {"name": "Ada", "age": "36"}))
    assert form.valid
    assert form.instance == Profile(name="Ada", age=36)


def test_invalid_post_binds_with_errors(rf: RequestFactory) -> None:
    form = bind(Profile, rf.post("/signup", {"name": "Ada", "age": "x"}))
    assert form.bound
    assert not form.valid
    assert list(form.errors.keys()) == ["age"]
    assert form.raw["age"] == ["x"]


def test_django_uploaded_file_conforms_to_core_protocol() -> None:
    upload = SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain")
    assert isinstance(upload, UploadedFile)


def test_file_upload_binds_end_to_end(rf: RequestFactory) -> None:
    upload = SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain")
    form = bind(Doc, rf.post("/docs", {"title": "hi", "attachment": upload}))
    assert form.valid, form.errors
    assert form.instance.attachment.read() == b"hello"
    assert form.instance.attachment.content_type == "text/plain"


def test_validation_context_carries_request(rf: RequestFactory) -> None:
    seen: dict[str, object] = {}

    class M(BaseModel):
        name: str

        @field_validator("name")
        @classmethod
        def grab(cls, value: str, info) -> str:
            seen["request"] = info.context["request"]
            return value

    request = rf.post("/x", {"name": "Ada"})
    bind(M, request)
    assert seen["request"] is request


def test_form_data_wraps_post_and_files(rf: RequestFactory) -> None:
    request = rf.post("/x", {"tags": ["a", "b"]})
    data = DjangoFormData(request)
    assert list(data.keys()) == ["tags"]
    assert data.getlist("tags") == ["a", "b"]
    assert data.files == {}
