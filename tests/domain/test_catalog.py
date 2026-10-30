"""Domain semantics of the four tools (ADR-002), on a small hand-built catalogue."""

from typing import Any

import pytest

from catalog.domain.catalog import Catalog, Filters
from catalog.domain.errors import ProductNotFound, UnknownCategory, UnknownSubcategory
from catalog.domain.models import Product
from catalog.domain.text import Vocabulary

CATEGORIES = {"home-living": "Home & Living", "kitchen-dining": "Kitchen & Dining", "pets": "Pets"}


def product(pid: str, **kw: Any) -> Product:
    prefix_to_slug = {"HL": "home-living", "KD": "kitchen-dining", "PT": "pets"}
    slug = kw.pop("category_slug", prefix_to_slug[pid[:2]])
    base: dict[str, Any] = {
        "product_id": pid,
        "name": f"Product {pid}",
        "category": CATEGORIES[slug],
        "category_slug": slug,
        "subcategory": "Decor",
        "brand": "Acme",
        "price_eur": 50.0,
        "stock": 10,
        "availability": "in_stock",
        "rating": 4.0,
        "reviews_count": 10,
        "recipient": "anyone",
        "occasions": [],
        "tags": [],
        "color": None,
        "material": None,
        "gift_wrap": True,
        "shipping_days": 3,
        "is_digital": False,
        "description": "Plain.",
        "also_listed_as": [],
        "search_primary": True,
        "search_text": "",
        "search_text_compact": "",
    }
    base.update(kw)
    if base["availability"] == "out_of_stock":
        base["stock"] = 0
    return Product(**base)


@pytest.fixture
def catalog() -> Catalog:
    return Catalog(
        [
            product(
                "KD-001",
                name="Chef's Knife 20cm",
                subcategory="Knives",
                price_eur=149,
                rating=4.8,
                reviews_count=394,
                tags=["knife", "japanese"],
                material="VG-10 steel",
            ),
            product(
                "KD-002",
                name="Paring Knife 9cm",
                subcategory="Knives",
                price_eur=69,
                rating=4.8,
                reviews_count=311,
                tags=["knife", "small"],
            ),
            product(
                "KD-003",
                name="Knife Sharpening Stone",
                subcategory="Knives",
                price_eur=54,
                rating=4.6,
                reviews_count=120,
                recipient="him",
            ),
            product(
                "KD-007",
                name="Cold Brew Carafe",
                subcategory="Coffee",
                price_eur=52,
                rating=4.4,
                availability="out_of_stock",
                tags=["coffee"],
            ),
            product(
                "KD-004",
                name="Moka Pot",
                subcategory="Coffee",
                price_eur=48,
                rating=4.5,
                reviews_count=500,
                tags=["coffee"],
                shipping_days=2,
            ),
            product(
                "KD-024",
                name="Herb Garden Kit",
                subcategory="Serving",
                price_eur=42,
                rating=4.3,
                also_listed_as=["HL-021"],
                search_primary=False,
            ),
            product(
                "HL-021",
                name="Herb Garden Kit",
                subcategory="Garden",
                price_eur=42,
                rating=4.3,
                also_listed_as=["KD-024"],
            ),
            product(
                "HL-009",
                name="Alpaca Throw",
                subcategory="Textiles",
                price_eur=185,
                rating=4.9,
                material="Baby alpaca",
                tags=["throw", "blanket"],
                occasions=["anniversary"],
                recipient="her",
            ),
            product(
                "HL-010",
                name="Waffle Cotton Throw",
                subcategory="Textiles",
                price_eur=64,
                rating=4.4,
                material="Organic cotton",
                tags=["throw", "blanket"],
                occasions=["housewarming"],
                description="The everyday version of the alpaca.",
            ),
            product(
                "HL-008",
                name="Bud Vase Cluster",
                subcategory="Vases",
                price_eur=36,
                rating=None,
                reviews_count=None,
                occasions=["housewarming"],
            ),
            product(
                "PT-003",
                name="Cat Tree, Compact",
                subcategory="Cats",
                price_eur=119,
                availability="out_of_stock",
            ),
            product("PT-001", name="Dog Bed", subcategory="Dogs", price_eur=89),
        ]
    )


def ids(result: Any) -> list[str]:
    return [p.product_id for p in result.products]


class TestCategories:
    def test_counts_listings_stock_prices_and_subcategories(self, catalog: Catalog) -> None:
        pets = next(c for c in catalog.categories() if c.slug == "pets")
        assert (pets.products, pets.in_stock, pets.price_min_eur, pets.price_max_eur) == (2, 1, 89, 119)
        assert {(s.name, s.products, s.in_stock) for s in pets.subcategories} == {
            ("Cats", 1, 0),
            ("Dogs", 1, 1),
        }


class TestResolution:
    @pytest.mark.parametrize("value", ["kitchen-dining", "Kitchen & Dining", "kitchen and dining", "KITCHEN"])
    def test_category_resolves_from_slug_name_or_one_word(self, catalog: Catalog, value: str) -> None:
        assert catalog.resolve_category(value) == "kitchen-dining"

    def test_unknown_category_lists_allowed_values_and_a_guess(self, catalog: Catalog) -> None:
        with pytest.raises(UnknownCategory) as err:
            catalog.browse("kitchn")
        assert err.value.allowed_values == ["home-living", "kitchen-dining", "pets"]
        assert err.value.did_you_mean == ["kitchen-dining"]

    def test_a_subcategory_name_points_to_its_category(self, catalog: Catalog) -> None:
        with pytest.raises(UnknownCategory) as err:
            catalog.browse("knives")
        assert err.value.did_you_mean == ["kitchen-dining"]
        assert "subcategory" in err.value.hint and "Knives" in err.value.hint

    @pytest.mark.parametrize("value", ["kd-1", "KD1", "kd-001", " KD-001 "])
    def test_product_id_is_tolerant(self, catalog: Catalog, value: str) -> None:
        assert catalog.details(value).product.product_id == "KD-001"


class TestBrowse:
    def test_default_is_in_stock_best_rated_first(self, catalog: Catalog) -> None:
        result = catalog.browse("kitchen-dining")
        assert ids(result) == ["KD-001", "KD-002", "KD-003", "KD-004", "KD-024"]
        assert result.total_matches == 5

    def test_ties_on_rating_go_to_review_count_then_id(self, catalog: Catalog) -> None:
        assert ids(catalog.browse("kitchen-dining"))[:2] == ["KD-001", "KD-002"]

    def test_missing_ratings_sort_last(self, catalog: Catalog) -> None:
        assert ids(catalog.browse("home-living"))[-1] == "HL-008"

    def test_subcategory_is_case_insensitive_and_unknown_is_an_error(self, catalog: Catalog) -> None:
        assert ids(catalog.browse("kitchen-dining", subcategory="knives")) == ["KD-001", "KD-002", "KD-003"]
        with pytest.raises(UnknownSubcategory) as err:
            catalog.browse("kitchen-dining", subcategory="Lamps")
        assert err.value.allowed_values == ["Coffee", "Knives", "Serving"]

    def test_price_bounds_are_inclusive(self, catalog: Catalog) -> None:
        result = catalog.browse("kitchen-dining", filters=Filters(min_price=48, max_price=69))
        assert ids(result) == ["KD-002", "KD-003", "KD-004"]

    def test_recipient_keeps_products_for_anyone(self, catalog: Catalog) -> None:
        assert set(ids(catalog.browse("home-living", filters=Filters(recipient="her")))) == {
            "HL-009",
            "HL-010",
            "HL-021",
            "HL-008",
        }
        assert "KD-003" not in ids(catalog.browse("kitchen-dining", filters=Filters(recipient="her")))

    def test_occasion_and_shipping_days(self, catalog: Catalog) -> None:
        assert ids(catalog.browse("home-living", filters=Filters(occasion="housewarming"))) == [
            "HL-010",
            "HL-008",
        ]
        assert ids(catalog.browse("kitchen-dining", filters=Filters(max_shipping_days=2))) == ["KD-004"]

    def test_exclude_matches_material_not_description(self, catalog: Catalog) -> None:
        result = catalog.browse("home-living", subcategory="Textiles", filters=Filters(exclude=["alpaca"]))
        assert ids(result) == ["HL-010"]

    def test_limit_is_clamped_with_a_note_and_offset_pages(self, catalog: Catalog) -> None:
        clamped = catalog.browse("kitchen-dining", limit=50)
        assert clamped.limit == 10
        assert any("limit" in n for n in clamped.notes)
        page = catalog.browse("kitchen-dining", limit=2, offset=2)
        assert ids(page) == ["KD-003", "KD-004"]
        assert page.next_offset == 4

    def test_last_page_has_no_next_offset(self, catalog: Catalog) -> None:
        assert catalog.browse("kitchen-dining", limit=5).next_offset is None

    def test_out_of_stock_is_reported_on_the_last_page_only(self, catalog: Catalog) -> None:
        assert catalog.browse("kitchen-dining", limit=2).out_of_stock_matches == []
        last = catalog.browse("kitchen-dining", limit=5)
        assert (len(last.products), last.next_offset) == (5, None)
        assert [p.product_id for p in last.out_of_stock_matches] == ["KD-007"]
        cats = catalog.browse("pets", subcategory="Cats")
        assert ids(cats) == []
        assert [p.product_id for p in cats.out_of_stock_matches] == ["PT-003"]

    def test_include_out_of_stock_returns_them_in_the_ranking(self, catalog: Catalog) -> None:
        result = catalog.browse("pets", subcategory="Cats", filters=Filters(include_out_of_stock=True))
        assert ids(result) == ["PT-003"]
        assert result.out_of_stock_matches == []

    def test_suggestion_gives_the_nearest_price_that_adds_a_result(self, catalog: Catalog) -> None:
        result = catalog.browse("kitchen-dining", filters=Filters(max_price=40))
        assert result.total_matches == 0
        assert [(s.change, s.to, s.would_match) for s in result.suggestions] == [("max_price", 42.0, 1)]

    def test_suggestion_for_a_non_price_filter_is_removal(self, catalog: Catalog) -> None:
        result = catalog.browse("home-living", filters=Filters(occasion="anniversary", max_price=100))
        assert ids(result) == []
        assert [(s.change, s.to) for s in result.suggestions] == [("occasion", None), ("max_price", 185.0)]


class TestSearch:
    def test_ranks_by_where_the_terms_hit(self, catalog: Catalog) -> None:
        assert ids(catalog.search("chef knife")) == ["KD-001", "KD-002", "KD-003"]

    def test_better_match_over_budget_is_reported_with_the_gap(self, catalog: Catalog) -> None:
        result = catalog.search("chef knife", filters=Filters(max_price=100))
        assert ids(result) == ["KD-002", "KD-003"]
        assert [(p.product_id, p.over_by_eur) for p in result.over_budget_matches] == [("KD-001", 49.0)]
        assert [(s.change, s.to, s.would_match) for s in result.suggestions] == [("max_price", 149.0, 3)]

    def test_out_of_stock_match_is_reported_when_there_is_a_query(self, catalog: Catalog) -> None:
        result = catalog.search("cold brew")
        assert ids(result) == []
        assert [p.product_id for p in result.out_of_stock_matches] == ["KD-007"]

    def test_unmatched_terms_are_reported(self, catalog: Catalog) -> None:
        result = catalog.search("sony knife")
        assert result.unmatched_terms == ["sony"]
        assert "KD-001" in ids(result)

    def test_stopwords_and_plurals(self, catalog: Catalog) -> None:
        assert ids(catalog.search("a gift with knives for my dad")) == ids(catalog.search("knife dad"))
        assert catalog.search("throws").total_matches == 2

    def test_occasions_are_searchable(self, catalog: Catalog) -> None:
        assert set(ids(catalog.search("housewarming"))) == {"HL-010", "HL-008"}

    def test_cross_listed_product_appears_once_under_its_primary_id(self, catalog: Catalog) -> None:
        assert ids(catalog.search("herb garden")) == ["HL-021"]

    def test_no_query_lists_the_catalogue_best_rated_first(self, catalog: Catalog) -> None:
        result = catalog.search(None)
        assert ids(result)[0] == "HL-009"
        assert result.total_matches == 9  # 11 primary listings, 2 out of stock
        assert result.out_of_stock_matches == []

    def test_explicit_sort_overrides_relevance(self, catalog: Catalog) -> None:
        assert ids(catalog.search("knife", sort="price_asc")) == ["KD-003", "KD-002", "KD-001"]
        assert ids(catalog.search(None, sort="popularity", limit=1)) == ["KD-004"]

    def test_nonsense_returns_nothing_and_says_so(self, catalog: Catalog) -> None:
        result = catalog.search("asdfghjkl")
        assert (ids(result), result.total_matches, result.unmatched_terms) == ([], 0, ["asdfghjkl"])


class TestDetails:
    def test_in_stock_product_has_no_alternatives(self, catalog: Catalog) -> None:
        assert catalog.details("KD-001").in_stock_alternatives == []

    def test_out_of_stock_product_offers_closest_in_price_same_subcategory_first(
        self, catalog: Catalog
    ) -> None:
        alternatives = catalog.details("KD-007").in_stock_alternatives
        assert [p.product_id for p in alternatives] == ["KD-004", "KD-003", "KD-002"]

    def test_alternatives_fall_back_to_the_category(self, catalog: Catalog) -> None:
        assert [p.product_id for p in catalog.details("PT-003").in_stock_alternatives] == ["PT-001"]

    def test_unknown_id_suggests_close_ids(self, catalog: Catalog) -> None:
        with pytest.raises(ProductNotFound) as err:
            catalog.details("KD-009")
        assert "KD-001" in err.value.did_you_mean

    def test_a_name_instead_of_an_id_suggests_the_product(self, catalog: Catalog) -> None:
        with pytest.raises(ProductNotFound) as err:
            catalog.details("Chef's Knife")
        assert err.value.did_you_mean == ["KD-001"]


@pytest.fixture
def relevance() -> Catalog:
    """A catalogue shaped to separate the ranking keys of ADR-005 one at a time."""
    return Catalog(
        [
            product("KD-010", name="Paring Knife", subcategory="Knives", rating=4.0, price_eur=60),
            product(
                "KD-011",
                name="Slate Cheese Board",
                subcategory="Serving",
                rating=4.9,
                price_eur=40,
                description="Slate board and three knives.",
            ),
            product("HL-030", name="Ember Candle", subcategory="Candles", rating=4.8, tags=["candle"]),
            product(
                "HL-031",
                name="Votive Trio",
                subcategory="Candles",
                rating=4.5,
                tags=["candle"],
                description="Fig and cedar.",
            ),
            product("HL-032", name="Fig Perfume", subcategory="Fragrance", rating=4.6),
            product("HL-033", name="Cocktail Kit", subcategory="Bar", rating=4.7),
            product("HL-034", name="Pasta Kit", subcategory="Cooking", rating=4.6),
            product("HL-035", name="Beard Kit", subcategory="Grooming", rating=4.5),
            product("HL-036", name="Ceramic Planter", subcategory="Garden", rating=4.0),
            product("HL-037", name="Wireless Headphones", subcategory="Audio", rating=4.7, tags=["anc"]),
            product("HL-038", name="Earbuds Pro", subcategory="Audio", rating=4.5, tags=["anc"]),
            product("HL-039", name="Noise Machine", subcategory="Audio", rating=4.2, recipient="her"),
            product(
                "HL-040",
                name="Linen Fig Candle",
                subcategory="Candles",
                price_eur=38,
                tags=["candle", "scented"],
                availability="out_of_stock",
            ),
            product("HL-041", name="Brass Frame", subcategory="Decor", price_eur=39),
            product("HL-042", name="Reed Diffuser", subcategory="Fragrance", price_eur=46, tags=["scented"]),
        ],
        vocabulary=Vocabulary(phrases={"noise cancelling": "anc"}, synonyms=[["headphone", "earbud"]]),
    )


class TestRelevance:
    """ADR-005: strong fields before weak ones, then coverage, rarity, score and rating."""

    def test_a_description_only_match_ranks_after_a_strong_match(self, relevance: Catalog) -> None:
        assert ids(relevance.search("knife")) == ["KD-010", "KD-011"]

    def test_the_category_name_is_not_searched(self, catalog: Catalog) -> None:
        result = catalog.search("kitchen")
        assert (ids(result), result.unmatched_terms) == ([], ["kitchen"])

    def test_matching_more_words_ranks_first(self, relevance: Catalog) -> None:
        assert ids(relevance.search("fig candle"))[:3] == ["HL-031", "HL-030", "HL-032"]

    def test_a_rarer_word_outranks_a_common_one(self, relevance: Catalog) -> None:
        assert ids(relevance.search("garden kit"))[0] == "HL-036"

    def test_explicit_sort_keeps_strong_matches_first(self, relevance: Catalog) -> None:
        assert ids(relevance.search("knife", sort="price_asc")) == ["KD-010", "KD-011"]

    def test_a_phrase_is_rewritten_and_synonyms_match(self, relevance: Catalog) -> None:
        result = relevance.search("noise cancelling headphones")
        assert ids(result) == ["HL-037", "HL-038"]
        assert result.unmatched_terms == []

    def test_a_synonym_counts_as_a_match_for_unmatched_terms(self, relevance: Catalog) -> None:
        assert ids(relevance.search("earbuds")) == ["HL-037", "HL-038"]

    def test_without_a_vocabulary_words_match_literally(self, catalog: Catalog) -> None:
        assert catalog.search("earbuds").unmatched_terms == ["earbud"]

    def test_exact_recipient_comes_before_anyone(self, relevance: Catalog) -> None:
        audio = relevance.search(None, filters=Filters(recipient="her"))
        assert ids(audio)[0] == "HL-039"
        by_rating = relevance.search(None, filters=Filters(recipient="her"), sort="rating")
        assert ids(by_rating)[0] != "HL-039"


class TestSmallerRules:
    def test_unknown_subcategory_points_to_where_the_word_is_listed(self, catalog: Catalog) -> None:
        with pytest.raises(UnknownSubcategory) as err:
            catalog.browse("kitchen-dining", subcategory="Pots")
        assert err.value.did_you_mean == ["Coffee"]

    def test_unknown_subcategory_without_a_lead_suggests_nothing(self, catalog: Catalog) -> None:
        with pytest.raises(UnknownSubcategory) as err:
            catalog.browse("kitchen-dining", subcategory="Lamps")
        assert err.value.did_you_mean == []

    def test_alternatives_from_the_category_prefer_shared_tags(self, relevance: Catalog) -> None:
        alternatives = relevance.details("HL-040").in_stock_alternatives
        assert [p.product_id for p in alternatives] == ["HL-030", "HL-031", "HL-042"]
