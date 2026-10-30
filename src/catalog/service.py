"""One entry point per tool, shared by REST and MCP: arguments in, ADR-002 response body out.

Both transports call `execute`, so they cannot return different answers for the same call.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from catalog.domain.catalog import Catalog, DetailsResult, Filters, ListResult, Sort
from catalog.domain.errors import CatalogError
from catalog.domain.models import Product
from catalog.tools import OCCASIONS, RECIPIENTS

ITEM_FIELDS = (
    "product_id",
    "name",
    "category",
    "subcategory",
    "price_eur",
    "availability",
    "rating",
    "reviews_count",
    "recipient",
    "occasions",
    "shipping_days",
    "gift_wrap",
    "description",
)
DETAIL_FIELDS = (*ITEM_FIELDS, "brand", "color", "material", "tags", "is_digital", "also_listed_as")


@dataclass(frozen=True)
class Context:
    catalog: Catalog
    catalog_version: str
    today: date


def item(p: Product) -> dict[str, Any]:
    return {f: getattr(p, f) for f in ITEM_FIELDS}


def full(p: Product) -> dict[str, Any]:
    return {**{f: getattr(p, f) for f in DETAIL_FIELDS}, "stock_units": p.stock}


def _meta(ctx: Context) -> dict[str, Any]:
    return {"today": ctx.today.isoformat(), "catalog_version": ctx.catalog_version}


def _with_missing(entry: dict[str, Any], r: ListResult) -> dict[str, Any]:
    lacking = r.missing_terms.get(entry["product_id"])
    return {**entry, "missing_terms": lacking} if lacking else entry


def list_body(r: ListResult, ctx: Context) -> dict[str, Any]:
    body: dict[str, Any] = {
        "products": [_with_missing(item(p), r) for p in r.products],
        "meta": {
            "total_matches": r.total_matches,
            "returned": len(r.products),
            "next_offset": r.next_offset,
            "applied": r.applied,
            **_meta(ctx),
        },
    }
    if r.out_of_stock_matches:
        body["out_of_stock_matches"] = [_with_missing(m.model_dump(), r) for m in r.out_of_stock_matches]
    if r.over_budget_matches:
        body["over_budget_matches"] = [_with_missing(m.model_dump(), r) for m in r.over_budget_matches]
    if r.unmatched_terms:
        body["unmatched_terms"] = r.unmatched_terms
    if r.suggestions:
        body["suggestions"] = [s.model_dump() for s in r.suggestions]
    if r.notes:
        body["note"] = " ".join(r.notes)
    return body


def details_body(d: DetailsResult, ctx: Context) -> dict[str, Any]:
    body: dict[str, Any] = {"product": full(d.product), "meta": _meta(ctx)}
    if d.in_stock_alternatives:
        body["in_stock_alternatives"] = [item(p) for p in d.in_stock_alternatives]
    if d.notes:
        body["note"] = " ".join(d.notes)
    return body


def categories_body(ctx: Context) -> dict[str, Any]:
    return {
        "categories": [c.model_dump() for c in ctx.catalog.categories()],
        "recipients": RECIPIENTS,
        "occasions": OCCASIONS,
        "meta": _meta(ctx),
    }


def error_body(err: CatalogError) -> dict[str, Any]:
    body: dict[str, Any] = {"code": err.code, "message": err.message, "hint": err.hint}
    if err.allowed_values:
        body["allowed_values"] = err.allowed_values
    if err.did_you_mean:
        body["did_you_mean"] = err.did_you_mean
    return {"error": body}


def _filters(args: dict[str, Any]) -> Filters:
    exclude = [t.strip().lower() for t in (args.get("exclude") or "").split(",") if t.strip()]
    return Filters(
        min_price=args.get("min_price"),
        max_price=args.get("max_price"),
        recipient=[r for r in (args.get("recipient") or "").split(",") if r.strip()],
        occasion=args.get("occasion"),
        max_shipping_days=args.get("max_shipping_days"),
        exclude=exclude,
        include_out_of_stock=bool(args.get("include_out_of_stock")),
    )


def execute(ctx: Context, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """Run one tool. Raises CatalogError for recoverable problems; the transport maps it to its format."""
    paging: dict[str, Any] = {"limit": args.get("limit") or 5, "offset": args.get("offset") or 0}
    sort: Sort | None = args.get("sort")
    if tool == "get_categories":
        return categories_body(ctx)
    if tool == "get_products_by_category":
        r = ctx.catalog.browse(args["category"], args.get("subcategory"), _filters(args), sort, **paging)
        return list_body(r, ctx)
    if tool == "search_products":
        return list_body(ctx.catalog.search(args.get("query"), _filters(args), sort, **paging), ctx)
    if tool == "get_product_details":
        return details_body(ctx.catalog.details(args["product_id"]), ctx)
    raise ValueError(f"unknown tool {tool!r}")
