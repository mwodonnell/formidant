import subprocess
import sys


def test_core_imports_no_django() -> None:
    code = (
        "import sys, formidant.core.constants, formidant.core.flatten, "
        "formidant.core.protocol; "
        "polluted = [m for m in sys.modules if m == 'django' or m.startswith('django.')]; "
        "assert not polluted, polluted"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
