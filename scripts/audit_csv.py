"""Audit the raw catalogue export and print every anomaly found, as JSON.

Stdlib only on purpose: this script is the independent look at the raw data that
ADR-001 is based on, so it must not share code with the service it informs.

Usage: python scripts/audit_csv.py data/gift-shop-catalog.csv
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ID_PATTERN = re.compile(r"^[A-Z]{2}-\d{3}$")
MULTI_VALUE = ("occasion", "tags")
NUMERIC = {"price_eur": float, "stock": int, "rating": float, "reviews_count": int, "shipping_days": int}


def audit(path: Path) -> dict:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    rows = list(csv.DictReader(text.splitlines()))
    columns = list(rows[0].keys())
    findings: dict = {
        "file": {
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": len(rows),
            "columns": columns,
            "has_bom": text.startswith("﻿"),
            "crlf": b"\r\n" in raw,
        },
    }

    # Whitespace and empties, per column.
    padded, empty = defaultdict(list), defaultdict(list)
    for r in rows:
        for c in columns:
            v = r[c] or ""
            if v != v.strip():
                padded[c].append({"product_id": r["product_id"], "value": v})
            if v.strip() == "":
                empty[c].append(r["product_id"])
    findings["padded_values"] = dict(padded)
    findings["empty_values"] = dict(empty)

    # IDs.
    ids = [r["product_id"].strip() for r in rows]
    findings["ids"] = {
        "bad_format": [i for i in ids if not ID_PATTERN.match(i)],
        "duplicated": [i for i, n in Counter(ids).items() if n > 1],
        "prefixes": dict(Counter(i[:2] for i in ids)),
    }

    # Category spellings and the canonical form they collapse to.
    def canon(v: str) -> str:
        return re.sub(r"\s+", " ", v.strip().lower().replace(" and ", " & "))

    spellings = Counter(r["category"] for r in rows)
    groups: dict[str, Counter] = defaultdict(Counter)
    for spelling, n in spellings.items():
        groups[canon(spelling)][spelling] += n
    findings["category_spellings"] = {k: dict(v) for k, v in sorted(groups.items())}
    findings["category_prefix_consistency"] = {
        k: dict(Counter(r["product_id"][:2] for r in rows if canon(r["category"]) == k)) for k in groups
    }

    # Subcategory spellings that differ only by case or whitespace.
    sub = defaultdict(set)
    for r in rows:
        sub[r["subcategory"].strip().lower()].add(r["subcategory"])
    findings["subcategory_variants"] = {k: sorted(v) for k, v in sub.items() if len(v) > 1}
    findings["subcategory_count"] = len(sub)

    # Numeric columns.
    numeric = {}
    for c, kind in NUMERIC.items():
        bad, values = [], []
        for r in rows:
            v = (r[c] or "").strip()
            if v == "":
                continue
            try:
                values.append(kind(v))
            except ValueError:
                bad.append({"product_id": r["product_id"], "value": v})
        numeric[c] = {"unparseable": bad, "min": min(values), "max": max(values), "n": len(values)}
    findings["numeric"] = numeric
    findings["stock_zero"] = [r["product_id"] for r in rows if (r["stock"] or "").strip() == "0"]
    findings["rating_without_reviews"] = [
        r["product_id"] for r in rows if bool(r["rating"].strip()) != bool(r["reviews_count"].strip())
    ]

    # Enumerations.
    for c in ("recipient", "gift_wrap", "color", "material", "brand"):
        findings[f"values_{c}"] = dict(Counter((r[c] or "").strip() for r in rows).most_common())
    for c in MULTI_VALUE:
        tokens = Counter()
        odd = []
        for r in rows:
            v = (r[c] or "").strip()
            if not v:
                continue
            parts = v.split("|")
            if any(p != p.strip() or p == "" for p in parts):
                odd.append({"product_id": r["product_id"], "value": v})
            tokens.update(p.strip().lower() for p in parts)
        findings[f"values_{c}"] = dict(tokens.most_common())
        findings[f"odd_separators_{c}"] = odd

    # Text lengths.
    for c in ("name", "description"):
        lengths = [len(r[c].strip()) for r in rows]
        findings[f"length_{c}"] = {
            "min": min(lengths),
            "max": max(lengths),
            "mean": round(sum(lengths) / len(lengths), 1),
        }

    # Same product listed under two IDs: identical on every field except id/category/subcategory.
    keyed = defaultdict(list)
    skip = {"product_id", "category", "subcategory"}
    for r in rows:
        keyed[tuple((c, (r[c] or "").strip()) for c in columns if c not in skip)].append(r["product_id"])
    findings["cross_listed"] = [ids for ids in keyed.values() if len(ids) > 1]
    names = Counter(r["name"].strip().lower() for r in rows)
    findings["repeated_names"] = {n: k for n, k in names.items() if k > 1}

    return findings


if __name__ == "__main__":
    print(json.dumps(audit(Path(sys.argv[1])), indent=2, ensure_ascii=False))
