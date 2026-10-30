"""The four tools' semantics over the cleaned catalogue (ADR-002). Pure: no I/O, no web framework."""

import difflib
import math
import re
from collections.abc import Callable, Iterable
from typing import Any, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from catalog.domain.errors import ProductNotFound, UnknownCategory, UnknownSubcategory
from catalog.domain.models import Product
from catalog.domain.text import Vocabulary, query_terms, words

Sort = Literal["relevance", "rating", "popularity", "price_asc", "price_desc"]

DEFAULT_LIMIT = 5
MAX_LIMIT = 10
MAX_OUT_OF_STOCK = 3
MAX_OVER_BUDGET = 2
MAX_SUGGESTIONS = 3
MAX_ALTERNATIVES = 3

# Where a query term hits, and how much that hit is worth. The best field per term counts (ADR-005).
# Strong fields say what the product is; weak ones only describe it. The category name is not
# searched: it would match a whole category, which get_products_by_category already lists.
STRONG_FIELDS: tuple[tuple[str, float], ...] = (
    ("name", 3.0),
    ("subcategory", 2.0),
    ("tags", 2.0),
    ("occasions", 1.5),
    ("brand", 1.5),
)
WEAK_FIELDS: tuple[tuple[str, float], ...] = (("material", 1.5), ("color", 1.5), ("description", 1.0))
FIELD_WEIGHTS = STRONG_FIELDS + WEAK_FIELDS
STRONG = frozenset(f for f, _ in STRONG_FIELDS)
# Descriptions name materials to compare or deny them ("the everyday version of the alpaca").
EXCLUDE_FIELDS = ("name", "subcategory", "tags", "material")
# Filters a suggestion may relax, in the order ties are broken.
# Not `exclude`: an exclusion is a deliberate constraint (vegan, allergic), never one to relax (ADR-007).
RELAXABLE = ("min_price", "max_price", "recipient", "occasion", "max_shipping_days")
_ID = re.compile(r"\s*([A-Za-z]{2})\s*-?\s*(\d{1,3})\s*")


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Filters(_Model):
    min_price: float | None = None
    max_price: float | None = None
    recipient: list[str] = Field(default_factory=list)
    occasion: str | None = None
    max_shipping_days: int | None = None
    exclude: list[str] = Field(default_factory=list)
    include_out_of_stock: bool = False

    @field_validator("recipient", mode="before")
    @classmethod
    def _split(cls, value: Any) -> Any:
        """'her, couple' or ['her', 'couple']: several recipients at once (ADR-006)."""
        if value is None:
            return []
        if isinstance(value, str):
            value = value.split(",")
        return list(dict.fromkeys(v.strip().lower() for v in value if v.strip()))

    def active(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v not in (None, [], False)}

    @property
    def narrowed(self) -> bool:
        """The shopper said who or what it is for: the blocks for near misses apply (ADR-006)."""
        return bool(self.recipient or self.occasion)


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
    missing_terms: dict[str, list[str]] = Field(default_factory=dict)
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


class Match(NamedTuple):
    """How well a product matches a query, as the ranking keys of ADR-005, best first."""

    strong: int = 0  # query words matched in a strong field
    any: int = 0  # query words matched in any field
    rarity: float = 0.0  # sum of ln(N / df) over the matched words
    score: float = 0.0  # best field weight per matched word, summed


NO_QUERY = Match()


def in_stock(p: Product) -> bool:
    return p.availability != "out_of_stock"


def _field_words(p: Product, field: str) -> set[str]:
    value = getattr(p, field)
    return words(" ".join(value) if isinstance(value, list) else str(value or ""))


def _passes(p: Product, f: Filters, skip: str | None = None) -> bool:
    checks: dict[str, Callable[[], bool]] = {
        "min_price": lambda: f.min_price is None or p.price_eur >= f.min_price,
        "max_price": lambda: f.max_price is None or p.price_eur <= f.max_price,
        "recipient": lambda: not f.recipient or p.recipient in (*f.recipient, "anyone"),
        "occasion": lambda: f.occasion is None or f.occasion in p.occasions,
        "max_shipping_days": lambda: f.max_shipping_days is None or p.shipping_days <= f.max_shipping_days,
        "exclude": lambda: not any(term in _exclusion_text(p) for term in f.exclude),
    }
    return all(check() for name, check in checks.items() if name != skip)


def _exclusion_text(p: Product) -> str:
    return " ".join([p.name, p.subcategory, " ".join(p.tags), p.material or ""]).lower()


class Catalog:
    def __init__(self, products: list[Product], vocabulary: Vocabulary | None = None) -> None:
        self._vocabulary = vocabulary or Vocabulary()
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
        owners = sorted(
            {(p.category_slug, p.subcategory) for p in self._products if words(p.subcategory) & words(key)}
        )
        if len({slug for slug, _ in owners}) == 1:
            slug, sub = owners[0]
            raise UnknownCategory(
                f"{value!r} is not a category; {sub} is a subcategory of {self._names[slug]}.",
                f"Call get_products_by_category with category {slug!r} and subcategory {sub!r}.",
                allowed_values=allowed,
                did_you_mean=[slug],
            )
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
                asked = words(subcategory)
                listed = {
                    p.subcategory
                    for p in pool
                    if asked
                    & (self._field_words[p.product_id]["name"] | self._field_words[p.product_id]["tags"])
                }
                hint = (
                    f"Call get_products_by_category with category {slug!r} and subcategory "
                    f"{next(iter(listed))!r}."
                    if len(listed) == 1
                    else "Use one of allowed_values, or leave subcategory out."
                )
                raise UnknownSubcategory(
                    f"{self._names[slug]} has no subcategory {subcategory!r}.",
                    hint,
                    allowed_values=sorted(subs.values()),
                    did_you_mean=sorted(listed),
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
        terms = self._vocabulary.terms(query)
        unmatched = [t for t in terms if not any(self._hits(p, t) for p in pool)]
        main = self._vocabulary.main_word(query)
        applied: dict[str, Any] = {"query": query} if query else {}
        f = filters or Filters()
        result = self._list(pool, terms or None, f, sort, limit, offset, applied, [], main)
        # For the near misses too: an over-budget "silver" pair that is vermeil must say so (ADR-007).
        listed = [
            *(p.product_id for p in result.products),
            *(r.product_id for r in result.over_budget_matches),
            *(r.product_id for r in result.out_of_stock_matches),
        ]
        missing = {
            pid: lacking
            for pid in dict.fromkeys(listed)
            if (lacking := [t for t in terms if not self._hits(self._by_id[pid], t)])
        }
        return result.model_copy(update={"unmatched_terms": unmatched, "missing_terms": missing})

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
        tags = {t.lower() for t in product.tags}
        rest = sorted(
            closest(p for p in same_category if p.subcategory != product.subcategory),
            key=lambda p: -len(tags & {t.lower() for t in p.tags}),
        )
        return (same_sub + rest)[:MAX_ALTERNATIVES]

    # ---------- shared list logic

    def _hits(self, p: Product, term: str) -> list[tuple[str, float]]:
        """The fields where a query word, or a synonym of it, appears in this product. A field that
        has only a synonym counts half (ADR-006): "earbuds" finds headphones, but earbuds first."""
        group = self._vocabulary.group(term)
        fields = self._field_words[p.product_id]
        return [(f, w if term in fields[f] else w / 2) for f, w in FIELD_WEIGHTS if fields[f] & group]

    def _matches(self, pool: list[Product], terms: list[str], main: str | None = None) -> dict[str, Match]:
        """Match per product. Rarity counts over the whole pool. With a main word that some product has
        in a strong field, only those products match (ADR-006)."""
        hits = {p.product_id: {t: self._hits(p, t) for t in terms} for p in pool}
        df = {t: sum(1 for h in hits.values() if h[t]) for t in terms}
        if main is not None:
            named = {p.product_id for p in pool if any(f in STRONG for f, _ in self._hits(p, main))}
            hits = {pid: h for pid, h in hits.items() if pid in named} if named else hits
        found = {}
        for pid, by_term in hits.items():
            matched = [t for t in terms if by_term[t]]
            if matched:
                found[pid] = Match(
                    strong=sum(1 for t in matched if any(f in STRONG for f, _ in by_term[t])),
                    any=len(matched),
                    rarity=round(sum(math.log(len(pool) / df[t]) for t in matched), 9),
                    score=sum(max(w for _, w in by_term[t]) for t in matched),
                )
        return found

    @staticmethod
    def _rank(p: Product, m: Match, sort: Sort, exact: bool, tiered: bool) -> tuple[Any, ...]:
        """Sort key. `exact`: the product is for exactly the recipient asked for. `tiered`: an explicit
        sort over a query, which still puts strong matches before weak-only ones."""
        rating = p.rating if p.rating is not None else -1.0
        reviews = p.reviews_count or 0
        keys: dict[Sort, tuple[float, ...]] = {
            "relevance": (-m.strong, -m.any, -exact, -m.rarity, -m.score, -rating, -reviews),
            "rating": (-exact, -rating, -reviews),
            "popularity": (-reviews, -rating),
            "price_asc": (p.price_eur, -rating),
            "price_desc": (-p.price_eur, -rating),
        }
        tier = (int(m.strong == 0),) if tiered else ()
        return (*tier, *keys[sort], p.product_id)

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
        main: str | None = None,
    ) -> ListResult:
        if limit > MAX_LIMIT:
            notes = [*notes, f"limit {limit} is above the maximum; returned at most {MAX_LIMIT}."]
        limit, offset = max(1, min(limit, MAX_LIMIT)), max(0, offset)
        order: Sort = sort or ("relevance" if terms else "rating")
        # Exact recipient first only in the default orders; an explicit sort is taken literally.
        recipient = f.recipient if order in ("relevance", "rating") and sort != "rating" else []
        tiered = bool(terms) and order != "relevance"
        found = self._matches(pool, terms, main) if terms else {p.product_id: NO_QUERY for p in pool}
        scored = [(p, found[p.product_id]) for p in pool if p.product_id in found]

        def key(pm: tuple[Product, Match]) -> tuple[Any, ...]:
            p, m = pm
            return self._rank(p, m, order, p.recipient in recipient, tiered)

        def matching(skip: str | None = None) -> list[tuple[Product, Match]]:
            return [
                (p, m) for p, m in scored if _passes(p, f, skip) and (f.include_out_of_stock or in_stock(p))
            ]

        hits = sorted(matching(), key=key)
        page = hits[offset : offset + limit]
        short = len(page) < limit
        next_offset = offset + limit if offset + limit < len(hits) else None

        out_of_stock: list[Ref] = []
        if not f.include_out_of_stock and (terms or f.narrowed or next_offset is None):
            gone = sorted(((p, m) for p, m in scored if _passes(p, f) and not in_stock(p)), key=key)
            out_of_stock = [_ref(p) for p, _ in gone[:MAX_OUT_OF_STOCK]]

        over_budget: list[OverBudget] = []
        if f.max_price is not None and (terms or f.narrowed):
            best = max((m for _, m in page), default=NO_QUERY)
            over = [(p, m) for p, m in matching(skip="max_price") if p.price_eur > f.max_price and m >= best]
            # The best matches first, then the recipients asked for (ADR-005 rule 7), then the nearest
            # above the budget.
            over.sort(
                key=lambda pm: (
                    tuple(-x for x in pm[1]),
                    -(pm[0].recipient in recipient),
                    pm[0].price_eur,
                    pm[0].product_id,
                )
            )
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
            next_offset=next_offset,
            applied={**applied, **f.active(), **({"sort": sort} if sort else {})},
            out_of_stock_matches=out_of_stock,
            over_budget_matches=over_budget,
            suggestions=suggestions,
            notes=notes,
        )

    @staticmethod
    def _suggestions(
        matching: Callable[[str | None], list[tuple[Product, Match]]], f: Filters, current: int
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
