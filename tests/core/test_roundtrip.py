from datetime import date
from decimal import Decimal
from enum import StrEnum

from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import BaseModel

from formidant import BoundForm, bind
from tests.utils import FakeMultidict, harvest_form_values


class Color(StrEnum):
    RED = "red"
    BLUE = "blue"
    GREEN = "green"


class Child(BaseModel):
    label: str
    qty: int


class Round(BaseModel):
    text: str
    num: int
    ratio: float
    price: Decimal
    flag: bool
    day: date
    color: Color
    maybe: int | None = None
    child: Child
    items: list[Child] = []
    tags: list[Color] = []


safe_text = st.text(st.characters(blacklist_categories=("Cs", "Cc")), max_size=40)
children = st.builds(Child, label=safe_text, qty=st.integers())
instances = st.builds(
    Round,
    text=safe_text,
    num=st.integers(),
    ratio=st.floats(allow_nan=False, allow_infinity=False),
    price=st.decimals(min_value=-(10**6), max_value=10**6, places=2),
    flag=st.booleans(),
    day=st.dates(),
    color=st.sampled_from(Color),
    maybe=st.none() | st.integers(),
    child=children,
    items=st.lists(children, max_size=3),
    tags=st.lists(st.sampled_from(Color), unique=True).map(
        lambda colors: sorted(colors, key=list(Color).index)
    ),
)


@given(instance=instances)
@settings(deadline=None)
def test_render_submit_rebind_roundtrips(instance: Round) -> None:
    html = BoundForm.unbound(Round, instance).render()
    submitted = harvest_form_values(html)
    rebound = bind(Round, FakeMultidict(submitted))
    assert rebound.valid, rebound.errors
    assert rebound.instance == instance
