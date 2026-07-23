from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from pydantic import BaseModel, Field

from formidant import BoundForm
from formidant.core.rendering import render_field
from formidant.django import bind, bind_view


class Item(BaseModel):
    sku: str
    qty: int = Field(ge=1)


class Order(BaseModel):
    customer: str
    items: list[Item] = []


SAMPLE = Order(customer="Ada", items=[Item(sku="A1", qty=2), Item(sku="B2", qty=5)])


def order_editor(request: HttpRequest) -> HttpResponse:
    form = bind(Order, request)
    if not form.bound:
        form = BoundForm.unbound(Order, SAMPLE)
    return render(request, "orders.html", {"form": form, "saved": form.valid})


@bind_view
def order_row(request: HttpRequest, index: int) -> HttpResponse:
    return HttpResponse(render_field(BoundForm.unbound(Order), "items", index=index))


def order_row_remove(request: HttpRequest) -> HttpResponse:
    return HttpResponse("")
