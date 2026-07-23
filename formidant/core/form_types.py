"""Shared vocabulary for the binding pipeline: paths, results, and errors.

Named form_types (not types) to stay unambiguous next to the stdlib module.
"""

from dataclasses import dataclass, field

from pydantic import BaseModel

PathSegment = str | int
Path = tuple[PathSegment, ...]
ListPath = tuple[str, ...]


@dataclass(frozen=True)
class StructuralError:
    """A malformed-input problem found before validation, tied to an input name."""

    input_name: str
    message: str


@dataclass(frozen=True)
class InflateResult:
    """Nested data ready for model validation, plus any structural errors."""

    data: dict
    errors: list[StructuralError] = field(default_factory=list)


@dataclass(frozen=True)
class BindResult[M: BaseModel]:
    """Outcome of binding form data to a model: an instance or an error map, plus raw input."""

    instance: M | None
    errors: dict[str, list[str]]
    raw: dict[str, list[str]] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return self.instance is not None
