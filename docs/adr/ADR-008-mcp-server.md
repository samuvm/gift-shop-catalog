# ADR-008 · The MCP server: the same four tools over Streamable HTTP

- **Status:** accepted · 2026-11-01
- **Deciders:** Samuel Viciana
- **Related:** ADR-002 (one tool definition, two transports; `readOnlyHint`; errors as `isError`
  with the REST body), G-MCP-PARITY, G-MCP-CONFORMANCE, G-ARCH-LAYERS

## Context

The brief's bonus asks for an MCP server wrapping the same operations over Streamable HTTP. The
indigo.ai platform's MCP client documents only this: the full endpoint URL with its path and no
trailing slash, static headers for authentication (stored as workspace secrets), and no OAuth. It
does not say which protocol revision it speaks. The current revision (2026-07-28) dropped the
`initialize` handshake in favour of a version and capabilities envelope on every request; the
earlier ones (2024-11-05 to 2025-11-25) still start with `initialize`.

## Decision

**The official SDK (`mcp==2.3.0`), its low-level `Server`, served by the existing FastAPI app at
`/mcp`.** Hand-rolling JSON-RPC over HTTP would be a few hundred lines that then have to track two
protocol eras; the SDK already answers both (`initialize` for 2025-11-25 and earlier,
`server/discover` and the per-request envelope for 2026-07-28), picking the era from the
`MCP-Protocol-Version` header. The high-level `MCPServer` (formerly FastMCP) builds each tool's
schema from Python signatures; the low-level server takes them as data, so the tool list is
generated from `catalog.tools.TOOLS`, the same definitions the OpenAPI document is built from:

| MCP tool field | Source |
|---|---|
| `name`, `description` | the tool's name and description, as in the spec's `operationId` and `summary` |
| `inputSchema` | an object of the tool's parameters, each with its schema and description; `required` from the path parameters |
| `annotations` | `readOnlyHint: true`, `openWorldHint: false` |
| `outputSchema` | not declared: the response schemas use OpenAPI 3.0's `nullable`, which JSON Schema does not have |

Every `tools/call` goes through `catalog.service.execute`, as every REST route does. A result is
`structuredContent` = the REST body, plus one text block holding the same bytes REST sends
(compact JSON, UTF-8), so a model reads exactly the same thing over both transports. A
`CatalogError` is a tool result with `isError: true` and the REST error body. An unknown tool name
is a JSON-RPC error (-32602), because there is no tool to report an error from.

**Arguments are read as REST reads them.** FastAPI checks types, bounds and lengths before REST's
`execute`; over MCP, `jsonschema` checks the same against the advertised schema, minus what REST
leaves to the service: closed sets (`enum`, `pattern`) are matched in any case by
`service.normalise` and a wrong value is answered with `allowed_values`; a category in another
spelling is resolved by the domain; a `limit` above 10 is clamped with a note (ADR-002). A number
or boolean sent as a string (`"50"`, `"true"`) is read as a query string would be, and a `null`
argument means the filter was left out. A failed check is `isError` with an `invalid_parameter`
body carrying the same code, hint and `allowed_values` as REST's; only the message wording
differs (JSON Schema's instead of pydantic's), and it still starts with the parameter's name.
Rejected: moving the bounds into `service.normalise` so both transports share one check. REST
would still validate first in FastAPI, so the bounds would live in two places instead of one per
transport, and the route signatures are what the OpenAPI contract test holds against the spec.

**Stateless, JSON responses.** Each call is one read with one answer: there is no session to keep
and nothing for the server to push. So no `Mcp-Session-Id`, no SSE stream, and any replica can
answer any request. `GET /mcp` is a 405 (the spec allows it when there is no stream to offer),
because the SDK would otherwise hold an idle stream open.

**Authentication: the same `X-API-Key`, checked first.** A FastAPI dependency does not reach an
ASGI endpoint, so `/mcp` checks the header itself with the same constant-time comparison, before
reading the body. Without a valid key it answers HTTP 401 with a JSON-RPC error that has no id,
code -32001, and the REST 401 body in `data`. It sends no `WWW-Authenticate: Bearer`: an
OAuth-capable client would go looking for an authorization server that does not exist. DNS-rebinding
protection is off, because it only admits listed `Host` headers and the service is reached by a
public hostname; the key is what protects the endpoint.

**Wiring.** `catalog/api/mcp.py` holds the server and the endpoint and imports nothing from the
REST modules (a G-ARCH-LAYERS rule). `create_app` builds a new endpoint per app, because a session
manager runs only once, and starts it from the app's lifespan, because a mounted app's own
lifespan never runs. `/mcp` is a plain route, not a mount, so it answers without a redirect to
`/mcp/`. It is not part of the OpenAPI document.

**What parity means (G-MCP-PARITY).** For each of the 74 level-1 cases, the REST response and the
MCP `tools/call` with the same arguments and the same `today` must give: on success, the same
`structuredContent` as the REST JSON and the same text bytes; on error, `isError` and the REST
error body. The HTTP status is not compared by design: MCP reports a tool error inside a
successful JSON-RPC response. G-MCP-CONFORMANCE sends 16 protocol checks as raw HTTP, so the
result does not depend on any client library; one of them, the SDK's answer to an envelope that is
not a request, is -32602 rather than JSON-RPC's -32600 on the handshake-era path, and the check
accepts either.

## Consequences

- A tool's name, description or parameters change in one place and both transports follow; the
  contract tests and `make eval-mcp` fail if they ever answer differently.
- Two dependencies, pinned: `mcp` and `jsonschema` (which `mcp` already requires). `mcp` also
  brings `httpx2`, which Starlette's test client now prefers over `httpx`.
- The server speaks both protocol eras, so it does not depend on which revision the platform's
  client uses. Connecting it in the platform: the URL `https://<host>/mcp` and a static header
  `X-API-Key` whose value is a workspace secret.
- Tests and in-process evals must enter the app's lifespan (`with TestClient(app) as c:`);
  without it every MCP request fails, while REST keeps working.
