"""Level-1 eval through the REST API (goals G-L1-EXACT, G-RESP-TOKENS-DEFAULT, G-RESP-TOKENS-MAX).

Every case is sent as an HTTP request with the API key, the JSON body is compared with the case's
expectation, and the body's size is counted in tokens exactly as the model would receive it.
Runs in-process by default; set CATALOG_URL and CATALOG_API_KEY to run it against a deployment.

Usage: uv run python evals/golden/l1/run.py
"""

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import tiktoken

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "evals" / "golden" / "l1" / "v2.jsonl"
REPORT = ROOT / "evals" / "reports" / "l1-latest.json"
ENCODING = tiktoken.get_encoding("o200k_base")
PATHS = {
    "get_categories": "/categories",
    "get_products_by_category": "/categories/{category}/products",
    "search_products": "/products/search",
    "get_product_details": "/products/{product_id}",
}


def url_for(tool: str, args: dict[str, Any]) -> str:
    params = dict(args)
    path = PATHS[tool]
    for name in ("category", "product_id"):
        if f"{{{name}}}" in path:
            path = path.replace(f"{{{name}}}", quote(str(params.pop(name)), safe=""))
    query = {k: str(v).lower() if isinstance(v, bool) else v for k, v in params.items()}
    return path + (f"?{urlencode(query)}" if query else "")


def summarise(tool: str, status: int, body: dict[str, Any]) -> dict[str, Any]:
    if status >= 400:
        return {"error_code": body["error"]["code"], "did_you_mean": body["error"].get("did_you_mean", [])}
    if tool == "get_categories":
        return {"categories": {c["slug"]: c for c in body["categories"]}}
    if tool == "get_product_details":
        out: dict[str, Any] = {"product_id": body["product"]["product_id"]}
        if "in_stock_alternatives" in body:
            out["in_stock_alternatives"] = [p["product_id"] for p in body["in_stock_alternatives"]]
        return out
    out = {
        "product_ids": [p["product_id"] for p in body["products"]],
        "total_matches": body["meta"]["total_matches"],
    }
    for key in ("out_of_stock_matches", "over_budget_matches"):
        if key in body:
            out[key] = [p["product_id"] for p in body[key]]
    for key in ("suggestions", "unmatched_terms"):
        if key in body:
            out[key] = body[key]
    return out


def matches(tool: str, got: dict[str, Any], expected: dict[str, Any]) -> bool:
    if tool != "get_categories":
        return got == expected
    for slug, e in expected["categories"].items():
        c = got["categories"].get(slug)
        subs = (
            {s["name"]: {"products": s["products"], "in_stock": s["in_stock"]} for s in c["subcategories"]}
            if c
            else {}
        )
        fields = ("products", "in_stock", "price_min_eur", "price_max_eur")
        if c is None or any(c[f] != e[f] for f in fields) or subs != e["subcategories"]:
            return False
    return True


def client() -> Any:
    if base := os.environ.get("CATALOG_URL"):
        import httpx

        return httpx.Client(base_url=base, headers={"X-API-Key": os.environ["CATALOG_API_KEY"]}, timeout=10)
    from fastapi.testclient import TestClient

    from catalog.api.app import create_app

    return TestClient(create_app("l1-eval"), headers={"X-API-Key": "l1-eval"})


def main() -> int:
    http = client()
    results = []
    for line in CASES.open(encoding="utf-8"):
        case = json.loads(line)
        response = http.get(url_for(case["tool"], case["args"]))
        got = summarise(case["tool"], response.status_code, response.json())
        page = case["args"].get("limit", 5)
        results.append(
            {
                "id": case["id"],
                "passed": matches(case["tool"], got, case["expect"]),
                "tokens": len(ENCODING.encode(response.text)),
                "is_list": "products" in response.text[:20],
                "page": min(page, 10),
                "got": got if not matches(case["tool"], got, case["expect"]) else None,
            }
        )
    lists = [r for r in results if r["is_list"]]
    report = {
        "exact_match_rate": sum(r["passed"] for r in results) / len(results),
        "n_cases": len(results),
        "max_tokens_default_page": max(r["tokens"] for r in lists if r["page"] <= 5),
        "max_tokens_max_page": max(r["tokens"] for r in lists if r["page"] == 10),
        "target": os.environ.get("CATALOG_URL", "in-process"),
        "failures": [r for r in results if not r["passed"]],
        "tokens_by_case": {r["id"]: r["tokens"] for r in results},
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for r in report["failures"]:
        print(f"  ✗ {r['id']}: got {json.dumps(r['got'])[:200]}")
    print(
        f"level 1: {sum(r['passed'] for r in results)}/{len(results)} exact · max tokens "
        f"default page {report['max_tokens_default_page']} · max page {report['max_tokens_max_page']} "
        f"-> {REPORT.relative_to(ROOT)}"
    )
    return 0 if not report["failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
