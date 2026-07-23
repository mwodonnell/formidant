import re
from collections.abc import Set
from dataclasses import dataclass, field
from typing import Any

from formidant.core.constants import BRACKET_MAX_DEPTH
from formidant.core.protocol import Multidict

PathSegment = str | int
Path = tuple[PathSegment, ...]
ListPath = tuple[str, ...]

_SEGMENT_RE = re.compile(r"\[([^\[\]]+)\]")


@dataclass(frozen=True)
class StructuralError:
    """A malformed-input problem found before validation, tied to an input name."""

    input_name: str
    message: str


@dataclass(frozen=True)
class InflateResult:
    """Nested data ready for model validation, plus any structural errors."""

    data: dict[str, Any]
    errors: list[StructuralError] = field(default_factory=list)


class _IndexDict(dict):
    pass


def path_to_name(path: Path) -> str:
    """Render a path back to its input name, e.g. ('items', 0, 'qty') -> 'items[0][qty]'."""
    head, *rest = path
    return str(head) + "".join(f"[{segment}]" for segment in rest)


def inflate(data: Multidict, list_paths: Set[ListPath] = frozenset()) -> InflateResult:
    """Turn bracket-notation multidict keys into nested data.

    `list_paths` names the fields whose values are scalar lists, as paths with
    numeric segments removed (('address', 'tags') matches 'address[tags]' and
    'items[0][tags]' alike); their values bind via getlist, everything else
    takes the last submitted value.
    """
    root: dict[str, Any] = {}
    errors: list[StructuralError] = []

    for key in data.keys():
        path = _parse_key(key)
        if path is None:
            errors.append(StructuralError(key, "malformed bracket syntax"))
            continue
        if len(path) > BRACKET_MAX_DEPTH:
            errors.append(
                StructuralError(
                    key, f"nesting exceeds maximum depth of {BRACKET_MAX_DEPTH}"
                )
            )
            continue

        values = data.getlist(key)
        value: Any = values if _is_list_path(path, list_paths) else values[-1]
        _assign(root, path, value, key, errors)

    return InflateResult(_finalize(root, (), errors), errors)


def _parse_key(key: str) -> Path | None:
    if "[" not in key:
        return (key,) if key and "]" not in key else None

    head, _, rest = key.partition("[")
    if not head or "]" in head:
        return None
    rest = "[" + rest

    segments = _SEGMENT_RE.findall(rest)
    if "".join(f"[{segment}]" for segment in segments) != rest:
        return None

    return head, *(int(s) if s.isdigit() else s for s in segments)


def _is_list_path(path: Path, list_paths: Set[ListPath]) -> bool:
    return tuple(s for s in path if isinstance(s, str)) in list_paths


def _assign(
    root: dict[str, Any],
    path: Path,
    value: Any,
    key: str,
    errors: list[StructuralError],
) -> None:
    parent: dict[Any, Any] = root
    for depth, segment in enumerate(path[:-1]):
        child_type = _IndexDict if isinstance(path[depth + 1], int) else dict
        child = parent.get(segment)
        if child is None:
            child = child_type()
            parent[segment] = child
        elif type(child) is not child_type:
            errors.append(StructuralError(key, "conflicting structure"))
            return
        parent = child

    if path[-1] in parent:
        errors.append(StructuralError(key, "conflicting structure"))
        return
    parent[path[-1]] = value


def _finalize(node: Any, path: Path, errors: list[StructuralError]) -> Any:
    if isinstance(node, _IndexDict):
        indexed = sorted(node.items())
        if [index for index, _ in indexed] != list(range(len(indexed))):
            errors.append(
                StructuralError(
                    path_to_name(path), "list indexes must be contiguous from 0"
                )
            )
        return [_finalize(child, (*path, index), errors) for index, child in indexed]
    if isinstance(node, dict):
        return {
            key: _finalize(child, (*path, key), errors) for key, child in node.items()
        }
    return node
