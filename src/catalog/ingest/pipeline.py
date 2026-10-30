"""Raw export rows + decisions -> cleaned products, or a list of what a person must decide.

Pure: no file or network access. `catalog.ingest.__main__` does the I/O.
"""

import math
import re
from collections import Counter, defaultdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from catalog.domain.models import Availability, Product
from catalog.domain.text import stem, words
from catalog.ingest.decisions import Category, Decisions
from catalog.ingest.rules import (
    category_key,
    clean,
    looks_like_instruction,
    parse_number,
    parse_yes_no,
    split_multi,
)

EXPECTED_COLUMNS = (
    "product_id",
    "name",
    "category",
    "subcategory",
    "brand",
    "price_eur",
    "stock",
    "rating",
    "reviews_count",
    "recipient",
    "occasion",
    "tags",
    "color",
    "material",
    "gift_wrap",
    "shipping_days",
    "description",
)
REQUIRED = (
    "product_id",
    "name",
    "category",
    "subcategory",
    "brand",
    "price_eur",
    "stock",
    "recipient",
    "gift_wrap",
    "shipping_days",
    "description",
)
# Two IDs are the same product when every column except these is identical.
LISTING_COLUMNS = ("product_id", "category", "subcategory")
# Derived text is left out of the diff: it changes whenever its sources do.
NOT_DIFFED = ("search_text", "search_text_compact")
ID_PATTERN = re.compile(r"^[A-Z]{2}-\d{3}$")
# Free text that reaches the agent verbatim, checked for prompt-injection phrasing.
TEXT_COLUMNS = ("name", "subcategory", "brand", "tags", "color", "material", "description")


class _Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Anomaly(_Record):
    code: str
    product_ids: list[str]
    detail: str


class Finding(_Record):
    rule: str
    product_ids: list[str]
    detail: str


class Diff(_Record):
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    changed: dict[str, list[str]] = Field(default_factory=dict)


class IngestResult(_Record):
    status: Literal["ok", "stopped"]
    products: list[Product]
    anomalies: list[Anomaly]
    quality_warnings: list[Anomaly]
    rules_applied: list[Finding]
    decisions_applied: list[Finding]
    diff: Diff


class _Row(_Record):
    """One export row after the general rules, before cross-listing is resolved."""

    values: dict[str, str | None]
    category: Category
    price_eur: float
    stock: int
    rating: float | None
    reviews_count: int | None
    occasions: list[str]
    gift_wrap: bool
    shipping_days: int

    @property
    def product_id(self) -> str:
        return self.values["product_id"] or ""

    def signature(self) -> tuple[str | None, ...]:
        return tuple(v for k, v in self.values.items() if k not in LISTING_COLUMNS)


def run_ingest(
    rows: list[dict[str, str]],
    columns: list[str],
    decisions: Decisions,
    previous: list[Product] | None = None,
) -> IngestResult:
    missing = [c for c in EXPECTED_COLUMNS if c not in columns]
    unexpected = [c for c in columns if c not in EXPECTED_COLUMNS]
    if missing or unexpected:
        detail = f"missing columns: {missing or 'none'}; unexpected columns: {unexpected or 'none'}"
        return _stopped([Anomaly(code="schema_mismatch", product_ids=[], detail=detail)])

    anomalies: list[Anomaly] = []
    rules: dict[str, list[str]] = defaultdict(list)
    respellings: Counter[str] = Counter()
    parsed: list[_Row] = []
    categories = {category_key(c.name): c for c in decisions.categories}

    for raw in rows:
        values = {c: clean(raw.get(c)) for c in EXPECTED_COLUMNS}
        pid = values["product_id"] or "(no id)"
        for column in EXPECTED_COLUMNS:
            original = raw.get(column) or ""
            if original.strip() and values[column] != original:
                rules["whitespace_trimmed"].append(pid)
        row, row_anomalies, respelled = _parse_row(values, categories, decisions)
        anomalies.extend(row_anomalies)
        if respelled:
            rules["category_respelled"].append(pid)
            respellings[respelled] += 1
        if row is not None:
            parsed.append(row)

    seen = Counter(i for raw in rows if (i := clean(raw.get("product_id"))))
    for dup, n in sorted(seen.items()):
        if n > 1:
            anomalies.append(
                Anomaly(code="duplicate_id", product_ids=[dup], detail=f"{dup} appears {n} times")
            )

    listing_anomalies, warnings, applied, links, secondary = _resolve_cross_listings(parsed, decisions)
    anomalies.extend(listing_anomalies)

    products = sorted(
        (
            _to_product(r, decisions, links.get(r.product_id, []), r.product_id not in secondary)
            for r in parsed
        ),
        key=lambda p: p.product_id,
    )
    diff = _diff(previous, products)
    if previous and len(diff.removed) / len(previous) > decisions.removal_guard.max_removed_ratio:
        share = len(diff.removed) / len(previous)
        anomalies.append(
            Anomaly(
                code="mass_removal",
                product_ids=diff.removed,
                detail=f"{len(diff.removed)} of {len(previous)} products removed ({share:.0%}), "
                f"above the allowed {decisions.removal_guard.max_removed_ratio:.0%}",
            )
        )

    findings = [
        Finding(rule=k, product_ids=sorted(set(v)), detail=_rule_detail(k, respellings))
        for k, v in rules.items()
    ]
    applied.extend(_sentinel_findings(products, decisions))
    warnings.extend(_quality_warnings(products, decisions))
    status: Literal["ok", "stopped"] = "stopped" if anomalies else "ok"
    return IngestResult(
        status=status,
        products=products if status == "ok" else [],
        anomalies=anomalies,
        quality_warnings=warnings,
        rules_applied=sorted(findings, key=lambda f: f.rule),
        decisions_applied=applied,
        diff=diff,
    )


def _stopped(anomalies: list[Anomaly]) -> IngestResult:
    return IngestResult(
        status="stopped",
        products=[],
        anomalies=anomalies,
        quality_warnings=[],
        rules_applied=[],
        decisions_applied=[],
        diff=Diff(),
    )


def _parse_row(
    values: dict[str, str | None], categories: dict[str, Category], decisions: Decisions
) -> tuple[_Row | None, list[Anomaly], str | None]:
    """Apply the general rules to one row. Returns the row (or None), its anomalies, and a respelling."""
    pid = values["product_id"] or "(no id)"
    problems = [f"{c} is missing" for c in REQUIRED if values[c] is None]
    if values["product_id"] and not ID_PATTERN.match(values["product_id"]):
        problems.append(f"product_id {values['product_id']!r} is not in the form AA-000")

    def number[T: (int, float)](column: str, kind: type[T], low: float, high: float = math.inf) -> T | None:
        try:
            value = parse_number(values[column], kind)
        except ValueError as exc:
            problems.append(f"{column}: {exc}")
            return None
        if value is not None and not (low <= value <= high and math.isfinite(value)):
            problems.append(f"{column} {value} is outside [{low}, {high}]")
            return None
        return value

    price = number("price_eur", float, 0.01)
    stock = number("stock", int, 0)
    shipping = number("shipping_days", int, 0)
    rating = number("rating", float, 0, 5)
    reviews = number("reviews_count", int, 0)

    recipient = (values["recipient"] or "").lower()
    if values["recipient"] and recipient not in decisions.recipients:
        problems.append(f"recipient {values['recipient']!r} is not one of {decisions.recipients}")
    values["recipient"] = recipient or None
    occasions = split_multi(values["occasion"])
    if unknown := [o for o in occasions if o not in decisions.occasions]:
        problems.append(f"occasion {unknown} not in {decisions.occasions}")
    gift_wrap = parse_yes_no(values["gift_wrap"])
    if values["gift_wrap"] and gift_wrap is None:
        problems.append(f"gift_wrap {values['gift_wrap']!r} is not yes/no")

    anomalies: list[Anomaly] = []
    category, respelled = None, None
    if values["category"]:
        category = categories.get(category_key(values["category"]))
        if category is None:
            detail = f"{values['category']!r} matches none of the {len(categories)} canonical categories"
            anomalies.append(Anomaly(code="unknown_category", product_ids=[pid], detail=detail))
        else:
            if values["category"] != category.name:
                respelled = f"{values['category']!r} -> {category.name!r}"
            well_formed = bool(values["product_id"] and ID_PATTERN.match(values["product_id"]))
            if well_formed and not pid.startswith(f"{category.id_prefix}-"):
                detail = f"{pid} is in {category.name}, whose IDs start with {category.id_prefix}-"
                anomalies.append(Anomaly(code="prefix_mismatch", product_ids=[pid], detail=detail))

    if steering := [c for c in TEXT_COLUMNS if values[c] and looks_like_instruction(values[c] or "")]:
        detail = f"text aimed at a language model in {steering}; the agent reads product copy verbatim"
        anomalies.append(Anomaly(code="instruction_like_text", product_ids=[pid], detail=detail))
    if problems:
        anomalies.append(Anomaly(code="invalid_value", product_ids=[pid], detail="; ".join(problems)))
    if (
        anomalies
        or category is None
        or price is None
        or stock is None
        or shipping is None
        or gift_wrap is None
    ):
        return None, anomalies, respelled
    values["category"] = category.name
    row = _Row(
        values=values,
        category=category,
        price_eur=price,
        stock=stock,
        rating=rating,
        reviews_count=reviews,
        occasions=occasions,
        gift_wrap=gift_wrap,
        shipping_days=shipping,
    )
    return row, [], respelled


def _resolve_cross_listings(
    rows: list[_Row], decisions: Decisions
) -> tuple[list[Anomaly], list[Anomaly], list[Finding], dict[str, list[str]], set[str]]:
    """Match identical products under different IDs against the declared pairs."""
    anomalies: list[Anomaly] = []
    warnings: list[Anomaly] = []
    applied: list[Finding] = []
    links: dict[str, list[str]] = {}
    secondary: set[str] = set()

    groups: dict[tuple[str | None, ...], list[str]] = defaultdict(list)
    for row in rows:
        groups[row.signature()].append(row.product_id)
    identical = {frozenset(ids) for ids in groups.values() if len(set(ids)) > 1}
    declared = {frozenset(p.ids): p for p in decisions.cross_listed}
    by_id = {r.product_id: r for r in rows}

    for ids in sorted(identical - declared.keys(), key=sorted):
        detail = (
            "identical in every field except category; declare the pair in decisions.yaml or fix the export"
        )
        anomalies.append(Anomaly(code="undeclared_cross_listing", product_ids=sorted(ids), detail=detail))

    for key, pair in declared.items():
        present = [i for i in pair.ids if i in by_id]
        if not present:
            warnings.append(
                Anomaly(
                    code="unused_decision",
                    product_ids=sorted(pair.ids),
                    detail="declared cross-listing whose IDs are no longer in the export",
                )
            )
        elif len(present) < len(pair.ids):
            gone = sorted(set(pair.ids) - set(present))
            anomalies.append(
                Anomaly(
                    code="stale_decision",
                    product_ids=sorted(pair.ids),
                    detail=f"declared cross-listing, but {gone} is no longer in the export",
                )
            )
        elif key not in identical:
            first, *rest = (by_id[i] for i in pair.ids)
            differing = sorted(
                {
                    c
                    for r in rest
                    for c in EXPECTED_COLUMNS
                    if c not in LISTING_COLUMNS and r.values[c] != first.values[c]
                }
            )
            anomalies.append(
                Anomaly(
                    code="stale_decision",
                    product_ids=sorted(pair.ids),
                    detail=f"declared cross-listing, but the listings now differ in {differing}",
                )
            )
        else:
            for pid in pair.ids:
                links[pid] = sorted(i for i in pair.ids if i != pid)
            secondary.update(i for i in pair.ids if i != pair.primary)
            applied.append(
                Finding(
                    rule="cross_listed",
                    product_ids=sorted(pair.ids),
                    detail=f"one product, primary {pair.primary}: {pair.reason}",
                )
            )
    return anomalies, warnings, applied, links, secondary


def _to_product(row: _Row, decisions: Decisions, also_listed_as: list[str], primary: bool) -> Product:
    v = row.values
    tags = split_multi(v["tags"])
    attributes = [
        f"{v['name']}.",
        f"{v['subcategory']}, {row.category.name}.",
        f"Brand: {v['brand']}.",
        f"For: {v['recipient']}.",
        f"Occasions: {', '.join(row.occasions) or 'not given'}.",
        f"Tags: {', '.join(tags) or 'none'}.",
        f"Colour: {v['color'] or 'not given'}.",
        f"Material: {v['material'] or 'not given'}.",
    ]
    compact = " ".join(attributes)
    return Product(
        product_id=row.product_id,
        name=v["name"] or "",
        category=row.category.name,
        category_slug=row.category.slug,
        subcategory=v["subcategory"] or "",
        brand=v["brand"] or "",
        price_eur=row.price_eur,
        stock=row.stock,
        availability=_availability(row.stock, decisions),
        rating=row.rating,
        reviews_count=row.reviews_count,
        recipient=v["recipient"] or "",
        occasions=row.occasions,
        tags=tags,
        color=v["color"],
        material=v["material"],
        gift_wrap=row.gift_wrap,
        shipping_days=row.shipping_days,
        is_digital=row.shipping_days == decisions.shipping.digital_days,
        description=v["description"] or "",
        also_listed_as=also_listed_as,
        search_primary=primary,
        search_text=f"{compact} {v['description']}",
        search_text_compact=compact,
    )


def _availability(stock: int, decisions: Decisions) -> Availability:
    if stock == decisions.stock.unlimited_sentinel:
        return "unlimited"
    if stock == 0:
        return "out_of_stock"
    if stock <= decisions.stock.low_stock_max:
        return "low_stock"
    return "in_stock"


def _diff(previous: list[Product] | None, current: list[Product]) -> Diff:
    if previous is None:
        return Diff()
    before = {p.product_id: p.model_dump(exclude=set(NOT_DIFFED)) for p in previous}
    after = {p.product_id: p.model_dump(exclude=set(NOT_DIFFED)) for p in current}
    changed = {
        pid: sorted(k for k in after[pid] if after[pid][k] != before[pid][k])
        for pid in sorted(before.keys() & after.keys())
        if after[pid] != before[pid]
    }
    return Diff(
        added=sorted(after.keys() - before.keys()),
        removed=sorted(before.keys() - after.keys()),
        changed=changed,
    )


def _sentinel_findings(products: list[Product], decisions: Decisions) -> list[Finding]:
    unlimited = [p.product_id for p in products if p.availability == "unlimited"]
    digital = [p.product_id for p in products if p.is_digital]
    findings = []
    if unlimited:
        detail = f"stock {decisions.stock.unlimited_sentinel} read as unlimited, not as a count"
        findings.append(Finding(rule="unlimited_stock", product_ids=unlimited, detail=detail))
    if digital:
        detail = f"shipping_days {decisions.shipping.digital_days} read as digital delivery"
        findings.append(Finding(rule="digital_delivery", product_ids=digital, detail=detail))
    return findings


def _quality_warnings(products: list[Product], decisions: Decisions) -> list[Anomaly]:
    limit = decisions.quality.thin_description_max_chars
    checks = {
        "missing_rating": ([p.product_id for p in products if p.rating is None], "no rating or review count"),
        "missing_occasion": ([p.product_id for p in products if not p.occasions], "no occasion given"),
        "thin_description": (
            [p.product_id for p in products if len(p.description) <= limit],
            f"description of {limit} characters or fewer: says nothing about the product",
        ),
    }
    warnings = [
        Anomaly(code=code, product_ids=ids, detail=detail) for code, (ids, detail) in checks.items() if ids
    ]
    used = set().union(*(words(p.search_text) for p in products))
    warnings += [
        Anomaly(
            code="unused_synonym",
            product_ids=[],
            detail=f"synonym group {group} matches no product; remove it or check the spelling",
        )
        for group in decisions.search.synonyms
        if not used & {stem(w) for w in group}
    ]
    return warnings


def _rule_detail(rule: str, respellings: Counter[str]) -> str:
    if rule == "category_respelled":
        return "; ".join(f"{spelling} ({n})" for spelling, n in sorted(respellings.items()))
    return {"whitespace_trimmed": "leading, trailing or repeated whitespace removed"}.get(rule, "")
