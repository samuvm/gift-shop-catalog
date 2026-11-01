# ADR-010 · Pet products, activity words, and the words of a category's name

- **Status:** accepted · 2026-11-01
- **Deciders:** Samuel Viciana
- **Related:** ADR-005 (search relevance), ADR-006 (main word, recipients), ADR-001 (decisions file).
  Supersedes ADR-005 rule 1 on the category name, which is no longer entirely unsearched, and
  ADR-006 rule 6 on `anyone`, which is no longer added for a pet. Ranking keys and the ADR-006
  freeze stand: no key changes and no weight of an existing field changes.

## Context

Running the real tools while writing conversation tests, and the platform's simulations, found
four answers a shop assistant would not give. None of them is a ranking disagreement. In each
one, the shop's words and the shopper's words don't meet:

| Call | Before | Why |
|---|---|---|
| `search_products {recipient: kids, max_price: 30}` | the Rope Toy Bundle (a dog toy) on the page | the three Pets products say `anyone`, and every person filter includes `anyone` |
| `search_products {query: gardening, recipient: him, max_price: 60}` | nothing, `unmatched_terms: [gardening]` | the shop says "Garden" (a subcategory); no product says "gardening" |
| `search_products {query: cooking, recipient: her, max_price: 50}` | the cookbook only | only its name says "cooking"; "kitchen" is a tag of the herb kit and the name of an aisle |
| `search_products {query: tech gadget, recipient: kids, max_price: 100}` | three Home Tech products, each marked missing "gadget"; `unmatched_terms: [gadget]` | "Tech & Gadgets" is the category name, which ADR-005 stopped searching; no product says "gadget" |

"kitchen" (≤ 60) found only the herb kit, and "toy" (kids, ≤ 30) found only the dog toy.

## Options considered

Measured on the 74 level-1 cases of v4 (in-process, the domain's own run of each case), and on
the calls above.

1. **Synonym groups only** (`[garden, gardening, gardener]`, `[cooking, cook, kitchen]`,
   `[gadget, tech]`). Changes no level-1 case. Fixes "gardening". "cooking" gains the herb kit,
   but no product of the kitchen aisle. `[gadget, tech]` only silences the unmatched "gadget".
   The same three Home Tech products are returned, and no headphones, speaker or camera.
2. **The category name as a weak field** (weight 1, as the description). Fixes "kitchen" and
   "gadget". It also changes two approved cases. l1-039 ("puzzle", price ascending) gets a card
   game back on its page, the exact noise ADR-005 removed, and without a `missing_terms` mark
   this time. l1-043 ("travel", him) gains an out-of-stock outdoor product and four matches. It
   also changes the deferred case l1-071.
3. **The category name as a strong field.** Changes the same cases as option 2, plus l1-062.
   Strong fields say what a product is. An aisle does not.
4. **Only the words of a category's name that a person chose, as a weak field, plus two synonym
   groups** (chosen). Changes no approved case and fixes all four calls.

## Decision

1. **`recipient: pet`.** `pet` joins the allowed recipients in `data/decisions.yaml`. A new
   decision, `recipient_overrides`, reads the export's `anyone` as `pet` for every product in
   *Pets*, with its reason. Only `anyone` is replaced. A recipient the export names is kept. The
   ingest records the override under `decisions_applied` (`recipient_override`, PT-001 to
   PT-003). If no product of that category is left in an export, it notes `unused_decision`.
2. **`anyone` means any person.** It is added to the products for a person (`him`, `her`,
   `couple`, `kids`), not to the products for a pet. `recipient: pet` lists pet products only,
   and `kids,pet` lists both plus `anyone`. The tool description says so, and tells the model to
   pass `pet` for a dog or a cat.
3. **Two synonym groups**, the same mechanism as `[wood, wooden]`: `[garden, gardening, gardener]`
   and `[cooking, cook, kitchen]`. A hobby is asked for as the activity, and the shop names the
   thing.
4. **`search.category_words`.** For a category, the words of its name a shopper uses for the whole
   aisle: `kitchen-dining: [kitchen]`, `tech-gadgets: [tech, gadget]`, `pets: [pet]`. They are
   searched as the weakest field (weak, weight 1). They say which aisle a product is in, not what
   it is. So they never make a product the main word's match (ADR-006 rule 1), and they rank
   after any strong match. The rest of the name stays unsearched: "puzzle", "travel" and "home"
   behave as before. The ingest rejects a word that is not in that category's name, so the list
   can only make the name searchable, never tag products with new words.
5. **The unused-synonym check runs the search.** It used to look for a group's words in
   `search_text`, which holds the category name and "For: kids". A group found only there passed
   the check and still matched nothing. Now a group is noted when searching it returns
   `unmatched_terms`.

## Results

Each call through `service.execute`, the entry point REST and MCP share, on the built catalogue.
The page shows 5 products at most. Before → after (rows 2 to 6 are level-1 cases l1-076 to
l1-081):

| Call | Before | After |
|---|---|---|
| gardening · him · ≤ 40 | nothing, unmatched | nothing; over budget: Herb Garden Kit €42, Aurora Hanging Planter €47 |
| gardening · him · ≤ 60 | nothing, unmatched | Herb Garden Kit, Ceramic Planter, Aurora Hanging Planter |
| cooking · her · ≤ 50 | Art of Slow Cooking | Art of Slow Cooking, Herb Garden Kit, Moka Pot, Loose Leaf Tea Flight |
| tech gadget · kids · ≤ 100 | 3 Home Tech, "gadget" unmatched (3 matches) | the same 3 first, then Monitor Light Bar, Portable Speaker (10 matches) |
| kitchen · ≤ 60 | Herb Garden Kit (1 match) | Herb Garden Kit, Art of Slow Cooking, Sharpening Stone, Moka Pot, Tea Flight (5 matches) |
| toy · kids · ≤ 30 | Rope Toy Bundle (dog toy) | nothing; over budget: Night Light €42, Junior Science Kit €62 |
| kids · ≤ 30, no query | Incense, 2 notebooks, Rope Toy Bundle, Film Twin Pack | Incense, 2 notebooks, Film Twin Pack, Letterpress Card |

The last row still lists products for `anyone` that a child would not use, such as the incense
set. That is the client's data, as ADR-005 already noted, and it stays with the agent.

## Consequences

- The level-1 set moves to v5: 81 cases. Two changed, both deferred in v4 and both back to
  review. l1-070 ("wooden toy", kids) loses the dog toy and is now what the reviewer asked for
  in v3. l1-049 (kids, ≤ 40) has one match fewer, with the same page. Seven new cases cover this
  ADR and the apostrophe ("chef's knife") over HTTP. No approved case changed.
- `decisions_sha256`, `products_sha256` and `served_sha256` change: three products changed
  recipient and the vocabulary grew. The served `catalog_version` shows it.
- The tool description changed, so the level-2 recordings, keyed by a hash of the tools, need
  a new recording.
- Response size: the largest default page is 621 tokens and the largest page 1,045, under their
  limits.
