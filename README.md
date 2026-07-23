# formidant

Pydantic-powered web forms: binding, bound-form lifecycle, and server-side HTML rendering.
Django-first with a framework-agnostic core.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Coverage Status](https://coveralls.io/repos/github/mwodonnell/formidant/badge.svg?branch=main)](https://coveralls.io/github/mwodonnell/formidant?branch=main)

## Why formidant?

Pydantic validation is the best in the Python ecosystem, but nothing pairs it with the part
Django Forms actually got right: the bound-form lifecycle, where an invalid submission
re-renders with the user's raw input and per-field errors in place. formidant fills that gap -
one plain pydantic model gives you binding from form-encoded data (bracket-notation nesting
and lists of nested models included), validation, minimal server-rendered HTML, and htmx-ready
partials. The same model keeps working everywhere else pydantic goes, django-ninja included.

## Quick Start

Define a schema - plain pydantic, presentation via `Annotated` metadata:

```python
from typing import Annotated

from pydantic import BaseModel, EmailStr, SecretStr

from formidant import Meta
from formidant.django import form_view


class SignupForm(BaseModel):
    email: EmailStr
    display_name: Annotated[str, Meta(label="Display name", placeholder="How you'll appear")]
    password: SecretStr
    accept_tos: Annotated[bool, Meta(label="I accept the terms of service")]


@form_view(template="signup.html")
def signup(request, form: SignupForm):
    create_account(form)  # body only runs on a valid POST
    return redirect("welcome")
```

The template renders the whole form, CSRF included:

```django
{% load formidant %}
<form method="post">
  {% formidant form %}
  <button>Sign up</button>
</form>
```

GET renders the blank form. An invalid POST re-renders it with the user's input preserved and
errors next to their fields. A valid POST is the only way into the view body, which receives
the typed `SignupForm` instance. Prefer manual control? Annotate `form: Bound[SignupForm]`
and the body always runs with the bound form, or drop to `form = bind(SignupForm, request)`.

### Multi-source binding

Path, query, and form parameters co-declared in one plain Django view:

```python
from formidant import Form
from formidant.django import bind_view


@bind_view
def update_item(request, item_id: int, q: str, item: Form[Item]):
    ...
```

`item_id` binds from the URLconf, `q` from the query string, `item` from the submitted form.

### Setup

Install `formidant` (pydantic and jinja2 are its only dependencies), then add the adapter to
`INSTALLED_APPS` for template-tag discovery:

```python
INSTALLED_APPS = [..., "formidant.django"]
```

## Demo

A runnable demo project (signup flow plus an htmx list-of-nested-models editor) lives in
[`demo/`](demo/):

```bash
uv run --extra test python demo/manage.py runserver
```

## Design

The full design doc - acceptance criteria, test design, decisions, and ticket history - is at
[`docs/design/formidant.md`](docs/design/formidant.md).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
