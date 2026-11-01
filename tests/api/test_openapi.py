"""The served OpenAPI is a contract: it follows the platform's rules and changes only on purpose.

To accept an intended change: UPDATE_SNAPSHOT=1 uv run pytest tests/api/test_openapi.py
"""

import importlib.util
import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from catalog.api.app import create_app
from catalog.service import CHOICES
from catalog.tools import RECIPIENTS, SLUGS, TOOLS

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
    if os.environ.get("UPDATE_SNAPSHOT") == "1":
        SNAPSHOT.write_text(json.dumps(served, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    assert SNAPSHOT.exists(), f"{SNAPSHOT.name} is missing; create it on purpose with UPDATE_SNAPSHOT=1"
    assert served == json.loads(SNAPSHOT.read_text(encoding="utf-8"))


# ---------- the routes FastAPI validates against and the spec the model reads cannot drift apart

COMPARED = ("type", "enum", "pattern", "minimum", "maximum", "maxLength", "default")
# Constraints the spec advertises that FastAPI deliberately does not enforce, and who does instead.
LENIENT = {
    "category": {"enum"},  # the domain resolves slugs, names and aliases, and answers with did_you_mean
    "occasion": {"enum"},  # service.normalise: any case, allowed_values on error
    "sort": {"enum"},  # service.normalise: any case, allowed_values on error
    "recipient": {"pattern"},  # service.normalise: any case, spaces and empty items, allowed_values
    "limit": {"maximum"},  # a larger limit is reduced to 10 with a note
}


def _constraints(schema: dict[str, Any]) -> dict[str, Any]:
    """A parameter schema reduced to what validation depends on, without FastAPI's `anyOf` null."""
    branches = [s for s in schema.get("anyOf", [schema]) if s.get("type") != "null"]
    merged = {**schema, **branches[0]}
    return {k: merged[k] for k in COMPARED if merged.get(k) is not None}


def _parameters(spec: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (path, p["name"]): {
            "in": p["in"],
            "required": p.get("required", False),
            **_constraints(p["schema"]),
        }
        for path, op in spec["paths"].items()
        for p in op["get"].get("parameters", [])
    }


def test_route_parameters_match_the_served_spec(client: TestClient) -> None:
    routes = _parameters(create_app("k").openapi())
    served = _parameters(client.get("/openapi.json").json())
    assert set(routes) == set(served)
    for key, advertised in served.items():
        relaxed = LENIENT.get(key[1], set())
        expected = {k: v for k, v in advertised.items() if k not in relaxed}
        assert routes[key] == expected, key


def test_what_fastapi_leaves_open_is_enforced_with_the_advertised_values(client: TestClient) -> None:
    served = _parameters(client.get("/openapi.json").json())
    enums = {name: v["enum"] for (_, name), v in served.items() if "enum" in v}
    assert enums == {"category": SLUGS, **CHOICES}
    pattern = served[("/products/search", "recipient")]["pattern"]
    assert all(r in pattern for r in RECIPIENTS)
