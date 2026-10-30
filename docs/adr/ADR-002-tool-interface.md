# ADR-002 · The tool interface: four read-only tools written for a model

- **Status:** accepted · 2026-10-30
- **Deciders:** Samuel Viciana
- **Related:** ADR-001 (cleaned catalogue), JOURNAL day 2 block 2 (100-conversation stress test)

## Context

The platform turns each OpenAPI operation into a tool, and the model decides whether to call it
and with what, **from the names and descriptions alone**. The brief asks for three operations
and invites more if the conversations need them. A stress test with 100 synthetic conversations
(671 customer messages) showed what customers actually ask for: dates, exclusions, price ranges,
out-of-stock products asked for by name, brands we do not sell, "the most popular", and
off-topic turns that no tool should serve.

## Decision

### Four tools, one job each

| Tool | Method and path | Its one job |
|---|---|---|
| `get_categories` | `GET /categories` | What the shop sells: categories, subcategories, counts, price range |
| `get_products_by_category` | `GET /categories/{category}/products` | Browse one category the shopper named or chose |
| `search_products` | `GET /products/search` | Find products across the whole catalogue from a description |
| `get_product_details` | `GET /products/{product_id}` | Everything about one product, including caveats and alternatives |

Search takes no `category` parameter on purpose: browsing *within* a category and searching
*across* the catalogue are separate decisions, and the model should never have to choose
between two tools that do the same thing. All four are `GET`: they read and never change
anything.

**Rejected:**
- `get_similar_products`: browsing the product's category with a price filter already does it.
- Batch details: list items already carry price, availability, shipping and wrapping, which
  covers totals and comparisons, and the platform can run calls in parallel.
- `get_shop_policies`: there is no returns, shipping-cost or discount data. A tool would invite
  the model to fill the gap.
- `recommend_gift`: recommending is the agent's job. A tool that decides hides the reasoning
  and cannot be evaluated.
- A "guard" tool to call on injection or off-topic: it runs only if the model chooses to call
  it, so it fails exactly when the model has been manipulated. That layer belongs before the
  model (the platform's Security layer), with deterministic limits in the service.

### Shared filters (browse and search)

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `min_price`, `max_price` | number ≥ 0, EUR | none | Inclusive. Prices are always EUR; the agent converts nothing |
| `recipient` | enum `anyone, him, her, couple, kids` | none | `anyone` products are included for every recipient |
| `occasion` | enum of the 6 occasions | none | The shop's own tags; not exhaustive (the description says so) |
| `max_shipping_days` | integer 0–14 | none | For deadlines. 0 = digital delivery |
| `exclude` | comma-separated words | none | Drops products whose name, tags, material or description contain any of them (`candle,leather,silk`) |
| `include_out_of_stock` | boolean | `false` | Out-of-stock matches are still *reported* (see below), never silently dropped |
| `sort` | enum `relevance, rating, popularity, price_asc, price_desc` | `relevance` for search with a query, else `rating` | `popularity` = review count. Missing ratings sort last |
| `limit` | integer 1–10 | 5 | Values above 10 are clamped to 10, with a note; never an error |
| `offset` | integer ≥ 0 | 0 | For "show me more" |

`get_products_by_category` adds `subcategory` (string, case-insensitive). `search_products` adds
`query` (optional, up to 100 characters). Its description tells the model to write it in
**catalogue words, in English**: product type, material, use or hobby ("noise cancelling
headphones", "candle", "coffee"), not the shopper's literal phrasing.

### Response shape

Every list response has the same envelope:

```json
{
  "products": [ /* compact items, below */ ],
  "meta": {
    "total_matches": 7, "returned": 5, "next_offset": 5,
    "applied": {"max_price": 100, "recipient": "her"},
    "today": "2026-10-30", "catalog_version": "6b3c871e"
  },
  "out_of_stock_matches": [ {"product_id": "GP-007", "name": "Jigsaw 1000pc, City Map", "price_eur": 32.0} ],
  "over_budget_matches": [ {"product_id": "KD-001", "name": "Chef's Knife 20cm", "price_eur": 149.0, "over_by_eur": 49.0} ],
  "unmatched_terms": ["sony"],
  "suggestions": [ {"remove": "occasion", "would_match": 4} ],
  "note": "One sentence when something needs attention, otherwise absent."
}
```

The optional blocks appear only when they carry information:

- **`out_of_stock_matches`** (up to 3) answers "do you have the City Map jigsaw?" when it exists
  but is out of stock. Without it, the agent would say the shop does not sell it.
- **`over_budget_matches`** (up to 2, search only) lists better matches that `max_price`
  excluded, and by how much. "A chef's knife under €100": the only chef's knife is €149.
- **`unmatched_terms`** lists query words that match nothing in the catalogue, so the agent can
  say "we don't stock Sony; the closest is…" instead of pretending.
- **`suggestions`** appears when fewer results than `limit` come back. It names the single
  filter whose removal would return the most products, and how many.
- **`meta.today`** gives the date, because the model may not know it and deadlines are common.

A compact item carries every field a recommendation can use without opening the details:

```json
{"product_id": "KD-002", "name": "Paring Knife 9cm", "category": "Kitchen & Dining", "subcategory": "Knives",
 "price_eur": 69.0, "availability": "in_stock", "rating": 4.8, "reviews_count": 311,
 "recipient": "anyone", "occasions": ["thank-you", "housewarming"], "shipping_days": 3, "gift_wrap": true,
 "description": "The knife people actually reach for most. Pairs with the gyuto."}
```

**Size, measured, not estimated** (`o200k_base`, every product in the catalogue, worst case
with every optional block at its maximum):

| Item shape | Tokens per item | Worst page of 5 | Worst page of 10 |
|---|---|---|---|
| **Chosen: the item above** | **~120** | **973** | **1,621** |
| Without category, recipient, occasions and review count | ~86 | 790 | 1,256 |
| Without the description as well | ~63 | 643 | 977 |

The first estimate (~90 tokens per item) was wrong by a third, and the chosen item broke the
original limits (≤ 800 and ≤ 1,500). Two options were measured: trim the item, or raise the
limits. The limits were raised to 1,150 and 1,800, that is the measured worst case plus a
margin of about 150 tokens. The reasons:
- A worst page of ~1,000 tokens is small next to the model's context.
- Recipient, occasions and review count are what make a recommendation reason ("for a
  housewarming", "311 reviews") readable without a second call per product.
- One second call per product adds latency to every recommendation in the widget.

The description stays because it is short (142 characters at most) and it is where the reasons
and caveats live. `note` is capped at 100 characters, and the sizes are re-measured on every
level-1 case.

`get_product_details` returns every field of the cleaned product, plus:

- **`in_stock_alternatives`** (up to 3) when the product is out of stock: same subcategory
  first, then the same category, closest in price.
- `rating: null` with `reviews_count: null` means "no reviews yet", never zero.
- `also_listed_as` for cross-listed products.

`get_categories` returns each category with its slug, listing count, in-stock count, price
range and subcategories (each with counts), plus the allowed `recipient` and `occasion` values.

### Search behaviour (deterministic, no model)

- **Terms.** The query is lower-cased, split into words, and stop-words are dropped; a
  trailing plural `s` is removed. A product matches if any term appears in its `search_text`.
- **Ranking.** Weighted by where the term hits: name ×3, subcategory and tags ×2, category,
  material and colour ×1.5, description ×1. Ties go to rating, then review count, then ID.
  This is keyword scoring and is called that, not BM25 or semantic search.
- **Duplicates.** Search shows each cross-listed product once, under its primary ID.
  Browsing a category shows each listing under that category's ID.

### Tolerant inputs, recoverable errors

The server resolves what it can and says so in `note`, instead of failing:

- `category` accepts the slug (the enum in the spec), the name in any spelling, or one word
  ("kitchen").
- `product_id` accepts `kd-7`, `KD7` or `kd-007`.
- `limit` above 10 is clamped.

What cannot be resolved returns a 4xx with one error shape:

```json
{"error": {"code": "unknown_category", "message": "No category matches 'garden'.",
           "hint": "Use one of allowed_values, or call get_categories.",
           "allowed_values": ["home-living", "kitchen-dining"], "did_you_mean": ["home-living"]}}
```

| Code | Status | Recovery the body offers |
|---|---|---|
| `unauthorized` | 401 | How to send `X-API-Key` |
| `unknown_category` | 404 | `allowed_values` and `did_you_mean` |
| `unknown_subcategory` | 404 | The subcategories of that category |
| `product_not_found` | 404 | `did_you_mean` by ID, or by name if a name was passed, plus "use search_products" |
| `invalid_parameter` | 400 | Which parameter, what was received, what is allowed |

An empty result is **not** an error: it is a 200 with `total_matches: 0` and suggestions.

**Open risk, checked in the platform's Playground before F2:** whether the platform passes a
4xx body to the model or only "the call failed". If only the status reaches it, recoverable
cases switch to 200 with an `error` block, and that change gets its own ADR.

### One definition, two transports

Each tool's name, description and parameter descriptions are written **once**, in code. Both the
OpenAPI document and the MCP server are generated from that one source, so they cannot drift
(G-MCP-PARITY), and the domain imports neither transport (G-ARCH-LAYERS). MCP tools are marked
`readOnlyHint: true`, and their errors are tool results with `isError` and the same body.

### Served OpenAPI

- OpenAPI 3.0.3 for the widest import compatibility.
- Every schema inline: no `$ref`, `oneOf`, `anyOf` or `allOf`, so the platform's form can edit
  each operation. Nullable fields use `nullable: true`.
- Enums inline. `operationId` equals the tool name. Every operation and parameter has a
  description written for the model, and every response has an example.
- The `X-API-Key` header is declared as a security scheme for human readers only; the platform
  ignores it and sends the key from a secret.

All of the above is checked by `make spec-lint` (G-SPEC-LINT) and pinned by a snapshot test.

## Consequences

- A model that reads only the spec can act on every case in the stress test that has catalogue
  data, and can say "I don't know" on the ones that have none.
- The descriptions are the product. They are written first, measured with the level-2 eval
  (v1 vs v2), and changed only with a measured reason.
- Renaming a tool after the platform is configured breaks the agent, so names are fixed here.
