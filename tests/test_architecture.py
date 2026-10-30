"""Layer boundaries (goal G-ARCH-LAYERS), checked on the import statements of the source tree.

The domain imports no transport or web framework; REST and MCP do not import each other.
"""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "catalog"
FORBIDDEN = {
    "domain": (
        "fastapi",
        "starlette",
        "uvicorn",
        "mcp",
        "httpx",
        "catalog.api",
        "catalog.mcp_server",
        "catalog.service",
        "catalog.storage",
        "catalog.ingest",
    ),
    "api": ("catalog.mcp_server",),
    "mcp_server": ("catalog.api",),
}


def imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_layers_do_not_import_across_boundaries() -> None:
    violations = []
    for layer, banned in FORBIDDEN.items():
        base = SRC / layer
        files = [base] if base.with_suffix(".py").exists() else []
        paths = [base.with_suffix(".py")] if files else sorted(base.rglob("*.py"))
        for path in paths:
            for module in imports(path):
                if any(module == b or module.startswith(f"{b}.") for b in banned):
                    violations.append(f"{path.relative_to(ROOT)} imports {module}")
    report = ROOT / "evals" / "reports" / "arch-latest.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"violations": len(violations), "detail": violations}, indent=2) + "\n")
    assert violations == []


def test_the_check_would_catch_a_violation(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("from fastapi import FastAPI\nimport catalog.api.app\n")
    assert {"fastapi", "catalog.api.app"} <= imports(bad)
