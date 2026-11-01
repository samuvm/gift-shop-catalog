"""REST transport: FastAPI routes over `catalog.service.execute`, plus auth and error mapping.

The MCP transport (`catalog.api.mcp`) is served by the same app at /mcp.
"""

import os
import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Query, Request
from fastapi import Path as PathParam
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from catalog import __version__
from catalog.api import mcp, openapi
from catalog.domain.catalog import Catalog
from catalog.domain.errors import CatalogError
from catalog.service import Context, InvalidParameter, error_body, execute
from catalog.storage import read_catalog, read_vocabulary

ROOT = Path(__file__).resolve().parents[3]
STATUS = {"unknown_category": 404, "unknown_subcategory": 404, "product_not_found": 404}

# occasion, sort and recipient are taken as plain strings: `service.normalise` matches them in any
# case and answers a wrong one with its allowed values, for REST and MCP alike.
Price = Annotated[float | None, Query(ge=0, allow_inf_nan=False)]  # nan and inf can match nothing
BOOLEAN_VALUES = ["true", "false"]
UNAUTHORIZED = {
    "error": {
        "code": "unauthorized",
        "message": "Missing or invalid API key.",
        "hint": "Send the key in the X-API-Key header.",
    }
}


class Unauthorized(Exception):
    pass


def create_app(
    api_key: str,
    catalog_path: Path = ROOT / "data" / "build" / "catalog.json",
    today: Callable[[], date] | None = None,
) -> FastAPI:
    if not api_key:
        raise ValueError("an API key is required; refusing to start an open service")
    version, products = read_catalog(catalog_path)
    catalog = Catalog(products, read_vocabulary(catalog_path))
    zone = ZoneInfo(os.environ.get("SHOP_TIMEZONE", "Europe/Rome"))
    clock = today or (lambda: datetime.now(zone).date())

    def context() -> Context:
        return Context(catalog=catalog, catalog_version=version["served_sha256"][:8], today=clock())

    # A new MCP endpoint per app, because its session manager can run only once; this app's
    # lifespan starts it (ADR-008).
    mcp_endpoint = mcp.Endpoint(context, api_key, UNAUTHORIZED)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with mcp_endpoint.run():
            yield

    app = FastAPI(
        title="Gift Shop Catalog",
        version=__version__,
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.router.routes.append(mcp_endpoint.route)

    def require_key(request: Request) -> None:
        sent = request.headers.get("x-api-key", "")
        if not secrets.compare_digest(sent.encode(), api_key.encode()):
            raise Unauthorized

    @app.exception_handler(Unauthorized)
    async def unauthorized(_: Request, __: Unauthorized) -> JSONResponse:
        return JSONResponse(UNAUTHORIZED, status_code=401)

    @app.exception_handler(CatalogError)
    async def catalog_error(_: Request, err: CatalogError) -> JSONResponse:
        return JSONResponse(error_body(err), status_code=STATUS.get(err.code, 400))

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, err: RequestValidationError) -> JSONResponse:
        problems = [f"{'.'.join(str(x) for x in e['loc'][1:])}: {e['msg']}" for e in err.errors()]
        if any(e["type"] == "bool_parsing" for e in err.errors()):
            hint, allowed = "Use one of allowed_values.", BOOLEAN_VALUES
        else:
            hint = (
                "Fix the parameter as described and call again. Allowed values are in the tool description."
            )
            allowed = None
        return JSONResponse(error_body(InvalidParameter("; ".join(problems), hint, allowed)), status_code=400)

    @app.get("/health", include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok", "catalog_version": context().catalog_version}

    @app.get("/openapi.json", include_in_schema=False)
    def spec() -> dict[str, Any]:
        return openapi.build(context(), __version__)

    auth = [Depends(require_key)]

    @app.get("/categories", dependencies=auth)
    def get_categories() -> dict[str, Any]:
        return execute(context(), "get_categories", {})

    @app.get("/categories/{category}/products", dependencies=auth)
    def get_products_by_category(
        category: Annotated[str, PathParam(max_length=50)],
        subcategory: Annotated[str | None, Query(max_length=50)] = None,
        min_price: Price = None,
        max_price: Price = None,
        recipient: Annotated[str | None, Query(max_length=40)] = None,
        occasion: str | None = None,
        max_shipping_days: Annotated[int | None, Query(ge=0, le=14)] = None,
        exclude: Annotated[str | None, Query(max_length=200)] = None,
        include_out_of_stock: bool = False,
        sort: str | None = None,
        limit: Annotated[int, Query(ge=1)] = 5,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict[str, Any]:
        return execute(context(), "get_products_by_category", dict(locals()))

    @app.get("/products/search", dependencies=auth)
    def search_products(
        query: Annotated[str | None, Query(max_length=100)] = None,
        min_price: Price = None,
        max_price: Price = None,
        recipient: Annotated[str | None, Query(max_length=40)] = None,
        occasion: str | None = None,
        max_shipping_days: Annotated[int | None, Query(ge=0, le=14)] = None,
        exclude: Annotated[str | None, Query(max_length=200)] = None,
        include_out_of_stock: bool = False,
        sort: str | None = None,
        limit: Annotated[int, Query(ge=1)] = 5,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict[str, Any]:
        return execute(context(), "search_products", dict(locals()))

    @app.get("/products/{product_id}", dependencies=auth)
    def get_product_details(product_id: Annotated[str, PathParam(max_length=20)]) -> dict[str, Any]:
        return execute(context(), "get_product_details", {"product_id": product_id})

    return app


def app_from_env() -> FastAPI:
    """Entry point for uvicorn (`--factory`): the key comes from the environment, never from the repo."""
    return create_app(os.environ.get("CATALOG_API_KEY", ""))
