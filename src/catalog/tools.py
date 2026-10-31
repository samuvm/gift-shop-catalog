"""The four tools, defined once: name, description, parameters and response shape.

The OpenAPI document (REST) and the MCP server are both generated from these definitions, so
what a model reads cannot drift between transports (ADR-002). The descriptions are written for
the model that decides whether to call a tool and with what: they are the interface.
"""

from dataclasses import dataclass, field
from typing import Any

SLUGS = [
    "beauty-wellness",
    "books-stationery",
    "experiences",
    "games-puzzles",
    "home-living",
    "jewellery",
    "kids",
    "kitchen-dining",
    "outdoor-travel",
    "pets",
    "tech-gadgets",
]
RECIPIENTS = ["anyone", "him", "her", "couple", "kids"]
# One recipient or several, comma-separated ("her,couple"), as exclude takes several words (ADR-006).
RECIPIENT_PATTERN = rf"^ *({'|'.join(RECIPIENTS)}) *(, *({'|'.join(RECIPIENTS)}) *)*$"
OCCASIONS = ["birthday", "christmas", "anniversary", "housewarming", "thank-you", "graduation"]
SORTS = ["relevance", "rating", "popularity", "price_asc", "price_desc"]
AVAILABILITY = ["in_stock", "low_stock", "out_of_stock", "unlimited"]


@dataclass(frozen=True)
class Param:
    name: str
    location: str  # "path" or "query"
    schema: dict[str, Any]
    description: str
    required: bool = False


@dataclass(frozen=True)
class Tool:
    name: str
    path: str
    summary: str
    description: str
    params: list[Param] = field(default_factory=list)
    response: dict[str, Any] = field(default_factory=dict)
    example: dict[str, Any] = field(default_factory=dict)


# ---------- shared parameters

FILTERS = [
    Param("min_price", "query", {"type": "number", "minimum": 0}, "Lowest price in EUR, inclusive."),
    Param(
        "max_price",
        "query",
        {"type": "number", "minimum": 0},
        "Highest price in EUR, inclusive. Prices are always in EUR. If the shopper gave an approximate "
        "budget ('about 50'), a small margin above it is reasonable.",
    ),
    Param(
        "recipient",
        "query",
        {"type": "string", "pattern": RECIPIENT_PATTERN, "maxLength": 40},
        "Who the gift is for: anyone, him, her, couple or kids, or several separated by commas. Products "
        "marked 'anyone' are always included, after the ones for the recipients asked for. Leave it out "
        "when unknown. For a partner (an anniversary, for example), pass 'her,couple' or 'him,couple'.",
    ),
    Param(
        "occasion",
        "query",
        {"type": "string", "enum": OCCASIONS},
        "Occasion tag. The shop's tags are not exhaustive: if a strict occasion filter returns little, "
        "try again without it.",
    ),
    Param(
        "max_shipping_days",
        "query",
        {"type": "integer", "minimum": 0, "maximum": 14},
        "Only products that ship within this many days. 0 means digital, delivered by email. For a "
        "deadline, count days from meta.today and leave a margin: shipping days are an estimate.",
    ),
    Param(
        "exclude",
        "query",
        {"type": "string", "maxLength": 200},
        "Comma-separated words to rule out, matched against product name, subcategory, tags and "
        "material. Examples: 'candle,scented' for someone who dislikes scents; 'leather,silk,wool,alpaca' "
        "for a vegan.",
    ),
    Param(
        "include_out_of_stock",
        "query",
        {"type": "boolean", "default": False},
        "Also list out-of-stock products. By default they are left out of the list but still reported in "
        "out_of_stock_matches.",
    ),
    Param(
        "sort",
        "query",
        {"type": "string", "enum": SORTS},
        "relevance (search default), rating (browse default), popularity (most reviewed), price_asc "
        "(cheapest first) or price_desc.",
    ),
    Param(
        "limit",
        "query",
        {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
        "How many products to return, 1 to 10. Default 5. Larger values are reduced to 10.",
    ),
    Param(
        "offset",
        "query",
        {"type": "integer", "minimum": 0, "default": 0},
        "Skip this many results, for 'show me more'. Use meta.next_offset from the previous answer.",
    ),
]

# ---------- response schemas (inline on purpose: the platform's form cannot edit $ref)

NULLABLE_NUMBER = {"type": "number", "nullable": True}
NULLABLE_INTEGER = {"type": "integer", "nullable": True}
NULLABLE_STRING = {"type": "string", "nullable": True}
STRINGS = {"type": "array", "items": {"type": "string"}}


def _obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or list(properties)}


ITEM = _obj(
    {
        "product_id": {"type": "string", "description": "Use it with get_product_details."},
        "name": {"type": "string"},
        "category": {"type": "string"},
        "subcategory": {"type": "string"},
        "price_eur": {"type": "number"},
        "availability": {
            "type": "string",
            "enum": AVAILABILITY,
            "description": "low_stock = 5 or fewer left; unlimited = digital gift card.",
        },
        "rating": {**NULLABLE_NUMBER, "description": "Out of 5. null means no reviews yet."},
        "reviews_count": NULLABLE_INTEGER,
        "recipient": {"type": "string", "enum": RECIPIENTS},
        "occasions": STRINGS,
        "shipping_days": {"type": "integer", "description": "Estimate in days; 0 = digital delivery."},
        "gift_wrap": {"type": "boolean"},
        "description": {"type": "string", "description": "The shop's own copy. Caveats live here."},
    }
)
REF = _obj({"product_id": {"type": "string"}, "name": {"type": "string"}, "price_eur": {"type": "number"}})
SUGGESTION = _obj(
    {
        "change": {"type": "string", "description": "The filter to relax."},
        "to": {
            **NULLABLE_NUMBER,
            "description": "New value for a price filter; null means remove the filter.",
        },
        "would_match": {"type": "integer", "description": "How many products the change would return."},
    }
)
META = _obj(
    {
        "total_matches": {"type": "integer"},
        "returned": {"type": "integer"},
        "next_offset": {
            **NULLABLE_INTEGER,
            "description": "Pass as offset to see more; null when there is no more.",
        },
        "applied": {
            "type": "object",
            "additionalProperties": True,
            "description": "The filters as the server understood them.",
        },
        "today": {"type": "string", "format": "date", "description": "The shop's date, for deadlines."},
        "catalog_version": {"type": "string"},
    }
)
MISSING_TERMS = {
    **STRINGS,
    "description": "Search words that do not appear in this product's record. Present only when some "
    "are missing. It means the shop's data does not say so, not that the product lacks it: check the "
    "description before recommending it for that word.",
}
LIST_ITEM = {**ITEM, "properties": {**ITEM["properties"], "missing_terms": MISSING_TERMS}}
NEAR_MISS = {**REF, "properties": {**REF["properties"], "missing_terms": MISSING_TERMS}}
LIST_RESPONSE = {
    "type": "object",
    "required": ["products", "meta"],
    "properties": {
        "products": {"type": "array", "items": LIST_ITEM},
        "meta": META,
        "out_of_stock_matches": {
            "type": "array",
            "items": NEAR_MISS,
            "description": "Products that match but are out of stock. Present only when relevant. "
            "Say they are "
            "out of stock; never say the shop does not sell them.",
        },
        "over_budget_matches": {
            "type": "array",
            "items": {
                **NEAR_MISS,
                "properties": {**NEAR_MISS["properties"], "over_by_eur": {"type": "number"}},
                "required": [*REF["required"], "over_by_eur"],
            },
            "description": "Better matches that max_price left out, with how far over budget they are.",
        },
        "unmatched_terms": {
            **STRINGS,
            "description": "Query words that match nothing in the whole catalogue: "
            "the shop does not carry them.",
        },
        "suggestions": {
            "type": "array",
            "items": SUGGESTION,
            "description": "When few results came back: filter changes that would return more, and how many.",
        },
        "note": {"type": "string", "description": "How the server interpreted an input, when it had to."},
    },
}
PRODUCT = _obj(
    {
        **ITEM["properties"],
        "brand": {"type": "string"},
        "color": NULLABLE_STRING,
        "material": NULLABLE_STRING,
        "tags": STRINGS,
        "stock_units": {
            "type": "integer",
            "description": "Units available; for gift cards a large placeholder.",
        },
        "is_digital": {"type": "boolean"},
        "also_listed_as": {**STRINGS, "description": "The same product listed under another category's id."},
    }
)
DETAILS_RESPONSE = _obj(
    {
        "product": PRODUCT,
        "in_stock_alternatives": {
            "type": "array",
            "items": ITEM,
            "description": "Present when the product is out of stock: similar products that are available.",
        },
        "meta": _obj({"today": META["properties"]["today"], "catalog_version": {"type": "string"}}),
        "note": {"type": "string"},
    },
    required=["product", "meta"],
)
CATEGORIES_RESPONSE = _obj(
    {
        "categories": {
            "type": "array",
            "items": _obj(
                {
                    "name": {"type": "string"},
                    "slug": {"type": "string", "enum": SLUGS},
                    "products": {"type": "integer"},
                    "in_stock": {"type": "integer"},
                    "price_min_eur": {"type": "number"},
                    "price_max_eur": {"type": "number"},
                    "subcategories": {
                        "type": "array",
                        "items": _obj(
                            {
                                "name": {"type": "string"},
                                "products": {"type": "integer"},
                                "in_stock": {"type": "integer"},
                            }
                        ),
                    },
                }
            ),
        },
        "recipients": {"type": "array", "items": {"type": "string", "enum": RECIPIENTS}},
        "occasions": {"type": "array", "items": {"type": "string", "enum": OCCASIONS}},
        "meta": _obj({"today": META["properties"]["today"], "catalog_version": {"type": "string"}}),
    }
)
ERROR_RESPONSE = _obj(
    {
        "error": _obj(
            {
                "code": {
                    "type": "string",
                    "enum": [
                        "unauthorized",
                        "unknown_category",
                        "unknown_subcategory",
                        "product_not_found",
                        "invalid_parameter",
                    ],
                },
                "message": {"type": "string"},
                "hint": {"type": "string", "description": "What to do next."},
                "allowed_values": STRINGS,
                "did_you_mean": STRINGS,
            },
            required=["code", "message", "hint"],
        )
    }
)

# ---------- the tools

GET_CATEGORIES = Tool(
    name="get_categories",
    path="/categories",
    summary="List what the shop sells: categories, subcategories, stock and price ranges.",
    description=(
        "The gift shop's 11 categories, each with its subcategories, how many products are listed and in "
        "stock, and its price range in EUR. Also returns the allowed values of the recipient and occasion "
        "filters.\n\n"
        "Call it when the shopper has not said what kind of product they want, when you need a category "
        "slug for get_products_by_category, or to check whether a budget is realistic before searching. "
        "It takes no parameters and rarely changes: one call per conversation is enough."
    ),
    response=CATEGORIES_RESPONSE,
)
GET_PRODUCTS_BY_CATEGORY = Tool(
    name="get_products_by_category",
    path="/categories/{category}/products",
    summary="Browse one category, with optional filters.",
    description=(
        "Lists products in one of the shop's 11 categories (the values of `category`). Use it when the "
        "shopper names or picks one of them ('something for the kitchen', 'show me jewellery') or asks for "
        "more of one. If the shopper's word is not one of those categories ('garden', 'candles', 'gadgets'), "
        "do not pick the nearest category: use search_products with that word. To find products from a "
        "description across all categories, use search_products too.\n\n"
        "Returns up to `limit` products (default 5), in stock, best rated first unless `sort` says "
        "otherwise. "
        "Each product has its price, availability, rating, who it suits, occasions, shipping days, gift wrap "
        "and the shop's short description. For brand, colour, material and stock units, call "
        "get_product_details.\n\n"
        "Read the extra fields when present: out_of_stock_matches (matching products that are out of stock), "
        "over_budget_matches (just above max_price, when recipient or occasion is set), suggestions (a "
        "filter change that would return more, and how many) and note (how an input was read)."
    ),
    params=[
        Param(
            "category",
            "path",
            {"type": "string", "enum": SLUGS},
            "Category slug, as listed by get_categories. Names in other spellings ('Kitchen and Dining') "
            "or a single word ('kitchen') are also accepted. If the shopper's word is none of these "
            "categories, call search_products with it instead of choosing the nearest one.",
            required=True,
        ),
        Param(
            "subcategory",
            "query",
            {"type": "string", "maxLength": 50},
            "A subcategory within the category, such as 'Knives' or 'Candles' (any case). get_categories "
            "lists them.",
        ),
        *FILTERS,
    ],
    response=LIST_RESPONSE,
)
SEARCH_PRODUCTS = Tool(
    name="search_products",
    path="/products/search",
    summary="Search the whole catalogue from a description of what the shopper wants.",
    description=(
        "Finds products in every category. Use it for requests such as 'a chef's knife under 100', "
        "'something for a coffee lover' or 'a housewarming gift around 50'. Without a query it lists the "
        "whole catalogue with the given filters, for 'your best rated' or 'the cheapest thing you have'.\n\n"
        "Write the query in English catalogue words: product types, materials, uses or hobbies ('knife', "
        "'candle', 'coffee', 'noise cancelling headphones', 'yoga'). Do not pass the shopper's literal "
        "phrasing or language. Put budget, recipient, occasion and deadline in the filters, not in the "
        "query. If the first query finds little, try a broader word or a synonym.\n\n"
        "Results are keyword matches. Put the kind of product last ('leather notebook', 'wireless speaker'): "
        "with two or more words, only products whose name, subcategory or tags contain the last one are "
        "returned, when there are any. Words such as 'set' or 'kit' only count on their own. Products that "
        "match more of the words come first; matches only in the description, colour or material come last. "
        "Each product lists missing_terms when it lacks some of the words. Category names are not searched: "
        "use get_products_by_category for a whole category. Results are in stock only by default, and each "
        "product appears once. Read the extra "
        "fields when present: over_budget_matches (better matches above max_price, with the gap in EUR), "
        "out_of_stock_matches, unmatched_terms (words that match nothing: the shop does not carry that "
        "brand or item) and suggestions."
    ),
    params=[
        Param(
            "query",
            "query",
            {"type": "string", "maxLength": 100},
            "What to look for, in English catalogue words, for example 'chef knife' or 'scented candle'. "
            "Optional: leave it out to list by filters only.",
        ),
        *FILTERS,
    ],
    response=LIST_RESPONSE,
)
GET_PRODUCT_DETAILS = Tool(
    name="get_product_details",
    path="/products/{product_id}",
    summary="Everything about one product, including caveats and available alternatives.",
    description=(
        "The full record of one product: brand, colour, material, tags, stock units, gift wrap, shipping "
        "days, rating and the shop's description with its caveats (for example 'needs an amplifier' or "
        "'subscription required after the first year'). Use it to answer a specific question about a "
        "product, before describing one in detail, or to check stock for several units.\n\n"
        "If the product is out of stock, in_stock_alternatives lists up to 3 similar products that are "
        "available (same subcategory first, then products sharing its tags, then closest in price). "
        "rating null means no reviews yet. "
        "shipping_days is the shop's estimate, not a guaranteed delivery date.\n\n"
        "Takes a product_id from an earlier result, such as 'KD-001'. If you only have a name, use "
        "search_products first."
    ),
    params=[
        Param(
            "product_id",
            "path",
            {"type": "string", "maxLength": 20},
            "Product id from an earlier result, such as 'KD-001'. Lower case or no zero padding ('kd-7') "
            "is accepted.",
            required=True,
        ),
    ],
    response=DETAILS_RESPONSE,
)

TOOLS = [GET_CATEGORIES, GET_PRODUCTS_BY_CATEGORY, SEARCH_PRODUCTS, GET_PRODUCT_DETAILS]
