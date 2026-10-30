"""The four tools' semantics over the cleaned catalogue (ADR-002). Pure: no I/O, no web framework."""

import difflib
import re
from collections.abc import Callable, Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from catalog.domain.errors import ProductNotFound, UnknownCategory, UnknownSubcategory
from catalog.domain.models import Product
from catalog.domain.text import query_terms, words

Sort = Literal["relevance", "rating", "popularity", "price_asc", "price_desc"]

DEFAULT_LIMIT = 5
MAX_LIMIT = 10
MAX_OUT_OF_STOCK = 3
MAX_OVER_BUDGET = 2
MAX_SUGGESTIONS = 3
MAX_ALTERNATIVES = 3

# Where a query term hits, and how much that hit is worth. The best field per term counts.
FIELD_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("name", 3.0),
    ("subcategory", 2.0),
    ("tags", 2.0),
    ("category", 1.5),
    ("occasions", 1.5),
    ("material", 1.5),
    ("color", 1.5),
    ("brand", 1.5),
    ("description", 1.0),
)
# Descriptions name materials to compare or deny them ("the everyday version of the alpaca").
EXCLUDE_FIELDS = ("name", "subcategory", "tags", "material")
# Filters a suggestion may relax, in the order ties are broken.
RELAXABLE = ("min_price", "max_price", "recipient", "occasion", "max_shipping_days", "exclude")
_ID = re.compile(r"\s*([A-Za-z]{2})\s*-?\s*(\d{1,3})\s*")


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Filters(_Model):
    min_price: float | None = None
    max_price: float | None = None
    recipient: str | None = None
    occasion: str | None = None
    max_shipping_days: int | None = None
    exclude: list[str] = Field(default_factory=list)
    include_out_of_stock: bool = False

    def active(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v not in (None, [], False)}


class Ref(_Model):
    product_id: str
    name: str
    price_eur: float


class OverBudget(Ref):
    over_by_eur: float


class Suggestion(_Model):
    change: str
    to: float | None
    would_match: int


class ListResult(_Model):
    products: list[Product]
    total_matches: int
    limit: int
    offset: int
    next_offset: int | None
    applied: dict[str, Any]
    out_of_stock_matches: list[Ref] = Field(default_factory=list)
    over_budget_matches: list[OverBudget] = Field(default_factory=list)
    unmatched_terms: list[str] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SubcategorySummary(_Model):
    name: str
    products: int
    in_stock: int


class CategorySummary(_Model):
    name: str
    slug: str
    products: int
    in_stock: int
    price_min_eur: float
    price_max_eur: float
    subcategories: list[SubcategorySummary]


class DetailsResult(_Model):
    product: Product
    in_stock_alternatives: list[Product]
    notes: list[str] = Field(default_factory=list)


def in_stock(p: Product) -> bool:
    return p.availability != "out_of_stock"


def _field_words(p: Product, field: str) -> set[str]:
    value = getattr(p, field)
    return words(" ".join(value) if isinstance(value, list) else str(value or ""))


def _passes(p: Product, f: Filters, skip: str | None = None) -> bool:
    checks: dict[str, Callable[[], bool]] = {
        "min_price": lambda: f.min_price is None or p.price_eur >= f.min_price,
        "max_price": lambda: f.max_price is None or p.price_eur <= f.max_price,
        "recipient": lambda: f.recipient is None or p.recipient in (f.recipient, "anyone"),
        "occasion": lambda: f.occasion is None or f.occasion in p.occasions,
        "max_shipping_days": lambda: f.max_shipping_days is None or p.shipping_days <= f.max_shipping_days,
        "exclude": lambda: not any(term in _exclusion_text(p) for term in f.exclude),
    }
    return all(check() for name, check in checks.items() if name != skip)


def _exclusion_text(p: Product) -> str:
    return " ".join([p.name, p.subcategory, " ".join(p.tags), p.material or ""]).lower()


class Catalog:
    def __init__(self, products: list[Product]) -> None:
        self._products = sorted(products, key=lambda p: p.product_id)
        self._by_id = {p.product_id: p for p in self._products}
        self._names = {p.category_slug: p.category for p in self._products}
        self._field_words = {
            p.product_id: {f: _field_words(p, f) for f, _ in FIELD_WEIGHTS} for p in products
        }

    # ---------- get_categories

    def categories(self) -> list[CategorySummary]:
        out = []
        for slug in sorted(self._names):
            ps = [p for p in self._products if p.category_slug == slug]
            subs = sorted({p.subcategory for p in ps})
            out.append(
                CategorySummary(
                    name=self._names[slug],
                    slug=slug,
                    products=len(ps),
                    in_stock=sum(map(in_stock, ps)),
                    price_min_eur=min(p.price_eur for p in ps),
                    price_max_eur=max(p.price_eur for p in ps),
                    subcategories=[
                        SubcategorySummary(
                            name=s,
                            products=sum(p.subcategory == s for p in ps),
                            in_stock=sum(in_stock(p) for p in ps if p.subcategory == s),
                        )
                        for s in subs
                    ],
                )
            )
        return out

    def resolve_category(self, value: str) -> str:
        """Slug, name in any spelling, or one distinctive word ("kitchen")."""
        key = re.sub(r"\s+", " ", value.strip().lower()).replace(" and ", " & ")
        for slug, name in self._names.items():
            if key in (slug, name.lower()):
                return slug
        hits = [s for s, n in self._names.items() if key in words(n) or key in s.split("-")]
        if len(hits) == 1:
            return hits[0]
        allowed = sorted(self._names)
        guesses = difflib.get_close_matches(key, allowed + [n.lower() for n in self._names.values()], n=3)
        did_you_mean = sorted({g if g in allowed else self._slug_of(g) for g in guesses})
        raise UnknownCategory(
            f"No category matches {value!r}.",
            "Use one of allowed_values, or call get_categories.",
            allowed_values=allowed,
            did_you_mean=did_you_mean,
        )

    def _slug_of(self, lowered_name: str) -> str:
        return next(s for s, n in self._names.items() if n.lower() == lowered_name)

    # ---------- get_products_by_category

    def browse(
        self,
        category: str,
        subcategory: str | None = None,
        filters: Filters | None = None,
        sort: Sort | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> ListResult:
        slug = self.resolve_category(category)
        notes = [] if category == slug else [f"Read category {category!r} as {self._names[slug]}."]
        pool = [p for p in self._products if p.category_slug == slug]
        applied: dict[str, Any] = {"category": slug}
        if subcategory is not None:
            subs = {p.subcategory.lower(): p.subcategory for p in pool}
            if subcategory.strip().lower() not in subs:
                raise UnknownSubcategory(
                    f"{self._names[slug]} has no subcategory {subcategory!r}.",
                    "Use one of allowed_values, or leave subcategory out.",
                    allowed_values=sorted(subs.values()),
                )
            applied["subcategory"] = subs[subcategory.strip().lower()]
            pool = [p for p in pool if p.subcategory == applied["subcategory"]]
        return self._list(pool, None, filters or Filters(), sort, limit, offset, applied, notes)

    # ---------- search_products

    def search(
        self,
        query: str | None,
        filters: Filters | None = None,
        sort: Sort | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> ListResult:
        pool = [p for p in self._products if p.search_primary]
        terms = query_terms(query)
        applied: dict[str, Any] = {"query": query} if query else {}
        result = self._list(pool, terms or None, filters or Filters(), sort, limit, offset, applied, [])
        unmatched = [t for t in terms if not any(self._score(p, [t]) for p in pool)]
        return result.model_copy(update={"unmatched_terms": unmatched}) if unmatched else result

    # ---------- get_product_details

    def details(self, product_id: str) -> DetailsResult:
        pid = self.normalise_id(product_id)
        product = self._by_id.get(pid)
        if product is None:
            raise ProductNotFound(
                f"No product with id {product_id!r}.",
                "Product ids look like 'KD-001'. To find a product by name or description, "
                "use search_products.",
                did_you_mean=self._guess_ids(product_id),
            )
        notes = [] if pid == product_id else [f"Read product id {product_id!r} as {pid}."]
        alternatives = [] if in_stock(product) else self._alternatives(product)
        return DetailsResult(product=product, in_stock_alternatives=alternatives, notes=notes)

    @staticmethod
    def normalise_id(value: str) -> str:
        m = _ID.fullmatch(value)
        return f"{m.group(1).upper()}-{int(m.group(2)):03d}" if m else value.strip()

    def _guess_ids(self, value: str) -> list[str]:
        terms = query_terms(value)
        by_name = [
            p.product_id
            for p in self._products
            if p.search_primary and terms and all(t in self._field_words[p.product_id]["name"] for t in terms)
        ]
        if by_name:
            return by_name[:3]
        target = self.normalise_id(value)
        close = [(-difflib.SequenceMatcher(None, target, pid).ratio(), pid) for pid in self._by_id]
        return [pid for neg_ratio, pid in sorted(close) if -neg_ratio >= 0.6][:3]

    def _alternatives(self, product: Product) -> list[Product]:
        twins = {product.product_id, *product.also_listed_as}
        candidates = [
            p for p in self._products if p.search_primary and in_stock(p) and p.product_id not in twins
        ]

        def closest(ps: Iterable[Product]) -> list[Product]:
            return sorted(ps, key=lambda p: (abs(p.price_eur - product.price_eur), p.product_id))

        same_category = [p for p in candidates if p.category_slug == product.category_slug]
        same_sub = closest(p for p in same_category if p.subcategory == product.subcategory)
        rest = closest(p for p in same_category if p.subcategory != product.subcategory)
        return (same_sub + rest)[:MAX_ALTERNATIVES]

    # ---------- shared list logic

    def _score(self, p: Product, terms: list[str]) -> float:
        fields = self._field_words[p.product_id]
        return sum(max((w for f, w in FIELD_WEIGHTS if t in fields[f]), default=0.0) for t in terms)

    @staticmethod
    def _rank(p: Product, score: float, sort: Sort) -> tuple[Any, ...]:
        rating = p.rating if p.rating is not None else -1.0
        reviews = p.reviews_count or 0
        keys: dict[Sort, tuple[float, ...]] = {
            "relevance": (-score, -rating, -reviews),
            "rating": (-rating, -reviews),
            "popularity": (-reviews, -rating),
            "price_asc": (p.price_eur, -rating),
            "price_desc": (-p.price_eur, -rating),
        }
        return (*keys[sort], p.product_id)

    def _list(
        self,
        pool: list[Product],
        terms: list[str] | None,
        f: Filters,
        sort: Sort | None,
        limit: int,
        offset: int,
        applied: dict[str, Any],
        notes: list[str],
    ) -> ListResult:
        if limit > MAX_LIMIT:
            notes = [*notes, f"limit {limit} is above the maximum; returned at most {MAX_LIMIT}."]
        limit, offset = max(1, min(limit, MAX_LIMIT)), max(0, offset)
        order: Sort = sort or ("relevance" if terms else "rating")
        scored = [(p, self._score(p, terms)) for p in pool] if terms else [(p, 0.0) for p in pool]
        if terms:
            scored = [(p, s) for p, s in scored if s > 0]

        def matching(skip: str | None = None) -> list[tuple[Product, float]]:
            return [
                (p, s) for p, s in scored if _passes(p, f, skip) and (f.include_out_of_stock or in_stock(p))
            ]

        hits = sorted(matching(), key=lambda ps: self._rank(ps[0], ps[1], order))
        page = hits[offset : offset + limit]
        short = len(page) < limit

        out_of_stock: list[Ref] = []
        if not f.include_out_of_stock and (terms or short):
            gone = sorted(
                ((p, s) for p, s in scored if _passes(p, f) and not in_stock(p)),
                key=lambda ps: self._rank(ps[0], ps[1], order),
            )
            out_of_stock = [_ref(p) for p, _ in gone[:MAX_OUT_OF_STOCK]]

        over_budget: list[OverBudget] = []
        if terms and f.max_price is not None:
            best = max((s for _, s in page), default=0.0)
            over = [(p, s) for p, s in matching(skip="max_price") if p.price_eur > f.max_price and s >= best]
            over.sort(key=lambda ps: (-ps[1], ps[0].price_eur, ps[0].product_id))
            over_budget = [
                OverBudget(**_ref(p).model_dump(), over_by_eur=round(p.price_eur - f.max_price, 2))
                for p, _ in over[:MAX_OVER_BUDGET]
            ]

        suggestions = self._suggestions(matching, f, len(hits)) if short else []
        return ListResult(
            products=[p for p, _ in page],
            total_matches=len(hits),
            limit=limit,
            offset=offset,
            next_offset=offset + limit if offset + limit < len(hits) else None,
            applied={**applied, **f.active(), **({"sort": sort} if sort else {})},
            out_of_stock_matches=out_of_stock,
            over_budget_matches=over_budget,
            suggestions=suggestions,
            notes=notes,
        )

    @staticmethod
    def _suggestions(
        matching: Callable[[str | None], list[tuple[Product, float]]], f: Filters, current: int
    ) -> list[Suggestion]:
        found = []
        for name in RELAXABLE:
            if getattr(f, name) in (None, []):
                continue
            freed = [p for p, _ in matching(name)]
            to: float | None = None
            if name == "max_price":
                above = [p.price_eur for p in freed if p.price_eur > (f.max_price or 0)]
                to = min(above) if above else None
                freed = [p for p in freed if to is not None and p.price_eur <= to]
            elif name == "min_price":
                below = [p.price_eur for p in freed if p.price_eur < (f.min_price or 0)]
                to = max(below) if below else None
                freed = [p for p in freed if to is not None and p.price_eur >= to]
            if len(freed) > current:
                found.append(Suggestion(change=name, to=to, would_match=len(freed)))
        found.sort(key=lambda s: (-s.would_match, RELAXABLE.index(s.change)))
        return found[:MAX_SUGGESTIONS]


def _ref(p: Product) -> Ref:
    return Ref(product_id=p.product_id, name=p.name, price_eur=p.price_eur)
