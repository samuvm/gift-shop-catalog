"""The served OpenAPI document, generated from the tool definitions (ADR-002).

OpenAPI 3.0.3, every schema inline (no $ref, oneOf, anyOf, allOf) so the platform's form can edit
each operation. Examples are real responses computed from the served catalogue.
"""

from typing import Any

from catalog.service import Context, execute
from catalog.tools import ERROR_RESPONSE, TOOLS, Tool

EXAMPLE_ARGS: dict[str, dict[str, Any]] = {
    "get_categories": {},
    "get_products_by_category": {"category": "kitchen-dining", "max_price": 60, "limit": 2},
    "search_products": {"query": "chef knife", "max_price": 100, "limit": 2},
    "get_product_details": {"product_id": "KD-007"},
}
SERVICE_DESCRIPTION = (
    "Product catalogue of an online gift shop, exposed as four read-only tools for an AI shopping "
    "assistant. Prices are in EUR. Every call needs the header X-API-Key."
)


def _error(description: str, code: str, message: str, hint: str) -> dict[str, Any]:
    example = {"error": {"code": code, "message": message, "hint": hint}}
    return {
        "description": description,
        "content": {"application/json": {"schema": ERROR_RESPONSE, "example": example}},
    }


def _operation(tool: Tool, ctx: Context) -> dict[str, Any]:
    example = execute(ctx, tool.name, EXAMPLE_ARGS[tool.name])
    if tool.name == "get_categories":
        example = {**example, "categories": example["categories"][:2]}
    responses: dict[str, Any] = {
        "200": {
            "description": "OK",
            "content": {"application/json": {"schema": tool.response, "example": example}},
        },
        "400": _error(
            "A parameter is invalid.",
            "invalid_parameter",
            "max_price must be a number.",
            "Fix the parameter and call again.",
        ),
        "401": _error(
            "Missing or wrong X-API-Key.",
            "unauthorized",
            "Missing or invalid API key.",
            "Send the key in the X-API-Key header.",
        ),
    }
    if any(p.location == "path" for p in tool.params):
        responses["404"] = _error(
            "The category, subcategory or product does not exist. The body says what to use instead.",
            "unknown_category",
            "No category matches 'garden'.",
            "Use one of allowed_values, or call get_categories.",
        )
    return {
        "operationId": tool.name,
        "summary": tool.summary,
        "description": tool.description,
        "parameters": [
            {
                "name": p.name,
                "in": p.location,
                "required": p.required or p.location == "path",
                "description": p.description,
                "schema": p.schema,
            }
            for p in tool.params
        ],
        "responses": responses,
        "security": [{"ApiKey": []}],
    }


def build(ctx: Context, version: str) -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "Gift Shop Catalog", "version": version, "description": SERVICE_DESCRIPTION},
        "paths": {t.path: {"get": _operation(t, ctx)} for t in TOOLS},
        "components": {
            "securitySchemes": {
                "ApiKey": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "Documentation only: the platform sends the key from a secret.",
                }
            }
        },
    }
