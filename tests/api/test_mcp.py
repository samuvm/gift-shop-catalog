"""MCP contract: the tool list, tool results and errors over Streamable HTTP, held against REST (ADR-008)."""

import json
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from catalog.api.app import create_app
from catalog.tools import OCCASIONS, TOOLS

KEY = "test-key-not-a-secret"
HEADERS = {
    "X-API-Key": KEY,
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    # `with` runs the lifespan that starts the MCP session manager.
    with TestClient(create_app(KEY, today=lambda: date(2026, 10, 30))) as c:
        yield c


def rpc(client: TestClient, method: str, params: dict[str, Any], headers: dict[str, str] = HEADERS) -> Any:
    message = {"jsonrpc": "2.0", "id": 7, "method": method, "params": params}
    return client.post("/mcp", content=json.dumps(message), headers=headers)


def call(client: TestClient, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    response = rpc(client, "tools/call", {"name": tool, "arguments": args})
    assert response.status_code == 200
    return dict(response.json()["result"])


def rest(client: TestClient, path: str) -> Any:
    return client.get(path, headers={"X-API-Key": KEY})


class TestToolList:
    def test_the_four_tools_are_generated_from_the_definitions(self, client: TestClient) -> None:
        listed = rpc(client, "tools/list", {}).json()["result"]["tools"]
        assert [t["name"] for t in listed] == [t.name for t in TOOLS]
        for got, tool in zip(listed, TOOLS, strict=True):
            assert got["description"] == tool.description
            assert got["inputSchema"] == {
                "type": "object",
                "properties": {p.name: {**p.schema, "description": p.description} for p in tool.params},
                "required": [p.name for p in tool.params if p.required],
            }

    def test_every_tool_is_read_only_and_declares_no_output_schema(self, client: TestClient) -> None:
        for tool in rpc(client, "tools/list", {}).json()["result"]["tools"]:
            assert tool["annotations"]["readOnlyHint"] is True
            assert "outputSchema" not in tool


class TestResults:
    @pytest.mark.parametrize(
        ("tool", "args", "path"),
        [
            ("get_categories", {}, "/categories"),
            (
                "get_products_by_category",
                {"category": "kitchen", "max_price": 60},
                "/categories/kitchen/products?max_price=60",
            ),
            (
                "search_products",
                {"query": "chef knife", "max_price": 100},
                "/products/search?query=chef%20knife&max_price=100",
            ),
            ("get_product_details", {"product_id": "kd-7"}, "/products/kd-7"),
        ],
    )
    def test_a_result_is_the_rest_body_as_structured_content_and_as_text(
        self, client: TestClient, tool: str, args: dict[str, Any], path: str
    ) -> None:
        result, expected = call(client, tool, args), rest(client, path)
        assert result["isError"] is False
        assert result["structuredContent"] == expected.json()
        assert result["content"] == [{"type": "text", "text": expected.text}]

    @pytest.mark.parametrize(
        ("args", "query"),
        [
            ({"recipient": "HER, Couple"}, "recipient=HER,%20Couple"),
            ({"occasion": "Birthday", "sort": "PRICE_ASC"}, "occasion=Birthday&sort=PRICE_ASC"),
            (
                {"max_price": "50", "limit": "3", "include_out_of_stock": "true"},
                "max_price=50&limit=3&include_out_of_stock=true",
            ),
            ({"limit": 5.0, "offset": 5}, "limit=5&offset=5"),
            ({"limit": 25}, "limit=25"),
            ({"query": "candle", "occasion": None, "sort": ""}, "query=candle&sort="),
        ],
    )
    def test_loose_values_are_read_as_rest_reads_them(
        self, client: TestClient, args: dict[str, Any], query: str
    ) -> None:
        expected = rest(client, f"/products/search?{query}")
        assert expected.status_code == 200
        assert call(client, "search_products", args)["structuredContent"] == expected.json()

    def test_a_domain_error_is_a_tool_error_with_the_rest_body(self, client: TestClient) -> None:
        result = call(client, "get_products_by_category", {"category": "garden"})
        expected = rest(client, "/categories/garden/products")
        assert result["isError"] is True
        assert result["structuredContent"] == expected.json()
        assert result["content"][0]["text"] == expected.text


class TestInvalidArguments:
    @pytest.mark.parametrize(
        ("tool", "args", "path"),
        [
            ("search_products", {"limit": 0}, "/products/search?limit=0"),
            ("search_products", {"offset": -1}, "/products/search?offset=-1"),
            ("search_products", {"max_shipping_days": 15}, "/products/search?max_shipping_days=15"),
            ("search_products", {"min_price": -1}, "/products/search?min_price=-1"),
            ("search_products", {"max_price": "inf"}, "/products/search?max_price=inf"),
            (
                "search_products",
                {"min_price": 80, "max_price": 20},
                "/products/search?min_price=80&max_price=20",
            ),
            ("search_products", {"limit": "two"}, "/products/search?limit=two"),
            ("search_products", {"limit": 2.5}, "/products/search?limit=2.5"),
            ("search_products", {"query": "x" * 101}, "/products/search?query=" + "x" * 101),
            (
                "search_products",
                {"recipient": "her," * 10 + "him"},
                "/products/search?recipient=" + "her," * 10 + "him",
            ),
            ("search_products", {"recipient": "wife"}, "/products/search?recipient=wife"),
            ("search_products", {"occasion": "halloween"}, "/products/search?occasion=halloween"),
            (
                "search_products",
                {"include_out_of_stock": "maybe"},
                "/products/search?include_out_of_stock=maybe",
            ),
            ("get_products_by_category", {"category": "x" * 51}, "/categories/" + "x" * 51 + "/products"),
            ("get_product_details", {"product_id": "X" * 21}, "/products/" + "X" * 21),
        ],
    )
    def test_what_rest_refuses_mcp_refuses_with_the_same_code_hint_and_allowed_values(
        self, client: TestClient, tool: str, args: dict[str, Any], path: str
    ) -> None:
        result = call(client, tool, args)
        got, expected = result["structuredContent"]["error"], rest(client, path).json()["error"]
        assert result["isError"] is True
        assert got["code"] == expected["code"] == "invalid_parameter"
        assert got["message"].split(":")[0] == expected["message"].split(":")[0]
        assert (got["hint"], got.get("allowed_values")) == (expected["hint"], expected.get("allowed_values"))

    def test_a_missing_required_argument_names_it(self, client: TestClient) -> None:
        error = call(client, "get_product_details", {})["structuredContent"]["error"]
        assert error["code"] == "invalid_parameter" and error["message"].startswith("product_id")

    def test_an_occasion_outside_the_set_lists_the_allowed_ones(self, client: TestClient) -> None:
        error = call(client, "search_products", {"occasion": "halloween"})["structuredContent"]["error"]
        assert error["allowed_values"] == OCCASIONS


class TestProtocol:
    def test_initialize_answers_the_handshake_era(self, client: TestClient) -> None:
        params = {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "t", "version": "1"},
        }
        result = rpc(client, "initialize", params).json()["result"]
        assert result["protocolVersion"] == "2025-11-25"
        assert "tools" in result["capabilities"] and result["serverInfo"]["name"] == "gift-shop-catalog"

    def test_an_unknown_tool_is_a_jsonrpc_error(self, client: TestClient) -> None:
        body = rpc(client, "tools/call", {"name": "get_weather", "arguments": {}}).json()
        assert "result" not in body and body["error"]["code"] == -32602

    def test_calls_need_no_initialize_and_open_no_session(self, client: TestClient) -> None:
        response = rpc(client, "tools/call", {"name": "get_categories", "arguments": {}})
        assert response.status_code == 200 and "mcp-session-id" not in response.headers

    def test_get_is_refused_with_405_instead_of_an_idle_stream(self, client: TestClient) -> None:
        response = client.get("/mcp", headers=HEADERS)
        assert response.status_code == 405 and response.headers["allow"] == "POST"

    def test_every_app_gets_its_own_mcp_server(self) -> None:
        for _ in range(2):
            with TestClient(create_app(KEY)) as c:
                assert call(c, "get_categories", {})["isError"] is False


class TestAuth:
    @pytest.mark.parametrize("key", [None, "", "nope"])
    def test_a_missing_or_wrong_key_is_401_with_the_rest_body_and_no_bearer_challenge(
        self, client: TestClient, key: str | None
    ) -> None:
        headers = {k: v for k, v in HEADERS.items() if k != "X-API-Key"} | (
            {"X-API-Key": key} if key is not None else {}
        )
        response = rpc(client, "tools/call", {"name": "get_categories", "arguments": {}}, headers)
        body = response.json()
        assert response.status_code == 401 and "www-authenticate" not in response.headers
        assert body["id"] is None and "result" not in body
        assert body["error"]["code"] == -32001
        assert body["error"]["data"] == client.get("/categories").json()

    def test_the_key_is_checked_before_the_method(self, client: TestClient) -> None:
        assert client.get("/mcp").status_code == 401


class TestRequestLog:
    """One log line per /mcp request, so a client's failure can be read from the server side."""

    def test_a_request_logs_its_method_protocol_and_status_without_the_key(
        self, client: TestClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("INFO", logger="uvicorn.error")
        headers = {**HEADERS, "MCP-Protocol-Version": "2025-06-18", "User-Agent": "probe/1"}
        rpc(client, "tools/list", {}, headers)
        line = next(r.getMessage() for r in caplog.records if r.getMessage().startswith("mcp "))
        assert "rpc=tools/list" in line
        assert "protocol=2025-06-18" in line
        assert "status=200" in line
        assert "agent=probe/1" in line
        assert KEY not in line

    def test_a_refused_key_is_logged_too(self, client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level("INFO", logger="uvicorn.error")
        rpc(client, "tools/list", {}, {**HEADERS, "X-API-Key": "wrong"})
        line = next(r.getMessage() for r in caplog.records if r.getMessage().startswith("mcp "))
        assert "status=401" in line
        assert "wrong" not in line
