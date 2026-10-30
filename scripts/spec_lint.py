"""Read the served OpenAPI the way the platform and a model will (goal G-SPEC-LINT).

Rules: OpenAPI 3.0.3; no $ref, oneOf, anyOf or allOf anywhere (the platform's form cannot edit
them); one GET per path; every operation has a snake_case operationId, a summary and a description
long enough to decide when to call it; every parameter is snake_case, typed and described, and not
sent as a header; every 200 response has a schema and an example.

Usage: uv run python scripts/spec_lint.py   (builds the app locally and writes the report)
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "evals" / "reports" / "spec-lint-latest.json"
SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
BANNED_KEYS = ("$ref", "oneOf", "anyOf", "allOf")
MIN_OPERATION_DESCRIPTION = 200
MIN_PARAMETER_DESCRIPTION = 20


def lint(spec: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if spec.get("openapi") != "3.0.3":
        problems.append(f"openapi is {spec.get('openapi')!r}, expected '3.0.3'")

    def walk(node: Any, where: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in BANNED_KEYS:
                    problems.append(f"{where}: uses {key}")
                walk(value, f"{where}.{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{where}[{i}]")

    walk(spec, "spec")
    for path, methods in spec.get("paths", {}).items():
        if set(methods) != {"get"}:
            problems.append(f"{path}: methods {sorted(methods)}, expected only get")
        for method, op in methods.items():
            where = f"{method.upper()} {path}"
            if not SNAKE.match(op.get("operationId", "")):
                problems.append(f"{where}: operationId {op.get('operationId')!r} is not snake_case")
            if not op.get("summary"):
                problems.append(f"{where}: no summary")
            if len(op.get("description", "")) < MIN_OPERATION_DESCRIPTION:
                problems.append(f"{where}: description shorter than {MIN_OPERATION_DESCRIPTION} characters")
            for p in op.get("parameters", []):
                pw = f"{where} param {p.get('name')}"
                if p.get("in") == "header":
                    problems.append(f"{pw}: sent as a header (the platform form cannot edit it)")
                if not SNAKE.match(p.get("name", "")):
                    problems.append(f"{pw}: name is not snake_case")
                if "type" not in p.get("schema", {}):
                    problems.append(f"{pw}: schema has no type")
                if len(p.get("description", "")) < MIN_PARAMETER_DESCRIPTION:
                    problems.append(f"{pw}: description shorter than {MIN_PARAMETER_DESCRIPTION} characters")
            ok = op.get("responses", {}).get("200", {}).get("content", {}).get("application/json", {})
            if "schema" not in ok:
                problems.append(f"{where}: 200 response has no schema")
            if "example" not in ok:
                problems.append(f"{where}: 200 response has no example")
    return problems


def main() -> int:
    from fastapi.testclient import TestClient

    from catalog.api.app import create_app

    spec = TestClient(create_app("spec-lint")).get("/openapi.json").json()
    problems = lint(spec)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"violations": len(problems), "detail": problems}, indent=2) + "\n")
    for p in problems:
        print(f"  ✗ {p}")
    print(f"spec-lint: {len(problems)} violations -> {REPORT.relative_to(ROOT)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
