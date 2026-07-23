import pkgutil
import subprocess
import sys

import formidant.core


def _all_core_modules() -> list[str]:
    return [
        f"formidant.core.{module.name}"
        for module in pkgutil.iter_modules(formidant.core.__path__)
    ]


def test_core_package_is_not_empty() -> None:
    assert len(_all_core_modules()) >= 6


def test_core_imports_no_django() -> None:
    imports = ", ".join(_all_core_modules())
    code = (
        f"import sys, {imports}; "
        "polluted = [m for m in sys.modules if m == 'django' or m.startswith('django.')]; "
        "assert not polluted, polluted"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
