"""Reference semantics of the four tools (ADR-002, ADR-005, ADR-006), written independently of the
service.

Stdlib only and reads the served catalogue directly. It exists to produce the expected answers
of the level-1 cases; the service is then checked against them. Two implementations that agree
are evidence; one that disagrees points at a bug in one of them, and the case says which is right.
"""

import difflib
import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "data" / "build" / "catalog.json"

DEFAULT_LIMIT, MAX_LIMIT = 5, 10
STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "for",
    "with",
    "of",
    "to",
    "in",
    "on",
    "at",
    "by",
    "from",
    "my",
    "his",
    "her",
    "him",
    "their",
    "our",
    "your",
    "me",
    "i",
    "it",
    "is",
    "that",
    "this",
    "some",
    "something",
    "any",
    "gift",
    "gifts",
    "present",
    "presents",
    "idea",
    "ideas",
}
# Where a query term hits, and how much that hit is worth (ADR-005). Category is not searched.
FIELD_WEIGHTS = (
    ("name", 3.0),
    ("subcategory", 2.0),
    ("tags", 2.0),
    ("occasions", 1.5),
    ("brand", 1.5),
    ("material", 1.5),
    ("color", 1.5),
    ("description", 1.0),
)
STRONG = {"name", "subcategory", "tags", "occasions", "brand"}
# Not the description: it names materials to compare or deny them ("the everyday version of the alpaca").
EXCLUDE_FIELDS = ("name", "subcategory", "tags", "material")
# An exclusion is a deliberate constraint, never suggested for removal (ADR-007).
REMOVABLE = ("min_price", "max_price", "recipient", "occasion", "max_shipping_days")

Product = dict[str, Any]


def load() -> list[Product]:
    products: list[Product] = json.loads(CATALOG.read_text(encoding="utf-8"))["products"]
    return products


def vocabulary() -> tuple[dict[str, str], dict[str, set[str]]]:
    """Phrases and synonym groups from the served catalogue, both keyed by normalised words."""
    search = json.loads(CATALOG.read_text(encoding="utf-8")).get("search") or {}
    phrases = {" ".join(split(k)): v for k, v in search.get("phrases", {}).items()}
    groups: dict[str, set[str]] = {}
    for group in search.get("synonyms", []):
        stems = {stem(w) for w in group}
        for w in stems:
            groups[w] = stems
    return phrases, groups


def generic() -> set[str]:
    """Packaging words ("set", "kit"): dropped from a query that has another word (ADR-006)."""
    search = json.loads(CATALOG.read_text(encoding="utf-8")).get("search") or {}
    return {stem(w) for w in search.get("generic", [])}


def stem(word: str) -> str:
    """English plural to singular, crudely: knives -> knife, glasses -> glass, accessories -> accessory."""
    if len(word) <= 3:
        return word
    for suffix, replacement in (("ies", "y"), ("ives", "ife"), ("ves", "f")):
        if word.endswith(suffix):
            return word[: -len(suffix)] + replacement
    if word.endswith(("sses", "xes", "zes", "ches", "shes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def split(text: str) -> list[str]:
    """Lowercase words. An apostrophe, straight or curly, is part of the word, never a break: a
    possessive 's goes ("chef's" -> chef), any other apostrophe is dropped ("don't" -> dont)."""
    out = []
    for raw in re.findall(r"[a-z0-9'\u2019]+", text.lower()):
        parts = raw.replace("\u2019", "'").split("'")
        kept = [w for i, w in enumerate(parts) if not (w == "s" and i > 0 and parts[i - 1])]
        if "".join(kept):
            out.append("".join(kept))
    return out


def words(text: str) -> set[str]:
    return {stem(w) for w in split(text)}


def terms(query: str | None) -> list[str]:
    every = all_terms(query)
    specific = [t for t in every if t not in generic()]
    return specific or every


def main_word(query: str | None) -> str | None:
    """With two or more words, the last specific one names the product (ADR-006, rule 1)."""
    every = all_terms(query)
    specific = [t for t in every if t not in generic()]
    return specific[-1] if len(every) >= 2 and specific else None


def all_terms(query: str | None) -> list[str]:
    phrases, _ = vocabulary()
    text = " ".join(split(query or ""))
    for phrase in sorted(phrases, key=lambda k: (-len(k), k)):
        text = re.sub(rf"\b{re.escape(phrase)}\b", phrases[phrase], text)
    seen: dict[str, None] = {}
    for w in text.split():
        if w not in STOPWORDS:
            seen.setdefault(stem(w), None)
    return list(seen)


def field_text(p: Product, field: str) -> str:
    value = p.get(field)
    return " ".join(value) if isinstance(value, list) else str(value or "")


def fields_hit(p: Product, term: str) -> list[tuple[str, float]]:
    _, groups = vocabulary()
    group = groups.get(term, {term})
    out = []
    for f, w in FIELD_WEIGHTS:
        found = words(field_text(p, f))
        if group & found:
            out.append((f, w if term in found else w / 2))  # a synonym alone counts half (ADR-006)
    return out


def match(p: Product, query_terms: list[str], df: dict[str, int], n: int) -> tuple[float, ...] | None:
    """(strong words, any words, rarity, score), or None when no word matches (ADR-005, rule 3)."""
    hits = {t: fields_hit(p, t) for t in query_terms}
    matched = [t for t in query_terms if hits[t]]
    if not matched:
        return None
    strong = sum(1 for t in matched if any(f in STRONG for f, _ in hits[t]))
    rarity = round(sum(math.log(n / df[t]) for t in matched), 9)
    score = sum(max(w for _, w in hits[t]) for t in matched)
    return (strong, len(matched), rarity, score)


def in_stock(p: Product) -> bool:
    return p["availability"] != "out_of_stock"


def passes(p: Product, a: dict[str, Any], skip: str | None = None) -> bool:
    def on(name: str) -> bool:
        return name != skip and a.get(name) is not None

    if on("min_price") and p["price_eur"] < a["min_price"]:
        return False
    if on("max_price") and p["price_eur"] > a["max_price"]:
        return False
    if on("recipient") and p["recipient"] not in (*recipients(a), "anyone"):
        return False
    if on("occasion") and a["occasion"] not in p["occasions"]:
        return False
    if on("max_shipping_days") and p["shipping_days"] > a["max_shipping_days"]:
        return False
    if on("exclude"):
        banned = [t.strip().lower() for t in a["exclude"].split(",") if t.strip()]
        text = " ".join(field_text(p, f) for f in EXCLUDE_FIELDS).lower()
        if any(t in text for t in banned):
            return False
    return True


NONE = (0, 0, 0.0, 0.0)


def recipients(a: dict[str, Any]) -> list[str]:
    """'her,couple' -> ['her', 'couple'] (ADR-006, rule 6)."""
    seen: dict[str, None] = {}
    for r in (a.get("recipient") or "").split(","):
        if r.strip():
            seen.setdefault(r.strip().lower(), None)
    return list(seen)


def rank_key(p: Product, m: tuple[float, ...], sort: str, wanted: list[str], tiered: bool) -> tuple[Any, ...]:
    rating = p["rating"] if p["rating"] is not None else -1.0
    reviews = p["reviews_count"] or 0
    exact = 1 if p["recipient"] in wanted else 0
    strong, anyw, rarity, s = m
    by = {
        "relevance": (-strong, -anyw, -exact, -rarity, -s, -rating, -reviews),
        "rating": (-exact, -rating, -reviews),
        "popularity": (-reviews, -rating),
        "price_asc": (p["price_eur"], -rating),
        "price_desc": (-p["price_eur"], -rating),
    }[sort]
    tier = (1 if strong == 0 else 0,) if tiered else ()
    return (*tier, *by, p["product_id"])


def _list(
    pool: list[Product], a: dict[str, Any], query_terms: list[str] | None, main: str | None = None
) -> dict[str, Any]:
    """Shared core of browse and search: filter, rank, page, and the information blocks."""
    if query_terms:
        df = {t: sum(1 for p in pool if fields_hit(p, t)) for t in query_terms}
        found = [(p, match(p, query_terms, df, len(pool))) for p in pool]
        scored = [(p, m) for p, m in found if m is not None]
        # The main word, when some product has it in a strong field, narrows the list (ADR-006).
        named = {p["product_id"] for p in pool if main and any(f in STRONG for f, _ in fields_hit(p, main))}
        if named:
            scored = [(p, m) for p, m in scored if p["product_id"] in named]
    else:
        scored = [(p, NONE) for p in pool]
    sort = a.get("sort") or ("relevance" if query_terms else "rating")
    # Exact recipient first only in the default orders (ADR-005, rule 7).
    recipient = recipients(a) if a.get("sort") in (None, "relevance") else []
    narrowed = bool(recipients(a) or a.get("occasion"))
    tiered = bool(query_terms) and sort != "relevance"

    def key(pm: tuple[Product, Any]) -> tuple[Any, ...]:
        return rank_key(pm[0], pm[1], sort, recipient, tiered)

    limit = min(a.get("limit") or DEFAULT_LIMIT, MAX_LIMIT)
    offset = a.get("offset") or 0
    want_oos = bool(a.get("include_out_of_stock"))

    def matching(skip: str | None = None) -> list[tuple[Product, float]]:
        return [(p, s) for p, s in scored if passes(p, a, skip) and (want_oos or in_stock(p))]

    hits = sorted(matching(), key=key)
    page = hits[offset : offset + limit]
    out: dict[str, Any] = {"product_ids": [p["product_id"] for p, _ in page], "total_matches": len(hits)}

    # Out-of-stock matches are news when the shopper asked for something, said who or what it is for
    # (ADR-006), or sees the last page.
    last_page = offset + limit >= len(hits)
    if not want_oos and (query_terms or narrowed or last_page):
        oos = sorted([(p, s) for p, s in scored if passes(p, a) and not in_stock(p)], key=key)
        if oos:
            out["out_of_stock_matches"] = [p["product_id"] for p, _ in oos[:3]]

    if (query_terms or narrowed) and a.get("max_price") is not None:
        best = max((s for _, s in page), default=NONE)
        over = [
            (p, s)
            for p, s in scored
            if passes(p, a, skip="max_price")
            and (want_oos or in_stock(p))
            and p["price_eur"] > a["max_price"]
            and s >= best
        ]
        # Best matches, then the recipients asked for, then the nearest above the budget.
        over.sort(
            key=lambda ps: (
                tuple(-x for x in ps[1]),
                0 if ps[0]["recipient"] in recipient else 1,
                ps[0]["price_eur"],
                ps[0]["product_id"],
            )
        )
        if over:
            out["over_budget_matches"] = [p["product_id"] for p, _ in over[:2]]

    if query_terms:  # for the page and for the near misses (ADR-006, ADR-007)
        by_id = {p["product_id"]: p for p in pool}
        shown = [
            *out["product_ids"],
            *out.get("over_budget_matches", []),
            *out.get("out_of_stock_matches", []),
        ]
        missing = {
            pid: [t for t in query_terms if not fields_hit(by_id[pid], t)] for pid in dict.fromkeys(shown)
        }
        if any(missing.values()):
            out["missing_terms"] = {k: v for k, v in missing.items() if v}

    if len(page) < limit:
        suggestions = []
        for f in (f for f in REMOVABLE if a.get(f) is not None):
            freed = [p for p, _ in matching(skip=f)]
            to: float | None = None
            if f == "max_price":  # the smallest raise that adds a result
                above = [p["price_eur"] for p in freed if p["price_eur"] > a["max_price"]]
                to = min(above) if above else None
                freed = [p for p in freed if to is not None and p["price_eur"] <= to]
            elif f == "min_price":  # the smallest drop that adds a result
                below = [p["price_eur"] for p in freed if p["price_eur"] < a["min_price"]]
                to = max(below) if below else None
                freed = [p for p in freed if to is not None and p["price_eur"] >= to]
            if len(freed) > len(hits):
                suggestions.append({"change": f, "to": to, "would_match": len(freed)})
        suggestions.sort(key=lambda g: (-g["would_match"], REMOVABLE.index(g["change"])))
        if suggestions:
            out["suggestions"] = suggestions[:3]
    return out


def get_categories() -> dict[str, Any]:
    ps = load()
    cats: dict[str, dict[str, Any]] = {}
    for p in ps:
        c = cats.setdefault(p["category_slug"], {"products": 0, "in_stock": 0, "prices": [], "subs": {}})
        c["products"] += 1
        c["in_stock"] += in_stock(p)
        c["prices"].append(p["price_eur"])
        sub = c["subs"].setdefault(p["subcategory"], [0, 0])
        sub[0] += 1
        sub[1] += in_stock(p)
    return {
        slug: {
            "products": c["products"],
            "in_stock": c["in_stock"],
            "price_min_eur": min(c["prices"]),
            "price_max_eur": max(c["prices"]),
            "subcategories": {k: {"products": v[0], "in_stock": v[1]} for k, v in sorted(c["subs"].items())},
        }
        for slug, c in sorted(cats.items())
    }


def get_products_by_category(a: dict[str, Any]) -> dict[str, Any]:
    ps = load()
    slug = resolve_category(a["category"], ps)
    if slug is None:
        guesses, hint = category_guesses(a["category"], ps)
        allowed = sorted({p["category_slug"] for p in ps})
        return {
            "error_code": "unknown_category",
            "allowed_values": allowed,
            "did_you_mean": guesses,
            "hint": hint,
        }
    pool = [p for p in ps if p["category_slug"] == slug]
    if a.get("subcategory"):
        subs = {p["subcategory"].lower() for p in pool}
        if a["subcategory"].lower() not in subs:
            # Where products named or tagged with the word asked for are listed (ADR-005, rule 5).
            asked = words(a["subcategory"])
            listed = {
                p["subcategory"] for p in pool if asked & (words(p["name"]) | words(" ".join(p["tags"])))
            }
            hint = (
                f"Call get_products_by_category with category {slug!r} and subcategory "
                f"{next(iter(listed))!r}."
                if len(listed) == 1
                else "Use one of allowed_values, or leave subcategory out."
            )
            return {
                "error_code": "unknown_subcategory",
                "allowed_values": sorted({p["subcategory"] for p in pool}),
                "did_you_mean": sorted(listed),
                "hint": hint,
            }
        pool = [p for p in pool if p["subcategory"].lower() == a["subcategory"].lower()]
    return _list(pool, a, None)


def search_products(a: dict[str, Any]) -> dict[str, Any]:
    ps = [p for p in load() if p["search_primary"]]
    query_terms = terms(a.get("query"))
    out = _list(ps, a, query_terms or None, main_word(a.get("query")))
    unmatched = [t for t in query_terms if not any(fields_hit(p, t) for p in ps)]
    if unmatched:
        out["unmatched_terms"] = unmatched
    return out


def get_product_details(a: dict[str, Any]) -> dict[str, Any]:
    ps = load()
    pid = normalise_id(a["product_id"])
    product = next((p for p in ps if p["product_id"] == pid), None)
    if product is None:
        return {
            "error_code": "product_not_found",
            "allowed_values": [],
            "did_you_mean": id_guesses(a["product_id"], ps),
            "hint": "Product ids look like 'KD-001'. To find a product by name or description, use "
            "search_products.",
        }
    out: dict[str, Any] = {"product_id": product["product_id"]}
    if not in_stock(product):
        twins = {product["product_id"], *product["also_listed_as"]}
        candidates = [p for p in ps if p["search_primary"] and in_stock(p) and p["product_id"] not in twins]

        def closeness(p: Product) -> tuple[float, str]:
            return (abs(p["price_eur"] - product["price_eur"]), p["product_id"])

        same_sub = sorted(
            [
                p
                for p in candidates
                if p["subcategory"] == product["subcategory"] and p["category"] == product["category"]
            ],
            key=closeness,
        )
        # Then the rest of the category: most tags in common, then closest in price (ADR-005, rule 8).
        tags = {t.lower() for t in product["tags"]}
        same_cat = sorted(
            [p for p in candidates if p["category"] == product["category"] and p not in same_sub],
            key=lambda p: (-len(tags & {t.lower() for t in p["tags"]}), *closeness(p)),
        )
        out["in_stock_alternatives"] = [p["product_id"] for p in (same_sub + same_cat)[:3]]
    return out


def resolve_category(value: str, ps: list[Product]) -> str | None:
    """Slug, name in any spelling, or a single distinctive word ("kitchen")."""
    key = re.sub(r"\s+", " ", value.strip().lower().replace(" and ", " & "))
    by_slug = {p["category_slug"]: p["category"] for p in ps}
    for slug, name in by_slug.items():
        if key in (slug, name.lower()):
            return slug
    hits = [slug for slug, name in by_slug.items() if key in words(name) or key in slug.split("-")]
    return hits[0] if len(hits) == 1 else None


def category_guesses(value: str, ps: list[Product]) -> tuple[list[str], str]:
    """A subcategory name points to its one category and names the call; otherwise the closest
    spellings."""
    key = re.sub(r"\s+", " ", value.strip().lower()).replace(" and ", " & ")
    owners = sorted(
        {(p["category_slug"], p["subcategory"]) for p in ps if words(p["subcategory"]) & words(key)}
    )
    if len({slug for slug, _ in owners}) == 1:
        slug, sub = owners[0]
        return [slug], f"Call get_products_by_category with category {slug!r} and subcategory {sub!r}."
    by_slug = {p["category_slug"]: p["category"] for p in ps}
    by_name = {name.lower(): slug for slug, name in by_slug.items()}
    close = difflib.get_close_matches(key, sorted(by_slug) + list(by_name), n=3)
    return sorted({by_name.get(c, c) for c in close}), "Use one of allowed_values, or call get_categories."


def id_guesses(value: str, ps: list[Product]) -> list[str]:
    """Products whose name holds every word given; otherwise ids that look alike."""
    asked = all_terms(value)
    by_name = [
        p["product_id"]
        for p in sorted(ps, key=lambda p: p["product_id"])
        if p["search_primary"] and asked and all(t in words(p["name"]) for t in asked)
    ]
    if by_name:
        return by_name[:3]
    target = normalise_id(value)
    ratios = sorted(
        (-difflib.SequenceMatcher(None, target, p["product_id"]).ratio(), p["product_id"]) for p in ps
    )
    return [pid for r, pid in ratios if -r >= 0.6][:3]


def normalise_id(value: str) -> str:
    m = re.fullmatch(r"\s*([A-Za-z]{2})\s*-?\s*(\d{1,3})\s*", value)
    return f"{m.group(1).upper()}-{int(m.group(2)):03d}" if m else value.strip()


TOOLS = {
    "get_categories": lambda a: {"categories": get_categories()},
    "get_products_by_category": get_products_by_category,
    "search_products": search_products,
    "get_product_details": get_product_details,
}
