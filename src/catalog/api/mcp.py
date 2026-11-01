"""MCP transport: the four tools over Streamable HTTP at /mcp, behind the same X-API-Key (ADR-008).

The tool list is generated from `catalog.tools.TOOLS` and every call goes through
`catalog.service.execute`, exactly as REST does, so the two transports cannot answer differently.
"""

import json
import math
import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import mcp_types as types
from jsonschema import Draft202012Validator, ValidationError
from mcp.server.context import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

from catalog import __version__
from catalog.domain.errors import CatalogError
from catalog.service import Context, InvalidParameter, error_body, execute
from catalog.tools import TOOLS, Tool

INVALID_HINT = "Fix the parameter as described and call again. Allowed values are in the tool description."
BOOLEAN_HINT = "Use one of allowed_values."
TRUE, FALSE = {"1", "on", "t", "true", "y", "yes"}, {"0", "off", "f", "false", "n", "no"}
# Keywords the model reads but the transport does not enforce, because REST does not either: closed
# sets (`enum`, `pattern`) are read in any case by `service.normalise`, or resolved by the domain for
# a category, and both answer a wrong value with allowed_values and did_you_mean; a limit above the
# advertised maximum is clamped with a note (ADR-002). Types, bounds and lengths are checked here,
# as FastAPI checks them for REST.
LEFT_TO_THE_SERVICE = ("enum", "pattern")
CLAMPED = {"limit": "maximum"}
UNAUTHORIZED_RPC = -32001


def input_schema(tool: Tool) -> dict[str, Any]:
    """The tool's parameters as one JSON Schema object, with the same descriptions REST publishes."""
    return {
        "type": "object",
        "properties": {p.name: {**p.schema, "description": p.description} for p in tool.params},
        "required": [p.name for p in tool.params if p.required],
    }


def _validator(tool: Tool) -> Draft202012Validator:
    schema = input_schema(tool)
    for name, prop in schema["properties"].items():
        dropped = (*LEFT_TO_THE_SERVICE, CLAMPED.get(name))
        schema["properties"][name] = {k: v for k, v in prop.items() if k not in dropped}
    return Draft202012Validator(schema)


def _coerce(value: Any, kind: str | None) -> Any:
    """Read a number or boolean sent as a string the way REST reads a query string ('50', 'true').

    Decided: models often quote numbers in tool arguments, and REST accepts '50' because every query
    value is a string; refusing it over MCP only would cost a round trip for no reason. A whole
    float for an integer (5.0) becomes 5, which JSON Schema already counts as an integer.
    """
    if isinstance(value, str) and kind in ("number", "integer"):
        try:
            number = float(value)
        except ValueError:
            return value
        if not math.isfinite(number):  # 'inf' and 'nan' are not prices, as for REST
            return value
        value = number
    if isinstance(value, str) and kind == "boolean" and value.strip().lower() in TRUE | FALSE:
        return value.strip().lower() in TRUE
    if kind == "integer" and isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _where(e: ValidationError) -> str:
    """The parameter an error is about, so the message starts with its name as REST's does."""
    if e.validator == "required":
        return ", ".join(name for name in e.validator_value if name not in e.instance)
    return ".".join(str(x) for x in e.path) or "arguments"


def _invalid(problems: list[ValidationError]) -> dict[str, Any]:
    """The body REST answers for a parameter its framework rejects, built from the schema errors."""
    message = "; ".join(f"{_where(e)}: {e.message}" for e in problems)
    if any(e.validator == "type" and e.validator_value == "boolean" for e in problems):
        return error_body(InvalidParameter(message, BOOLEAN_HINT, ["true", "false"]))
    return error_body(InvalidParameter(message, INVALID_HINT))


def _result(body: dict[str, Any], is_error: bool = False) -> types.CallToolResult:
    # The same bytes REST sends (compact, UTF-8), so the model reads the same text over both.
    text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    return types.CallToolResult(
        content=[types.TextContent(text=text)], structured_content=body, is_error=is_error
    )


def build_server(context: Callable[[], Context]) -> Server[Any]:
    tools = {t.name: t for t in TOOLS}
    validators = {t.name: _validator(t) for t in TOOLS}
    listed = [
        types.Tool(
            name=t.name,
            description=t.description,
            input_schema=input_schema(t),
            annotations=types.ToolAnnotations(read_only_hint=True, open_world_hint=False),
        )
        for t in TOOLS
    ]

    async def list_tools(
        _: ServerRequestContext[Any], __: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        return types.ListToolsResult(tools=listed)

    async def call_tool(
        _: ServerRequestContext[Any], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        tool = tools.get(params.name)
        if tool is None:
            raise MCPError(types.INVALID_PARAMS, f"Unknown tool: {params.name!r}.", {"tools": list(tools)})
        kinds = {p.name: p.schema.get("type") for p in tool.params}
        # A null argument means the filter was left out, as an absent query parameter does in REST.
        args = {k: _coerce(v, kinds.get(k)) for k, v in (params.arguments or {}).items() if v is not None}
        problems = sorted(validators[tool.name].iter_errors(args), key=lambda e: [str(x) for x in e.path])
        if problems:
            return _result(_invalid(problems), is_error=True)
        try:
            return _result(execute(context(), tool.name, args))
        except CatalogError as err:
            return _result(error_body(err), is_error=True)

    return Server(
        "gift-shop-catalog",
        version=__version__,
        title="Gift Shop Catalog",
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


class Endpoint:
    """The ASGI app served at /mcp: the API key check, then the SDK's Streamable HTTP transport."""

    def __init__(self, context: Callable[[], Context], api_key: str, unauthorized: dict[str, Any]) -> None:
        self._key = api_key.encode()
        self._unauthorized = unauthorized
        # Decided: stateless and JSON responses, because every tool is one read with one answer: no
        # session to keep between calls, no server-to-client messages to stream. DNS-rebinding
        # protection is off because it only allows listed Host headers and the service is reached
        # by a public hostname; every request already needs the API key.
        self._manager = StreamableHTTPSessionManager(
            app=build_server(context),
            json_response=True,
            stateless=True,
            security_settings=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        )

    @property
    def route(self) -> Route:
        """A plain route, not a mount: /mcp answers as is, with no redirect to /mcp/."""
        return Route("/mcp", endpoint=self)

    @asynccontextmanager
    async def run(self) -> AsyncIterator[None]:
        async with self._manager.run():
            yield

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        sent = dict(scope["headers"]).get(b"x-api-key", b"")
        if not secrets.compare_digest(sent, self._key):
            # No WWW-Authenticate: Bearer would send OAuth-capable clients looking for an
            # authorization server that does not exist.
            body = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": UNAUTHORIZED_RPC,
                    "message": "Missing or invalid API key.",
                    "data": self._unauthorized,
                },
            }
            await JSONResponse(body, status_code=401)(scope, receive, send)
            return
        if scope["method"] != "POST":
            # Decided: 405 for GET (and DELETE), as the spec allows, because a stateless server has
            # neither server-to-client messages for a GET stream nor a session to delete. The
            # SDK would otherwise hold a GET open with nothing to send.
            await Response(status_code=405, headers={"Allow": "POST"})(scope, receive, send)
            return
        await self._manager.handle_request(scope, receive, send)
