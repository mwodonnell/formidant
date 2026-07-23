import ast
from pathlib import Path

import formidant.django


def test_django_adapter_uses_public_core_surface_only() -> None:
    violations: list[str] = []
    for path in Path(formidant.django.__path__[0]).rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.ImportFrom):
                continue
            if not (node.module or "").startswith("formidant.core"):
                continue
            for alias in node.names:
                if alias.name.startswith("_"):
                    violations.append(f"{path.name}: {node.module}.{alias.name}")
    assert not violations, violations
