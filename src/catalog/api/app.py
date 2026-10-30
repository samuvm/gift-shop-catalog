"""REST transport: FastAPI routes over `catalog.service.execute`, plus auth and error mapping."""

import os
import secrets
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Query, Request
from fastapi import Path as PathParam
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from catalog import __version__
from catalog.api import openapi
from catalog.domain.catalog import Catalog
from catalog.domain.errors import CatalogError
from catalog.service import Context, error_body, execute
from catalog.storage import read_catalog

ROOT = Path(__file__).resolve().parents[3]
STATUS = {"unknown_category": 404, "unknown_subcategory": 404, "product_not_found": 404}

Recipient = Literal["anyone", "him", "her", "couple", "kids"]
Occasion = Literal["birthday", "christmas", "anniversary", "housewarming", "thank-you", "graduation"]
SortParam = Literal["relevance", "rating", "popularity", "price_asc", "price_desc"]


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
    catalog = Catalog(products)
    zone = ZoneInfo(os.environ.get("SHOP_TIMEZONE", "Europe/Rome"))
    clock = today or (lambda: datetime.now(zone).date())

    def context() -> Context:
        return Context(catalog=catalog, catalog_version=version["products_sha256"][:8], today=clock())

    app = FastAPI(
        title="Gift Shop Catalog", version=__version__, openapi_url=None, docs_url=None, redoc_url=None
    )

    def require_key(request: Request) -> None:
        sent = request.headers.get("x-api-key", "")
        if not secrets.compare_digest(sent.encode(), api_key.encode()):
            raise Unauthorized

    @app.exception_handler(Unauthorized)
    async def unauthorized(_: Request, __: Unauthorized) -> JSONResponse:
        body = {
            "error": {
                "code": "unauthorized",
                "message": "Missing or invalid API key.",
                "hint": "Send the key in the X-API-Key header.",
            }
        }
        return JSONResponse(body, status_code=401)

    @app.exception_handler(CatalogError)
    async def catalog_error(_: Request, err: CatalogError) -> JSONResponse:
        return JSONResponse(error_body(err), status_code=STATUS.get(err.code, 400))

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, err: RequestValidationError) -> JSONResponse:
        problems = [f"{'.'.join(str(x) for x in e['loc'][1:])}: {e['msg']}" for e in err.errors()]
        body = {
            "error": {
                "code": "invalid_parameter",
                "message": "; ".join(problems),
                "hint": "Fix the parameter as described and call again. Allowed values are in the tool "
                "description.",
            }
        }
        return JSONResponse(body, status_code=400)

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
        min_price: Annotated[float | None, Query(ge=0)] = None,
        max_price: Annotated[float | None, Query(ge=0)] = None,
        recipient: Recipient | None = None,
        occasion: Occasion | None = None,
        max_shipping_days: Annotated[int | None, Query(ge=0, le=14)] = None,
        exclude: Annotated[str | None, Query(max_length=200)] = None,
        include_out_of_stock: bool = False,
        sort: SortParam | None = None,
        limit: Annotated[int, Query(ge=1)] = 5,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict[str, Any]:
        return execute(context(), "get_products_by_category", dict(locals()))

    @app.get("/products/search", dependencies=auth)
    def search_products(
        query: Annotated[str | None, Query(max_length=100)] = None,
        min_price: Annotated[float | None, Query(ge=0)] = None,
        max_price: Annotated[float | None, Query(ge=0)] = None,
        recipient: Recipient | None = None,
        occasion: Occasion | None = None,
        max_shipping_days: Annotated[int | None, Query(ge=0, le=14)] = None,
        exclude: Annotated[str | None, Query(max_length=200)] = None,
        include_out_of_stock: bool = False,
        sort: SortParam | None = None,
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
