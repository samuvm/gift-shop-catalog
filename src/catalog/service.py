"""One entry point per tool, shared by REST and MCP: arguments in, ADR-002 response body out.

Both transports call `execute`, so they cannot return different answers for the same call.
"""

import difflib
import math
from dataclasses import dataclass
from datetime import date
from typing import Any

from catalog.domain.catalog import Catalog, DetailsResult, Filters, ListResult, Sort
from catalog.domain.errors import CatalogError
from catalog.domain.models import Product
from catalog.tools import OCCASIONS, RECIPIENTS, TOOLS

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
# Query parameters with a closed set of values, read from the tool definitions: occasion and sort.
CHOICES: dict[str, list[str]] = {
    p.name: p.schema["enum"] for t in TOOLS for p in t.params if p.location == "query" and "enum" in p.schema
}


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


class InvalidParameter(CatalogError):
    code = "invalid_parameter"


def _choice(name: str, value: Any, allowed: list[str]) -> str:
    """One value of a closed set, in any case: 'Birthday' is 'birthday'. Anything else is an error
    that lists the allowed values, so the model can correct itself."""
    key = str(value).strip().lower()
    if key in allowed:
        return key
    raise InvalidParameter(
        f"{name}: {str(value)!r} is not an allowed value.",
        f"Use one of allowed_values for {name}, or leave it out.",
        allowed_values=allowed,
        did_you_mean=difflib.get_close_matches(key, allowed, n=2),
    )


def normalise(args: dict[str, Any]) -> dict[str, Any]:
    """Read the arguments the same way for every transport, before the domain sees them.

    Decided: values of a closed set are matched in any case and with surrounding spaces, because a
    model that writes 'Birthday' or 'HER' has made no mistake worth a round trip; the spec still
    advertises the lower-case values. A blank value means the filter was left out, as for query and
    exclude. Empty items in a recipient list ('her,', 'her,,couple') are dropped, because they carry
    no meaning and the list stays exactly what the model asked for. Non-finite prices and a price range
    that is upside down are errors: no product can match them, and an empty answer would read as
    'the shop has nothing'.
    """
    out = dict(args)
    for name, allowed in CHOICES.items():
        value = out.get(name)
        if value is not None:
            out[name] = _choice(name, value, allowed) if str(value).strip() else None
    recipient = out.get("recipient")
    if recipient is not None:
        items = recipient.split(",") if isinstance(recipient, str) else list(recipient)
        chosen = [_choice("recipient", r, RECIPIENTS) for r in items if str(r).strip()]
        out["recipient"] = list(dict.fromkeys(chosen))
    for name in ("min_price", "max_price"):
        price = out.get(name)
        if price is not None and not math.isfinite(price):
            raise InvalidParameter(
                f"{name}: {price} is not a finite number.",
                f"Pass {name} as a number in EUR, or leave it out.",
            )
    low, high = out.get("min_price"), out.get("max_price")
    if low is not None and high is not None and low > high:
        raise InvalidParameter(
            f"min_price ({low:g}) is above max_price ({high:g}).",
            "Swap the two values, or leave one of them out.",
        )
    return out


def _filters(args: dict[str, Any]) -> Filters:
    exclude = [t.strip().lower() for t in (args.get("exclude") or "").split(",") if t.strip()]
    return Filters(
        min_price=args.get("min_price"),
        max_price=args.get("max_price"),
        recipient=args.get("recipient") or [],
        occasion=args.get("occasion"),
        max_shipping_days=args.get("max_shipping_days"),
        exclude=exclude,
        include_out_of_stock=bool(args.get("include_out_of_stock")),
    )


def execute(ctx: Context, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """Run one tool. Raises CatalogError for recoverable problems; the transport maps it to its format."""
    args = normalise(args)
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
