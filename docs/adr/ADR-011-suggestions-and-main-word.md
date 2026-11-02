# ADR-011 · Suggestions that keep the request's meaning, and a main word found only in a description

- **Status:** accepted · 2026-11-02
- **Deciders:** Samuel Viciana
- **Related:** ADR-002 (suggestions), ADR-005 (strong and weak fields, rule 4), ADR-006 (main word,
  rule 1), ADR-007 (no suggestion to drop `exclude`), ADR-010 (pets, category words). Supersedes
  ADR-006 rule 1 where no product has the main word in a strong field, and ADR-007 rule 4 on which
  filters may be relaxed. Ranking keys and the ADR-006 freeze stand: no key and no weight changes.

## Context

The review of the level-1 set v5 (81 cases) left ten comments. Six of them are about information
the tool gives, not about order. In each one, the tool offers something the shopper did not ask for:

| Case | Call | Comment |
|---|---|---|
| l1-070 | "wooden toy" · kids | `recipient → null` adds only the dog toy that ADR-010 took out of `kids` |
| l1-076 | "toy" · kids · ≤ 30 | the same: `recipient → null` would match the dog toy |
| l1-077 | recipient pet | `recipient → null` (139) brings back gifts for people |
| l1-066 | "wireless speaker" · ≤ 120 | `max_price → 899` counts only the passive bookshelf speakers, which `over_budget_matches` rightly leaves out |
| l1-078 | "gardening" · him · ≤ 60 | `max_price → 99` counts a speaker whose description says "small garden" |
| l1-071 | "travel pillow" | 10 travel items listed, each marked missing "pillow" |

I checked the cause of each:

- **Recipient.** A suggestion relaxed every filter except `exclude`. Dropping the recipient never
  finds a better gift for the same person. Here it only undid ADR-010.
- **l1-066.** Main-word narrowing is applied once, before any filter, so the suggestion and
  `over_budget_matches` see the same matches. What differs is the bar. `over_budget_matches` lists a
  product above the budget only if it matches at least as well as the best product returned
  (ADR-005 rule 4). The suggestion counted every product the relaxed filter let through. The
  bookshelf speakers match "speaker" but not "wireless", so they pass the second test and fail
  the first.
- **l1-078.** The speaker matches "gardening" only in its description, a weak field (ADR-005). It
  is listed last when it fits the filters, but a weak-only match was enough to propose a new budget.
- **l1-071.** The guess was that the main-word check looked only at products in stock. It does
  not: it runs over every searched product, out of stock included. The cause is the field. The only
  product that says "pillow" is the out-of-stock Acupressure Mat Set (BW-012), and it says so in its
  description: "Mat and pillow with a carry bag". ADR-006 rule 1 narrows only when some product has
  the main word in a strong field, and "otherwise the query is not narrowed". So the request fell
  back to "travel". l1-062, l1-064 and l1-069 have their main word in a strong field ("game",
  "notebook", "grinder") and were narrowed.

## Options considered

Measured on the 81 level-1 cases of v5, in-process, the domain's own run of each case.

1. **Which products a suggestion may count.**
   1. *Only products with a strong-field match.* Fixes l1-078 but not l1-066, where the bookshelf
      speakers match "speaker" in their name. It also changes approved l1-079 ("cooking", her,
      ≤ 50): the suggested €62 cheese board, like the listed Moka pot and tea flight, comes from the
      kitchen aisle's word, which is weak.
   2. *The bar of `over_budget_matches`: as good as the best product returned, and strong.* Fixes
      l1-066 and l1-078. It also changes l1-079, which loses its approved suggestion.
   3. *As good as the weakest product already listed; with nothing listed and a query, a
      strong-field match* (chosen). Fixes l1-066 and l1-078, keeps l1-079. A raised budget is
      suggested only if it brings something the list would show next to what it already shows.
      When nothing is listed there is nothing to compare with, and the bar is the field. Without a
      query there is no match to compare, so a browse is unchanged.
2. **A main word no product has in a strong field.**
   1. *Leave ADR-006 rule 1 as it is.* l1-071 keeps listing travel items, each one missing the word
      that names the product.
   2. *Narrow to the products that have the main word in any field* (chosen), but not in the
      category words of ADR-010. Those name an aisle, not a product, and ADR-010 rule 4 keeps them
      from ever deciding the main word's match. A word no product has anywhere still does not
      narrow, and `unmatched_terms` reports it, as before ("fig gizmo").

## Decision

1. **`recipient` is never suggested for removal**, like `exclude` (ADR-007). The recipient is who
   the gift is for. Price, occasion and shipping days can still be relaxed.
2. **A suggestion must add a product worth listing.** A filter is suggested only if relaxing it
   adds a product that matches the query at least as well as the weakest product already listed
   (the ranking keys of ADR-005, compared as `over_budget_matches` compares them). With a query
   and nothing listed, the product must match in a strong field. A new price (`to`) is the nearest
   one that adds such a product.
3. **`would_match` keeps its meaning:** the number of products the relaxed request returns. It still
   counts weaker matches that come with the new value, because the request would list them.
4. **The main word, when no product has it in a strong field, narrows to the products that have it
   in any of their own fields** (all but the category words). Rarity is still counted over every
   searched product. For "travel pillow" the in-stock list is empty, `total_matches` is 0, and the
   mat is reported in `out_of_stock_matches`, marked missing "travel". Finding something close,
   such as the eye mask, is the agent's job.

The reference implementation (`evals/golden/l1/oracle.py`) was changed to the same rules,
separately from the domain. Both produce the same 81 expected results.

## Results

| Case | Before (v5) | After (v6) |
|---|---|---|
| l1-066 · wireless speaker ≤ 120 | TG-004; suggestion `max_price → 899` (2) | TG-004; no suggestion |
| l1-070 · wooden toy · kids | 4 products; suggestion `recipient → null` (5) | same 4 products; no suggestion |
| l1-071 · travel pillow | 10 travel items (5 shown), each missing "pillow"; BW-012 out of stock | nothing listed, `total_matches` 0; BW-012 out of stock, missing "travel" |
| l1-076 · toy · kids ≤ 30 | nothing; `max_price → 42` (1) and `recipient → null` (1) | nothing; `max_price → 42` (1) |
| l1-077 · recipient pet | PT-001, PT-002, PT-003 out of stock; `recipient → null` (139) | the same; no suggestion |
| l1-078 · gardening · him ≤ 60 | 3 garden products; `max_price → 99` (4) | 3 garden products; no suggestion |

Each row is now what the review asked for. No other case changed, approved or not.

- `make eval-l1`: 81/81 exact on v6. Largest default page 621 tokens, largest page 1,045, as before.
- `make eval-mcp`: parity 81/81, conformance 16/16.
- `make gate-fast`: 522 → 529 tests passed, the seven new ones in `TestSuggestionsAndMainWord`.

## Deferred

These comments ask for a different order, or are about the client's data. Their results did not
change, and they go to the level-2 evaluation with the reviewer's words (`DEFERRED` in
`evals/golden/l1/build.py`):

- **l1-049** (kids, ≤ 40): the incense set is listed for a child. The client's data says `anyone`.
  That is a data issue to report, not a search rule (ADR-005, ADR-010).
- **l1-062** ("wooden board game"): the chess set and backgammon were expected higher. That is an
  order change, and ranking is frozen (ADR-006).
- **l1-080** ("tech gadget", kids, ≤ 100): the tech aisle by rating was expected instead of the
  Home Tech products and their over-budget neighbours. That is also an order change: a
  subcategory is a strong field and an aisle word is not (ADR-010).

## Consequences

- The level-1 set moves to v6: 81 cases, 6 changed and back to review (l1-066, l1-070, l1-071,
  l1-076, l1-077, l1-078), the rest approved or deferred as before.
- The tool descriptions and the OpenAPI document do not change. "A filter change that would
  return more, and how many" still describes a suggestion, so the level-2 recordings stay valid.
- The served catalogue does not change: the rules live in the domain, not in the data.
