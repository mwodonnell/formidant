class FormidantError(Exception):
    """Base for all formidant errors."""


class InvalidFormAccessError(FormidantError):
    """Raised when .instance is read from a form that is not valid."""
