# ADR-005 · Search relevance, vocabulary and four smaller rules

- **Status:** accepted · 2026-10-30
- **Deciders:** Samuel Viciana
- **Related:** ADR-002 (tool interface). Supersedes ADR-002's keyword scoring and ranking, its
  rule for when out-of-stock matches are shown, and its ordering of in-stock alternatives.
  Everything else in ADR-002 stands.

## Context

The level-1 golden set was built from ADR-002's semantics by an independent reference
implementation, then reviewed by a person case by case, as a shop assistant would judge it.
The code matched the specification in all 61 cases, but 18 cases drew a comment, and most of
them showed the specification itself giving answers a shop assistant would not give. For each
product named in a comment, I checked which field produced the match:

| Cause | Cases | Example |
|---|---|---|
| Match in the description only | l1-026, l1-027, l1-028, l1-038 | "chef knife" returns a cheese board whose description mentions "three knives" |
| Match in the category name only | l1-039 | "puzzle" matches every product in *Games & Puzzles*, card games included |
| Match in colour or material only | l1-036 | "amber glass tumbler" returns a serum whose colour is amber and material glass |
| Matching more of the words earns nothing | l1-029 | for "fig candle", the votive trio matches both words but ties with a plain candle |
| A rare word counts the same as a common one | l1-035 | "garden" (3 products) weighs no more than "kit" (11) |
| Shopper words absent from the catalogue | l1-031, l1-044 | "headphones" misses earbuds; "noise cancelling" misses the tag "anc" |

Four smaller comments pointed at rules that stopped short of their own intent: l1-007, l1-013,
l1-049 and l1-054 (rules 5 to 8 below).

## Options considered

1. **Drop weak matches.** Cleaner lists, but "coffee" would lose the travel mug, whose only
   mention of coffee is in its description. That case was reviewed and approved as it is.
2. **Rank weak matches last, reward coverage and rarity** (chosen).
3. **Leave ranking to the agent.** The model can discard a cheese board, but only among the
   five products it is shown, and order decides which five those are.

## Decision

### Search (`search_products`)

1. **Fields.** *Strong* fields say what the product is: name (3), subcategory (2), tags (2),
   occasions (1.5), brand (1.5). *Weak* fields only describe it: material (1.5), colour (1.5),
   description (1). The category name is no longer searched: it matches up to 28 products at
   once, and `get_products_by_category` already covers it.
2. **Vocabulary**, kept in `data/decisions.yaml` as a human decision, under `search`:
   - `phrases` rewrites a multi-word shopper phrase into one catalogue word before the query is
     split ("noise cancelling" → "anc").
   - `synonyms` lists groups of words that mean the same thing to a shopper. A query word
     matches a field that contains any word of its group.

   The groups come from the 100 development conversations and the catalogue's own tags, not
   from the reviewed cases. Each group needs at least one word that the catalogue uses. The
   list stays small and reviewed; a missing word is a decision for a person, not something the
   code guesses.
3. **Order with a query** (default `relevance`):
   1. the number of query words matched in a strong field, highest first;
   2. the number of query words matched in any field;
   3. **rarity**: for each matched word, ln(N / df), summed, where N is the number of products
      searched and df the number of them the word matches;
   4. the field-weighted score (the best field per word, summed);
   5. rating (none last), review count, product id.

   With an explicit `sort`, products with a strong match still come before products with only
   weak matches, and each group is sorted as asked.
4. **Blocks derived from the ranking.**
   - `over_budget_matches` lists products above `max_price` whose keys 3.1 to 3.4 are at least
     those of the best product returned.
   - `unmatched_terms` lists words that match no product in any searched field, synonyms
     included.

### Smaller rules

5. **Unknown subcategory** (l1-007). `did_you_mean` names the subcategories in that category
   that hold a product whose name or tags contain the word asked for. "Lamps" points to
   *Lighting*, where both lamps are listed.
6. **Out-of-stock matches** (l1-013) are reported when there is a query, or when the shopper
   is seeing the last page of results (`next_offset` is null). ADR-002 said "a short page",
   which missed a result that exactly fills the page.
7. **Recipient** (l1-049). When `recipient` is set and no explicit `sort` is given, products
   for exactly that recipient come before products for `anyone`. With a query this is applied
   after keys 3.1 and 3.2. The filter's description also tells the model that, for a partner,
   `couple` is worth trying (l1-045).
8. **In-stock alternatives** (l1-054). Same subcategory first, closest in price. Then the rest
   of the category, ordered by tags shared with the original product and then by closest price.
   For the out-of-stock fig candle, that gives a scented diffuser instead of a picture frame.

### Not done in the tool

Some comments need an understanding of the product that keyword rules cannot give. These stay
with the agent:

- whether a sauna blanket counts as a throw;
- whether a camp mug substitutes for a glass tumbler;
- whether incense suits a child (the client's data says `anyone`, which is reported as a data
  quality issue);
- offering another puzzle for the out-of-stock city-map jigsaw. That one is already one call
  away: `get_product_details` on it returns in-stock puzzles from its subcategory.

## Consequences

- The level-1 set moves to v2. Its expectations come from the reference implementation updated
  to these rules. The cases whose result changes, and six held-out cases registered before
  these rules were written, go back to human review. The rest keep their approval.
- The served `catalog_version` covers the vocabulary as well as the products, so a change of
  synonyms is traceable in every response like a change of data.
- Ranking is still explainable in one sentence per key. That matters, because the review is
  done by a person reading results, not by a metric.
