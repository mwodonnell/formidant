from typing import Annotated

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from pydantic import BaseModel, EmailStr, SecretStr, field_validator

from formidant import Meta
from formidant.django import form_view

MIN_PASSWORD_LENGTH = 12


class SignupForm(BaseModel):
    email: EmailStr
    display_name: Annotated[
        str, Meta(label="Display name", placeholder="How you'll appear")
    ]
    password: SecretStr
    accept_tos: Annotated[bool, Meta(label="I accept the terms of service")]

    @field_validator("password")
    @classmethod
    def password_min_length(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
            )
        return value


@form_view(template="signup.html")
def signup(request: HttpRequest, form: SignupForm) -> HttpResponse:
    return redirect("welcome")


def welcome(request: HttpRequest) -> HttpResponse:
    return render(request, "welcome.html")
