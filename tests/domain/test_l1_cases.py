"""Every level-1 case, run against the domain on the real catalogue.

The expectations come from an independent reference implementation (evals/golden/l1/oracle.py).
A failure here means the two disagree; the case says which behaviour the ADRs ask for.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from catalog.domain.catalog import Catalog, Filters, ListResult
from catalog.domain.errors import CatalogError
from catalog.storage import read_catalog, read_vocabulary

ROOT = Path(__file__).resolve().parents[2]
CASES = [json.loads(line) for line in (ROOT / "evals" / "golden" / "l1" / "v6.jsonl").open(encoding="utf-8")]
FILTER_KEYS = set(Filters.model_fields)


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    path = ROOT / "data" / "build" / "catalog.json"
    return Catalog(read_catalog(path)[1], read_vocabulary(path))


def run(catalog: Catalog, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    a = dict(args)
    raw = {k: a.pop(k) for k in list(a) if k in FILTER_KEYS}
    if "exclude" in raw:
        raw["exclude"] = [t.strip().lower() for t in raw["exclude"].split(",") if t.strip()]
    filters = Filters(**raw)
    paging = {k: a.pop(k) for k in ("sort", "limit", "offset") if k in a}
    try:
        if tool == "get_categories":
            return {"categories": {c.slug: c for c in catalog.categories()}}
        if tool == "get_product_details":
            d = catalog.details(a["product_id"])
            out: dict[str, Any] = {"product_id": d.product.product_id}
            if d.in_stock_alternatives:
                out["in_stock_alternatives"] = [p.product_id for p in d.in_stock_alternatives]
            return out
        if tool == "get_products_by_category":
            return summarise(catalog.browse(a["category"], a.get("subcategory"), filters, **paging))
        return summarise(catalog.search(a.get("query"), filters, **paging))
    except CatalogError as err:
        return {
            "error_code": err.code,
            "allowed_values": err.allowed_values,
            "did_you_mean": err.did_you_mean,
            "hint": err.hint,
        }


def summarise(r: ListResult) -> dict[str, Any]:
    out: dict[str, Any] = {
        "product_ids": [p.product_id for p in r.products],
        "total_matches": r.total_matches,
    }
    if r.out_of_stock_matches:
        out["out_of_stock_matches"] = [p.product_id for p in r.out_of_stock_matches]
    if r.over_budget_matches:
        out["over_budget_matches"] = [p.product_id for p in r.over_budget_matches]
    if r.suggestions:
        out["suggestions"] = [s.model_dump() for s in r.suggestions]
    if r.unmatched_terms:
        out["unmatched_terms"] = r.unmatched_terms
    if r.missing_terms:
        out["missing_terms"] = r.missing_terms
    return out


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_level_one_case(catalog: Catalog, case: dict[str, Any]) -> None:
    got = run(catalog, case["tool"], case["args"])
    expected = case["expect"]
    if case["tool"] == "get_categories":
        for slug, e in expected["categories"].items():
            c = got["categories"][slug]
            assert (c.products, c.in_stock, c.price_min_eur, c.price_max_eur) == (
                e["products"],
                e["in_stock"],
                e["price_min_eur"],
                e["price_max_eur"],
            )
            assert {s.name: {"products": s.products, "in_stock": s.in_stock} for s in c.subcategories} == e[
                "subcategories"
            ]
        return
    assert got == expected
