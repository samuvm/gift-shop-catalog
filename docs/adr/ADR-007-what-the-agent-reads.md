# ADR-007 · What the agent reads must not mislead it

- **Status:** accepted · 2026-10-30
- **Deciders:** Samuel Viciana
- **Related:** ADR-006 (main word, `missing_terms`, ranking freeze). Extends ADR-006's
  `missing_terms` and ADR-002's suggestions and error hints. Ranking does not change.

## Context

The third human review of the level-1 set (v3, 30 cases) left 11 comments. They fall into two
groups:

- **Information that would mislead the agent.** These are not a matter of taste:
  - the portable speaker is Bluetooth, yet `missing_terms` said it lacks "wireless" (l1-066);
  - two vermeil earrings were offered over budget for "silver earrings", with nothing to say
    they are not silver (l1-068);
  - for a vegan, a suggestion proposed dropping the exclusion (l1-038);
  - the hint for an unknown subcategory stayed generic, although the tool knew the one place
    where lamps are listed (l1-007). The reviewer also asked whether `allowed_values`, which
    the hint refers to, is in the response. It is, but the review sheet did not show it.
- **Disagreements with the order or with a semantic judgement**, on results that did not
  change: a sauna blanket, incense for children, a pepper mill for "coffee grinder", a dog toy
  for "wooden toy", chess as a board game. ADR-006 froze ranking, so these go to the level-2
  evaluation. Each listed product that does not fit now says which words it lacks, so the agent
  can tell.

## Decision

1. **`missing_terms` covers near misses too.** Products in `over_budget_matches` and
   `out_of_stock_matches` carry the query words they lack, the same as listed products.
2. **`missing_terms` is described for what it is:** the shop's record does not mention the
   word. That is not proof that the product lacks the feature, and the description tells the
   model to check before recommending.
3. **`[wireless, bluetooth]`** joins the synonym groups in `data/decisions.yaml`. In this
   catalogue, the only product that says "bluetooth" is wireless.
4. **An exclusion is never suggested for removal.** `exclude` is a deliberate constraint (vegan,
   allergy, a dislike). Price, recipient, occasion and shipping days can still be relaxed.
5. **One lead, one call.** When an unknown subcategory's word is listed in exactly one
   subcategory, the hint names the call, as it already did for an unknown category.
6. **Error cases record `allowed_values`**, so the review sheet shows what the hint refers to.

## Consequences

- The level-1 set moves to v4: 74 cases, 9 changed and back to review. The 8 frozen ranking
  comments are shown as *deferred to level 2*, with the reviewer's words, and are not counted
  as approved.
- Responses grow by a few tokens: the largest default page is 622 tokens and the largest page
  1,046, under their limits of 1,150 and 1,800.
