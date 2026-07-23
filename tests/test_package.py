import formidant
import formidant.core


def test_package_imports() -> None:
    assert formidant.__doc__ is not None
    assert formidant.core is not None


def test_public_api_is_narrow() -> None:
    assert all(hasattr(formidant, name) for name in formidant.__all__)
    assert len(formidant.__all__) <= 16
