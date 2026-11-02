"""Build the level-1 golden set: tool + arguments -> exactly what the tool must return.

Each case states the behaviour it pins. Expected values come from `oracle.py` (ADR-002, ADR-005,
ADR-006, ADR-010 and ADR-011 semantics), then a person reviews every case in REVIEW.md against the catalogue
before the set is frozen. A case whose arguments and expected result are unchanged since the previous
version keeps its approval; every other case goes back to review, with the previous comment shown
next to it. A case still waiting for review, or deferred, carries the reviewer's last words forward.

Usage: uv run python evals/golden/l1/build.py   (writes v<VERSION>.jsonl and REVIEW.md next to this file)
"""

import json
import re
from pathlib import Path
from typing import Any

from oracle import TOOLS, load

HERE = Path(__file__).resolve().parent
VERSION = 6
# Who approved the previous version, for kept cases that do not already carry an approval.
REVIEWER, REVIEWED_AT = "Samuel Viciana", "2026-10-30"
C, B, S, D = "get_categories", "get_products_by_category", "search_products", "get_product_details"

# (tool, args, what the case pins). Order is the id order; ids are never reused.
CASES: list[tuple[str, dict[str, Any], str]] = [
    # --- get_categories
    (C, {}, "11 categories with listing counts, in-stock counts, price range and subcategories"),
    # --- browse: defaults and resolution
    (B, {"category": "kitchen-dining"}, "default page: in stock only, best rated first, 5 items"),
    (B, {"category": "Kitchen and Dining"}, "category name in another spelling resolves to the slug"),
    (B, {"category": "kitchen"}, "one distinctive word resolves to its category"),
    (B, {"category": "garden"}, "unknown category is a recoverable error that points to the right call"),
    (
        B,
        {"category": "home-living", "subcategory": "candles"},
        "subcategory filter, case-insensitive; out-of-stock candle reported",
    ),
    (
        B,
        {"category": "home-living", "subcategory": "Lamps"},
        "unknown subcategory is a recoverable error; the lamps are listed under Lighting",
    ),
    (
        B,
        {"category": "pets", "subcategory": "cats"},
        "the only cat product is out of stock: empty page, reported, not hidden",
    ),
    (
        B,
        {"category": "pets", "subcategory": "cats", "include_out_of_stock": True},
        "include_out_of_stock returns it",
    ),
    (B, {"category": "experiences"}, "Experiences holds only the two gift cards"),
    # --- browse: filters
    (B, {"category": "kitchen-dining", "max_price": 42}, "max_price is inclusive: KD-024 costs exactly 42"),
    (B, {"category": "kitchen-dining", "min_price": 50, "max_price": 70}, "price range"),
    (B, {"category": "jewellery", "recipient": "her"}, "recipient includes products for anyone"),
    (B, {"category": "home-living", "occasion": "housewarming", "max_price": 50}, "occasion plus price"),
    (B, {"category": "tech-gadgets", "max_shipping_days": 2}, "deadline filter"),
    (B, {"category": "beauty-wellness", "exclude": "scent,fragrance,candle"}, "exclusions by word"),
    (B, {"category": "kids", "max_price": 30}, "nothing under 30 in Kids: empty page and the filter to drop"),
    (
        B,
        {"category": "jewellery", "recipient": "her", "occasion": "anniversary", "max_price": 100},
        "strict filters return few: suggestion names the filter to drop",
    ),
    # --- browse: sorting and paging
    (B, {"category": "tech-gadgets", "sort": "price_asc"}, "cheapest first"),
    (B, {"category": "tech-gadgets", "sort": "price_desc"}, "most expensive first"),
    (B, {"category": "books-stationery", "sort": "popularity"}, "popularity is review count"),
    (B, {"category": "home-living", "limit": 5, "offset": 5}, "second page"),
    (B, {"category": "home-living", "limit": 25}, "limit above 10 is clamped to 10"),
    (
        B,
        {"category": "home-living", "limit": 10, "offset": 10},
        "second page of ten; cross-listed HL-021 appears in Home & Living under its HL id",
    ),
    (
        B,
        {"category": "kitchen-dining", "sort": "price_asc", "limit": 10},
        "cross-listed products appear in Kitchen & Dining under their KD ids",
    ),
    # --- search: the brief's scenarios
    (
        S,
        {"query": "chef knife", "max_price": 100},
        "specific request with no exact answer: the €149 chef's knife is reported over budget",
    ),
    (S, {"query": "chef knife"}, "the same request without a budget finds the chef's knife first"),
    (
        S,
        {"query": "city map jigsaw"},
        "a product asked for by name that is out of stock is reported, not hidden",
    ),
    (
        S,
        {"query": "fig candle"},
        "out-of-stock fig candle reported; the in-stock trio with a fig scent is returned",
    ),
    (S, {"query": "housewarming", "max_price": 50}, "an occasion word in the query matches tags and text"),
    (
        S,
        {"query": "sony noise cancelling headphones"},
        "a brand the shop does not sell is reported as unmatched",
    ),
    (S, {"query": "iphone"}, "nothing matches: empty, unmatched term, no invention"),
    (S, {"query": "cuchillo"}, "a non-English word matches nothing: the agent must translate"),
    (S, {"query": "asdfghjkl"}, "nonsense matches nothing"),
    # --- search: filters and ranking
    (S, {"query": "herb garden kit"}, "cross-listed product appears once, under its primary id"),
    (
        S,
        {"query": "amber glass tumbler"},
        "the second cross-listed product appears once, under its primary id",
    ),
    (S, {"query": "coffee", "max_price": 60}, "keyword plus budget across categories"),
    (
        S,
        {"query": "throw blanket", "exclude": "alpaca,wool,sheepskin"},
        "vegan-style exclusions on materials",
    ),
    (S, {"query": "puzzle", "sort": "price_asc"}, "explicit sort overrides relevance"),
    (S, {"query": "running"}, "a hobby word that lives in tags"),
    (S, {"query": "pasta"}, "pasta matches the pasta kit (the agent decides if the shopper meant money)"),
    (
        S,
        {"query": "candle", "include_out_of_stock": True},
        "include_out_of_stock mixes them into the ranking",
    ),
    (S, {"query": "travel", "recipient": "him", "max_shipping_days": 3}, "recipient plus deadline"),
    (
        S,
        {"query": "headphones", "max_price": 150},
        "every ANC option costs more than 150: over-budget matches",
    ),
    (
        S,
        {"query": "anniversary", "recipient": "her", "max_price": 100},
        "an occasion word in the query matches the occasion tags; better matches over budget are reported",
    ),
    # --- search: no query
    (S, {}, "no query: best rated in the whole catalogue"),
    (S, {"sort": "price_asc"}, "no query: the cheapest products in the catalogue"),
    (S, {"sort": "popularity", "limit": 3}, "no query: the most reviewed"),
    (S, {"recipient": "kids", "max_price": 40}, "no query, filters only"),
    (S, {"max_shipping_days": 0}, "same-day: only digital gift cards"),
    (S, {"max_price": 10}, "almost nothing under 10"),
    (S, {"min_price": 300}, "only the most expensive items"),
    # --- details
    (D, {"product_id": "KD-001"}, "an in-stock product: no alternatives block"),
    (D, {"product_id": "HL-004"}, "out of stock: in-stock alternatives from the same subcategory first"),
    (
        D,
        {"product_id": "PT-003"},
        "out of stock with no sibling in its subcategory: alternatives from its category",
    ),
    (D, {"product_id": "KD-007"}, "out-of-stock coffee product: alternatives closest in price"),
    (D, {"product_id": "kd-7"}, "tolerant id: lower case, no zero padding"),
    (D, {"product_id": "KD024"}, "tolerant id without dash; a cross-listed product resolves by either id"),
    (D, {"product_id": "EX-001"}, "unrated digital gift card"),
    (D, {"product_id": "XX-999"}, "unknown id is a recoverable error"),
    (D, {"product_id": "Chef's Knife"}, "a name instead of an id is a recoverable error"),
    # --- held out: registered after the first human review and before the relevance rules of
    # ADR-005 were written, so they test whether those rules generalise beyond the reviewed cases.
    (S, {"query": "wooden board game"}, "held out: three words; products matching more of them first"),
    (S, {"query": "scented gift", "recipient": "her", "max_price": 60}, "held out: word plus filters"),
    (S, {"query": "leather notebook"}, "held out: material word and product word"),
    (S, {"query": "tea set", "max_price": 50}, "held out: two common words under a budget"),
    (S, {"query": "wireless speaker", "max_price": 120}, "held out: product type with a budget"),
    (B, {"category": "outdoor-travel", "recipient": "him"}, "held out: recipient filter on a browse"),
    # --- held out: registered after the second human review and before the rules of ADR-006 were
    # written. The six above informed those rules, so these take over as the unseen cases.
    (S, {"query": "silver earrings", "max_price": 80}, "held out: material and product word, budget"),
    (S, {"query": "coffee grinder"}, "held out: the first word is itself a kind of product"),
    (S, {"query": "wooden toy", "recipient": "kids"}, "held out: material and product word, recipient"),
    (S, {"query": "travel pillow"}, "held out: a product word the catalogue may not use"),
    (
        B,
        {"category": "jewellery", "recipient": "her", "max_price": 60},
        "held out: browse, recipient and budget",
    ),
    (S, {"query": "anniversary", "recipient": "him,couple", "max_price": 120}, "held out: two recipients"),
    # --- after the held-out cases, so their ids stay as registered.
    (S, {"query": "anniversary", "recipient": "her,couple", "max_price": 100}, "a partner: her and couple"),
    # --- ADR-010: found by the platform's simulations and by running the tools in conversation tests.
    (S, {"query": "chef's knife"}, "an apostrophe in the query: the possessive reads as its word"),
    (S, {"query": "toy", "recipient": "kids", "max_price": 30}, "a dog toy is for a pet, not for kids"),
    (S, {"recipient": "pet"}, "a pet gets pet products only, not the ones for any person"),
    (
        S,
        {"query": "gardening", "recipient": "him", "max_price": 60},
        "the activity finds the Garden subcategory through a synonym",
    ),
    (
        S,
        {"query": "cooking", "recipient": "her", "max_price": 50},
        "the activity finds the cookbook, the herb kit and the kitchen aisle",
    ),
    (
        S,
        {"query": "tech gadget", "recipient": "kids", "max_price": 100},
        "a category word: the tech aisle, after the products that say tech",
    ),
    (S, {"query": "kitchen", "max_price": 60}, "a category word: the aisle after the product tagged kitchen"),
]


# Comments that ask for a different order or a semantic judgement on a result that did not change.
# Ranking is frozen (ADR-006): these go to the level-2 evaluation, which decides whether the agent
# recommends the wrong product because of them. They are shown, not counted as pending.
# l1-070 and l1-071 left this list in v6: ADR-011 changed their results as the reviewer asked.
DEFERRED = {
    "l1-038": "a sauna blanket listed for 'throw blanket'",
    "l1-044": "over-budget earbuds before the dearer headphones",
    "l1-049": "incense listed for kids: the client's data says 'anyone', a data issue, not a rule",
    "l1-062": "chess and backgammon expected higher as wooden board games: an order change",
    "l1-063": "incense as a scented gift",
    "l1-069": "a pepper mill for 'coffee grinder' (marked missing 'coffee')",
    "l1-080": "the tech aisle by rating before Home Tech for kids: an order change",
}


def previous() -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, str]]:
    """The previous version's cases, the reviewer's verdict on each, and the earlier comment its sheet
    carried forward (`*vN comment:* ...`), by case id."""
    cases_path, review_path = HERE / f"v{VERSION - 1}.jsonl", HERE / f"review-v{VERSION - 1}.md"
    cases = {c["id"]: c for c in map(json.loads, cases_path.read_text(encoding="utf-8").splitlines())}
    sheet = review_path.read_text(encoding="utf-8")
    sections = re.findall(r"^## (l1-\d+) (.*?)(?=^## |\Z)", sheet, re.M | re.S)
    comments, carried = {}, {}
    for cid, text in sections:
        if verdict := re.search(r"^Review: ?(.*?)$", text, re.M):
            comments[cid] = verdict.group(1)
        if earlier := re.search(r"^\*v\d+ comment:\*.*$", text, re.M):
            carried[cid] = earlier.group(0)
    return cases, comments, carried


def main() -> None:
    by_id = {p["product_id"]: p for p in load()}
    old_cases, old_comments, carried = previous()
    lines: list[str] = []
    pending: list[str] = []
    review = [
        f"# Level-1 golden set v{VERSION} · review sheet",
        "",
        "For each case: is the expected result what the tool *should* return for this catalogue?",
        "Mark `ok`, or write what is wrong. Prices in EUR; ✗ = out of stock.",
        f"Cases unchanged since v{VERSION - 1} keep their approval and are marked `ok (v{VERSION - 1})`.",
        "",
    ]
    for n, (tool, args, covers) in enumerate(CASES, start=1):
        cid = f"l1-{n:03d}"
        expect = TOOLS[tool](args)
        old = old_cases.get(cid)
        kept = (
            old is not None
            and (old["tool"], old["args"], old["expect"]) == (tool, args, expect)
            and re.match(r"ok\b", old_comments.get(cid, "").strip()) is not None
        )
        case = {
            "id": cid,
            "version": VERSION,
            "tool": tool,
            "args": args,
            "expect": expect,
            "covers": covers,
            "provenance": "llm_generated_reviewed_human",
            "reviewed_by": (old["reviewed_by"] or REVIEWER) if old and kept else None,
            "reviewed_at": (old["reviewed_at"] or REVIEWED_AT) if old and kept else None,
        }
        lines.append(json.dumps(case, ensure_ascii=False))
        review += [f"## {cid} · `{tool}` `{json.dumps(args, ensure_ascii=False)}`", f"*{covers}*", ""]
        if "categories" in expect:
            for slug, c in expect["categories"].items():
                subs = ", ".join(
                    f"{k} {v['in_stock']}/{v['products']}" for k, v in c["subcategories"].items()
                )
                review.append(
                    f"- **{slug}** {c['in_stock']}/{c['products']} in stock, "
                    f"€{c['price_min_eur']:g} to {c['price_max_eur']:g} · {subs}"
                )
        for key, value in expect.items():
            if key in ("categories",):
                continue
            if isinstance(value, list) and value and isinstance(value[0], str) and value[0] in by_id:
                review.append(f"- **{key}**:")
                review += [f"  - {_line(by_id[i])}" for i in value]
            elif key == "product_ids" and not value:
                review.append("- **product_ids**: *(none)*")
            else:
                review.append(f"- **{key}**: `{json.dumps(value, ensure_ascii=False)}`")
        if kept:
            review += ["", f"Review: ok (v{VERSION - 1})", ""]
            continue
        unchanged = old is not None and (old["tool"], old["args"], old["expect"]) == (tool, args, expect)
        verdict = old_comments.get(cid, "").strip()
        # Not reviewed yet, or deferred: the sheet's words are the reviewer's earlier comment, not a verdict.
        earlier = carried.get(cid) if verdict == "" or verdict.startswith("deferred") else None
        if unchanged and cid in DEFERRED and verdict:  # still deferred; never reviewed is still pending
            comment = earlier or f"*v{VERSION - 1} comment:* {verdict}"
            review += ["", comment, "", f"Review: deferred to level 2 (ADR-006 freeze): {DEFERRED[cid]}", ""]
            continue
        pending.append(cid)
        if old is None:
            review += ["", "*New in this version.*"]
        elif verdict == "" or verdict.startswith("deferred"):
            status = "deferred to level 2" if verdict else "not reviewed yet"
            changed = "" if unchanged else "; the expected result changed"
            review += ["", f"*In v{VERSION - 1}: {status}{changed}.*"] + (["", earlier] if earlier else [])
        elif verdict != "ok":
            review += ["", f"*v{VERSION - 1} comment:* {verdict}"]
        else:
            review += ["", f"*Approved in v{VERSION - 1}; the expected result changed.*"]
        review += ["", "Review: ", ""]
    (HERE / f"v{VERSION}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (HERE / "REVIEW.md").write_text("\n".join(review), encoding="utf-8")
    print(f"{len(lines)} cases -> v{VERSION}.jsonl · {len(pending)} to review: {', '.join(pending)}")


def _line(p: dict[str, Any]) -> str:
    stock = "✗ " if p["availability"] == "out_of_stock" else ""
    rating = f"★{p['rating']}" if p["rating"] is not None else "no reviews"
    return (
        f"{stock}`{p['product_id']}` {p['name']} · €{p['price_eur']:g} · {rating} "
        f"({p['reviews_count'] or 0}) · {p['recipient']} · ships {p['shipping_days']}d"
    )


if __name__ == "__main__":
    main()
