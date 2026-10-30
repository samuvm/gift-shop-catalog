"""The served OpenAPI is a contract: it follows the platform's rules and changes only on purpose.

To accept an intended change: UPDATE_SNAPSHOT=1 uv run pytest tests/api/test_openapi.py
"""

import importlib.util
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from catalog.tools import TOOLS

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = Path(__file__).with_name("openapi.snapshot.json")
_spec = importlib.util.spec_from_file_location("spec_lint", ROOT / "scripts" / "spec_lint.py")
assert _spec and _spec.loader
spec_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(spec_lint)


def test_spec_follows_the_platform_rules(client: TestClient) -> None:
    assert spec_lint.lint(client.get("/openapi.json").json()) == []


def test_one_operation_per_tool_with_the_tool_name(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert sorted(op["get"]["operationId"] for op in spec["paths"].values()) == sorted(t.name for t in TOOLS)


def test_lint_catches_what_it_is_meant_to(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    spec["paths"]["/categories"]["get"]["responses"]["200"]["content"]["application/json"]["schema"] = {
        "$ref": "#/components/schemas/X"
    }
    spec["paths"]["/products/search"]["get"]["parameters"].append(
        {"name": "X-Trace", "in": "header", "description": "short", "schema": {}}
    )
    problems = " | ".join(spec_lint.lint(spec))
    for expected in ("uses $ref", "sent as a header", "not snake_case", "schema has no type", "shorter than"):
        assert expected in problems


def test_served_spec_matches_the_snapshot(client: TestClient) -> None:
    served = client.get("/openapi.json").json()
    if os.environ.get("UPDATE_SNAPSHOT") or not SNAPSHOT.exists():
        SNAPSHOT.write_text(json.dumps(served, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    assert served == json.loads(SNAPSHOT.read_text(encoding="utf-8"))
