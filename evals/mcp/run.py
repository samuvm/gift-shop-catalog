"""MCP server eval over Streamable HTTP (goals G-MCP-PARITY and G-MCP-CONFORMANCE).

Parity: every level-1 case is sent twice, as a REST request and as an MCP tools/call with the same
arguments, and the two answers must be the same. A success needs structuredContent equal to the REST
body and the text content byte-for-byte equal to it (what the model reads); an error needs isError
and the REST error body. By design the HTTP status (200 vs 4xx) is not compared: MCP reports a tool
error inside a successful JSON-RPC response, with isError.

Conformance: protocol checks sent as raw HTTP, so they do not depend on any MCP client library:
the handshake era (initialize, 2025-11-25) and the per-request era (server/discover, 2026-07-28),
tools/list against the tool definitions, tools/call results and errors, JSON-RPC errors, the
X-API-Key check and the transport's HTTP answers.

Runs in-process with a pinned date by default. With a base URL it runs against a deployment, with
the key from CATALOG_API_KEY.

Usage: uv run python evals/mcp/run.py [https://base.url]
"""

import importlib.util
import json
import os
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from mcp_types.version import HANDSHAKE_PROTOCOL_VERSIONS

from catalog.tools import TOOLS

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "evals" / "golden" / "l1" / "v5.jsonl"
REPORT = ROOT / "evals" / "reports" / "mcp-latest.json"
TODAY = date(2026, 10, 30)
HANDSHAKE, MODERN = "2025-11-25", "2026-07-28"
ACCEPT = "application/json, text/event-stream"
BY_DESIGN = [
    "A tool error is HTTP 200 with result.isError true over MCP, and HTTP 4xx over REST; "
    "the body is the same.",
    "A parameter the framework rejects (type, bound, length) is answered with the same code, hint and "
    "allowed_values over both; the message wording comes from each validator (pydantic vs JSON Schema).",
    "A JSON-RPC envelope that is not a request is answered with code -32602 by the SDK's handshake-era "
    "path (JSON-RPC names -32600); the per-request era answers -32600.",
]


def _l1_runner() -> Any:
    spec = importlib.util.spec_from_file_location("l1_run", ROOT / "evals" / "golden" / "l1" / "run.py")
    if spec is None or spec.loader is None:
        raise SystemExit("evals/golden/l1/run.py not found")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Wire:
    """Raw HTTP to /mcp and to the REST routes of one service."""

    def __init__(self, http: Any, key: str) -> None:
        self.http, self.key = http, key
        self.headers = {"X-API-Key": key, "Accept": ACCEPT, "Content-Type": "application/json"}

    def post(self, body: Any, headers: dict[str, str] | None = None, raw: str | None = None) -> Any:
        content = raw if raw is not None else json.dumps(body)
        return self.http.post("/mcp", content=content, headers=headers or self.headers)

    def rpc(self, method: str, params: dict[str, Any] | None = None, **headers: str) -> Any:
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            message["params"] = params
        return self.post(message, {**self.headers, **headers})

    def call(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        return dict(self.rpc("tools/call", {"name": tool, "arguments": args}).json()["result"])

    def modern(self, method: str, params: dict[str, Any], name: str | None = None) -> Any:
        meta = {
            "io.modelcontextprotocol/protocolVersion": MODERN,
            "io.modelcontextprotocol/clientCapabilities": {},
        }
        headers = {
            "MCP-Protocol-Version": MODERN,
            "Mcp-Method": method,
            **({"Mcp-Name": name} if name else {}),
        }
        return self.rpc(method, {**params, "_meta": meta}, **headers)

    def rest(self, path: str) -> Any:
        return self.http.get(path, headers={"X-API-Key": self.key})


def _dump(body: Any) -> str:
    return json.dumps(body, sort_keys=True, ensure_ascii=False)


def same_answer(result: dict[str, Any], rest: Any) -> bool:
    """One MCP tools/call result against the REST response to the same call."""
    body = rest.json()
    is_error = rest.status_code >= 400
    text = result["content"][0]["text"] if result.get("content") else ""
    return (
        result.get("isError", False) is is_error
        and _dump(result.get("structuredContent")) == _dump(body)
        and text == rest.text
    )


def conformance(w: Wire) -> dict[str, bool]:
    checks: dict[str, Callable[[], bool]] = {}
    init = {"capabilities": {}, "clientInfo": {"name": "mcp-eval", "version": "1"}}

    def initialize() -> bool:
        r = w.rpc("initialize", {"protocolVersion": HANDSHAKE, **init})
        res = r.json().get("result", {})
        return (
            r.status_code == 200
            and r.headers["content-type"].startswith("application/json")
            and res.get("protocolVersion") == HANDSHAKE
            and "tools" in res.get("capabilities", {})
            and res.get("serverInfo", {}).get("name") == "gift-shop-catalog"
        )

    def unsupported_version() -> bool:
        res = w.rpc("initialize", {"protocolVersion": "1999-01-01", **init}).json().get("result", {})
        return res.get("protocolVersion") in HANDSHAKE_PROTOCOL_VERSIONS

    def initialized_notification() -> bool:
        r = w.post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return r.status_code == 202 and r.content == b""

    def tools_list() -> bool:
        listed = w.rpc("tools/list", {}).json()["result"]["tools"]
        expected = [
            (
                t.name,
                t.description,
                {p.name: {**p.schema, "description": p.description} for p in t.params},
                sorted(p.name for p in t.params if p.required),
            )
            for t in TOOLS
        ]
        got = [
            (
                t["name"],
                t["description"],
                t["inputSchema"]["properties"],
                sorted(t["inputSchema"]["required"]),
            )
            for t in listed
        ]
        read_only = all(t["annotations"]["readOnlyHint"] is True for t in listed)
        return got == expected and read_only and all(t["inputSchema"]["type"] == "object" for t in listed)

    def call_success() -> bool:
        return same_answer(w.call("get_categories", {}), w.rest("/categories"))

    def unknown_tool() -> bool:
        body = w.rpc("tools/call", {"name": "get_weather", "arguments": {}}).json()
        return "result" not in body and body.get("error", {}).get("code") == -32602

    def domain_error() -> bool:
        result = w.call("get_product_details", {"product_id": "XX-999"})
        return same_answer(result, w.rest("/products/XX-999")) and result["isError"] is True

    def invalid_argument() -> bool:
        error = w.call("search_products", {"limit": 0})["structuredContent"]["error"]
        rest = w.rest("/products/search?limit=0").json()["error"]
        same = {k: error.get(k) for k in ("code", "hint", "allowed_values")}
        return error["message"].startswith("limit") and same == {
            k: rest.get(k) for k in ("code", "hint", "allowed_values")
        }

    def loose_value() -> bool:
        args = {"query": "necklace", "recipient": "HER, Couple", "occasion": "Anniversary"}
        rest = w.rest("/products/search?query=necklace&recipient=HER,%20Couple&occasion=Anniversary")
        return rest.status_code == 200 and same_answer(w.call("search_products", args), rest)

    def parse_error() -> bool:
        r = w.post(None, raw="{not json")
        return r.status_code == 400 and r.json()["error"]["code"] == -32700

    def invalid_request() -> bool:
        r = w.post({"jsonrpc": "2.0", "id": 1})
        body = r.json()
        return r.status_code == 400 and body["id"] is None and body["error"]["code"] in (-32600, -32602)

    def auth() -> bool:
        rest_401 = w.http.get("/categories").json()
        ok = True
        for key in (None, "", "wrong-key"):
            headers = {k: v for k, v in w.headers.items() if k != "X-API-Key"}
            if key is not None:
                headers["X-API-Key"] = key
            message = {"jsonrpc": "2.0", "id": 1, "method": "tools/call"}
            r = w.post({**message, "params": {"name": "get_categories", "arguments": {}}}, headers)
            body = r.json()
            ok &= (
                r.status_code == 401
                and "result" not in body
                and body["error"]["code"] == -32001
                and body["error"]["data"] == rest_401
                and "www-authenticate" not in r.headers
            )
        return ok

    def http_answers() -> bool:
        get = w.http.get("/mcp", headers=w.headers)
        not_json = w.rpc("tools/list", {}, Accept="text/html")
        json_only = w.rpc("tools/list", {}, Accept="application/json")
        return (
            get.status_code == 405
            and get.headers.get("allow") == "POST"
            and not_json.status_code == 406
            and json_only.status_code == 200
        )

    def stateless() -> bool:
        r = w.rpc("tools/call", {"name": "get_categories", "arguments": {}})
        return (
            r.status_code == 200 and "mcp-session-id" not in r.headers and not r.json()["result"]["isError"]
        )

    def modern_discover() -> bool:
        res = w.modern("server/discover", {}).json().get("result", {})
        return MODERN in res.get("supportedVersions", []) and "tools" in res.get("capabilities", {})

    def modern_call() -> bool:
        r = w.modern(
            "tools/call",
            {"name": "get_product_details", "arguments": {"product_id": "kd-7"}},
            "get_product_details",
        )
        return same_answer(r.json()["result"], w.rest("/products/kd-7"))

    checks = {
        "initialize_2025_11_25": initialize,
        "initialize_unsupported_version_gets_a_supported_one": unsupported_version,
        "initialized_notification_is_202_without_body": initialized_notification,
        "tools_list_equals_the_tool_definitions_read_only": tools_list,
        "tools_call_success_equals_rest": call_success,
        "unknown_tool_is_a_jsonrpc_error": unknown_tool,
        "domain_error_is_iserror_with_the_rest_body": domain_error,
        "invalid_argument_is_iserror_invalid_parameter": invalid_argument,
        "loose_closed_set_values_read_like_rest": loose_value,
        "malformed_json_is_parse_error": parse_error,
        "non_request_envelope_is_rejected": invalid_request,
        "missing_empty_or_wrong_key_is_401_without_executing": auth,
        "get_is_405_and_accept_without_json_is_406": http_answers,
        "stateless_call_without_initialize_or_session": stateless,
        "server_discover_2026_07_28": modern_discover,
        "tools_call_2026_07_28_equals_rest": modern_call,
    }
    results = {}
    for name, check in checks.items():
        try:
            results[name] = bool(check())
        except Exception as err:  # a check that crashes is a failed check, with the reason kept
            print(f"  ! {name}: {type(err).__name__}: {err}")
            results[name] = False
    return results


def parity(w: Wire) -> list[dict[str, Any]]:
    url_for = _l1_runner().url_for
    results = []
    for line in CASES.open(encoding="utf-8"):
        case = json.loads(line)
        rest = w.rest(url_for(case["tool"], case["args"]))
        result = w.call(case["tool"], case["args"])
        results.append(
            {"id": case["id"], "passed": same_answer(result, rest), "rest_status": rest.status_code}
        )
    return results


def main() -> int:
    base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else None
    if base:
        import httpx

        key = os.environ.get("CATALOG_API_KEY")
        if not key:
            raise SystemExit("CATALOG_API_KEY is not set")
        with httpx.Client(base_url=base, timeout=15) as http:
            checks, cases = conformance(Wire(http, key)), parity(Wire(http, key))
    else:
        from fastapi.testclient import TestClient

        from catalog.api.app import create_app

        # `with` runs the app's lifespan, which starts the MCP session manager.
        with TestClient(create_app("mcp-eval", today=lambda: TODAY)) as http:
            checks, cases = conformance(Wire(http, "mcp-eval")), parity(Wire(http, "mcp-eval"))
    report = {
        "parity_rate": sum(c["passed"] for c in cases) / len(cases),
        "conformance_rate": sum(checks.values()) / len(checks),
        "n": {"parity_cases": len(cases), "conformance_checks": len(checks)},
        "target": base or f"in-process, today pinned to {TODAY.isoformat()}",
        "failures": [*(c for c in cases if not c["passed"]), *(k for k, ok in checks.items() if not ok)],
        "checks": checks,
        "parity_error_cases": [c["id"] for c in cases if c["rest_status"] >= 400],
        "by_design_differences": BY_DESIGN,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for failure in report["failures"]:
        print(f"  ✗ {failure}")
    print(
        f"mcp: parity {sum(c['passed'] for c in cases)}/{len(cases)} · conformance "
        f"{sum(checks.values())}/{len(checks)} -> {REPORT.relative_to(ROOT)}"
    )
    return 0 if not report["failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
