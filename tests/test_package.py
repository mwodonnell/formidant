import formidant
import formidant.core


def test_package_imports() -> None:
    assert formidant.__doc__ is not None
    assert formidant.core is not None
