from django import template
from django.http import HttpRequest
from django.middleware.csrf import get_token
from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe

from formidant.core.bound import BoundForm

register = template.Library()


@register.simple_tag(takes_context=True)
def formidant(context: template.Context, form: BoundForm) -> SafeString:
    """Render the full form, CSRF hidden input included."""
    request = context.get("request")
    hidden = _csrf_input(request) if request is not None else ""
    return mark_safe(form.render(hidden_inputs=hidden))  # noqa: S308


@register.simple_tag
def formidant_field(form: BoundForm, name: str, index: int | None = None) -> SafeString:
    """Render one field (or one repeat row, with index) in isolation."""
    return mark_safe(form.render_field(name, index=index))  # noqa: S308


def _csrf_input(request: HttpRequest) -> str:
    return format_html(
        '<input type="hidden" name="csrfmiddlewaretoken" value="{}">',
        get_token(request),
    )
