from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel

from formidant.core.exceptions import InvalidFormAccessError
from formidant.core.form_types import BindResult

if TYPE_CHECKING:
    from formidant.core.rendering import TemplateEngine


@dataclass(frozen=True)
class BoundForm[M: BaseModel]:
    """A form in one of three states: unbound, bound-valid, or bound-invalid.

    Unbound forms render blank (or from `initial` in the edit case); invalid
    forms re-render with raw input and errors; valid forms expose the typed
    instance. Reading `instance` in any other state raises - the one deliberate
    exception in the API, so half-valid data can never be read silently.
    """

    model: type[M]
    result: BindResult[M] | None = None
    initial: M | None = None

    @classmethod
    def unbound(cls, model: type[M], instance: M | None = None) -> "BoundForm[M]":
        """An unsubmitted form: blank, or pre-populated from `instance` for edit pages."""
        return cls(model=model, initial=instance)

    @property
    def bound(self) -> bool:
        return self.result is not None

    @property
    def valid(self) -> bool:
        return self.result is not None and self.result.valid

    @property
    def errors(self) -> dict[str, list[str]]:
        return self.result.errors if self.result is not None else {}

    @property
    def raw(self) -> dict[str, list[str]]:
        return self.result.raw if self.result is not None else {}

    @property
    def instance(self) -> M:
        if self.result is None or self.result.instance is None:
            raise InvalidFormAccessError(
                f"{self.model.__name__} form is not valid; check .valid before reading .instance"
            )
        return self.result.instance

    def render(
        self, engine: "TemplateEngine | None" = None, hidden_inputs: str = ""
    ) -> str:
        """Render the full form body through the default or given template engine."""
        from formidant.core.rendering import render_form

        return render_form(self, engine=engine, hidden_inputs=hidden_inputs)

    def render_field(
        self,
        name: str,
        engine: "TemplateEngine | None" = None,
        index: int | None = None,
    ) -> str:
        """Render one field (or one repeat row, with `index`) in isolation."""
        from formidant.core.rendering import render_field

        return render_field(self, name, engine=engine, index=index)


@dataclass(frozen=True)
class BoundContract:
    """Adapter-inspectable marker carried by Bound[Model] annotations."""

    model: type[BaseModel]


class Bound:
    """View annotation contract: Bound[Model] means the body always runs.

    Where a plain `form: Model` annotation short-circuits invalid submissions,
    `form: Bound[Model]` hands the body the BoundForm itself - errors, raw
    values and all - restoring manual branching with decorator ergonomics.
    """

    def __class_getitem__(cls, model: type[BaseModel]) -> Any:
        return Annotated[BoundForm, BoundContract(model)]


@dataclass(frozen=True)
class FormContract:
    """Adapter-inspectable marker carried by Form[Model] annotations."""

    model: type[BaseModel]


class Form:
    """View annotation contract: Form[Model] binds the parameter from form data.

    In a multi-source view signature, Form[Model] marks the parameter that
    binds from the submitted form body; the body receives the validated,
    typed instance.
    """

    def __class_getitem__(cls, model: type[BaseModel]) -> Any:
        return Annotated[model, FormContract(model)]
