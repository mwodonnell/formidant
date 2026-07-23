import pytest

from formidant.core.flatten import InflateResult, inflate, path_to_name
from tests.utils import FakeMultidict


def inflate_pairs(
    pairs: list[tuple[str, str]], list_paths: frozenset = frozenset()
) -> InflateResult:
    return inflate(FakeMultidict(pairs), list_paths)


def test_flat_keys() -> None:
    result = inflate_pairs([("name", "Ada"), ("age", "36")])
    assert result.data == {"name": "Ada", "age": "36"}
    assert result.errors == []


def test_nested_model_keys() -> None:
    result = inflate_pairs(
        [("name", "Ada"), ("address[city]", "Oslo"), ("address[zip]", "0150")]
    )
    assert result.data == {"name": "Ada", "address": {"city": "Oslo", "zip": "0150"}}


def test_list_of_models_via_indices() -> None:
    result = inflate_pairs(
        [
            ("items[0][sku]", "A1"),
            ("items[0][qty]", "2"),
            ("items[1][sku]", "B2"),
            ("items[1][qty]", "5"),
        ]
    )
    assert result.data == {
        "items": [{"sku": "A1", "qty": "2"}, {"sku": "B2", "qty": "5"}]
    }


def test_deep_mixed_nesting() -> None:
    result = inflate_pairs([("a[b][0][c]", "x")])
    assert result.data == {"a": {"b": [{"c": "x"}]}}


def test_scalar_list_via_repeated_keys() -> None:
    result = inflate_pairs([("tags", "red"), ("tags", "blue")], frozenset({("tags",)}))
    assert result.data == {"tags": ["red", "blue"]}


def test_scalar_list_single_value_stays_list() -> None:
    result = inflate_pairs([("tags", "red")], frozenset({("tags",)}))
    assert result.data == {"tags": ["red"]}


def test_list_path_matches_through_numeric_segments() -> None:
    result = inflate_pairs(
        [
            ("items[0][tags]", "red"),
            ("items[0][tags]", "blue"),
            ("items[0][sku]", "A1"),
        ],
        frozenset({("items", "tags")}),
    )
    assert result.data == {"items": [{"tags": ["red", "blue"], "sku": "A1"}]}


def test_duplicate_scalar_key_last_wins() -> None:
    result = inflate_pairs([("name", "first"), ("name", "second")])
    assert result.data == {"name": "second"}
    assert result.errors == []


def test_depth_cap_is_error() -> None:
    result = inflate_pairs([("a[b][c][d][e][f]", "x")])
    assert result.data == {}
    assert [e.message for e in result.errors] == ["nesting exceeds maximum depth of 5"]
    assert result.errors[0].input_name == "a[b][c][d][e][f]"


@pytest.mark.parametrize(
    "key",
    ["a[", "a[]", "a]b", "a[b]c", "a[[b]]", "[b]", ""],
)
def test_malformed_brackets_are_errors(key: str) -> None:
    result = inflate_pairs([(key, "x")])
    assert result.data == {}
    assert [e.message for e in result.errors] == ["malformed bracket syntax"]


def test_index_gap_is_error() -> None:
    result = inflate_pairs([("items[0][sku]", "A1"), ("items[2][sku]", "C3")])
    assert [e.message for e in result.errors] == [
        "list indexes must be contiguous from 0"
    ]
    assert result.errors[0].input_name == "items"
    assert result.data == {"items": [{"sku": "A1"}, {"sku": "C3"}]}


def test_scalar_then_container_conflict() -> None:
    result = inflate_pairs([("a", "1"), ("a[b]", "2")])
    assert result.data == {"a": "1"}
    assert [e.message for e in result.errors] == ["conflicting structure"]
    assert result.errors[0].input_name == "a[b]"


def test_container_then_scalar_conflict() -> None:
    result = inflate_pairs([("a[b]", "1"), ("a", "2")])
    assert result.data == {"a": {"b": "1"}}
    assert [e.message for e in result.errors] == ["conflicting structure"]


def test_dict_then_list_conflict() -> None:
    result = inflate_pairs([("a[b]", "1"), ("a[0]", "2")])
    assert [e.message for e in result.errors] == ["conflicting structure"]


def test_empty_input() -> None:
    result = inflate_pairs([])
    assert result.data == {}
    assert result.errors == []


def test_insertion_order_preserved() -> None:
    result = inflate_pairs([("b", "1"), ("a", "2")])
    assert list(result.data.keys()) == ["b", "a"]


def test_path_to_name() -> None:
    assert path_to_name(("items", 0, "qty")) == "items[0][qty]"
    assert path_to_name(("name",)) == "name"
