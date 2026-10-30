# ADR-006 · The main word of a query, missing terms, and near misses under a filter

- **Status:** accepted · 2026-10-30
- **Deciders:** Samuel Viciana
- **Related:** ADR-005 (search relevance). Supersedes ADR-005 on which products a multi-word
  query returns, on the weight of a synonym, and on when `out_of_stock_matches` and
  `over_budget_matches` appear. Extends ADR-002's `recipient` filter to several values. The
  ranking keys of ADR-005 stand.

## Context

The second human review of the level-1 set (v2, 27 cases) left 16 comments. In nine of them,
the reviewer struck out products that match a modifier of the query but not the thing asked
for. ADR-005 had already moved them to the end of the list. The reviewer still did not want
them listed:

| Case | Query | Struck out | Why it matched |
|---|---|---|---|
| l1-064 | leather notebook | leather watch strap, weekender bag | "leather" in tags |
| l1-066 | wireless speaker | vertical mouse | "wireless" in name |
| l1-065 | tea set | coaster set, resistance bands, incense | "set" in name; "green tea" in a description |
| l1-062 | wooden board game | balance board (first) | "wooden" and "board" in tags |
| l1-026, l1-027 | chef knife | cheese board | "knives" in its description |
| l1-028 | city map jigsaw | atlas | "map" |
| l1-036 | amber glass tumbler | serum, pour-over set, infuser pot | colour and material |
| l1-038 | throw blanket | lamp, ladder, basket | descriptions |

Five other comments asked for blocks the tool did not give: the out-of-stock hammock on a
filtered browse (l1-067), a kids' night light just above the budget (l1-049), the scented
candle before a perfume found through a synonym (l1-063), the subcategory in the error for
"garden" (l1-005) and couple products for an anniversary (l1-045).

## Options considered

All three are deterministic, and all were measured on the 67 cases before deciding.

1. **The product type from the client's CSV as a filter.** The first tag of every row names
   what the product is (`notebook`, `speaker`, `candle`, `strap`): 115 types over 150 products.
   A query word that is a type would keep only products of that type. It removes all nine kinds
   of noise, but it breaks five approved cases: "chef knife" loses the sharpening stone (type
   `sharpening`), "coffee" loses the travel mug, "pasta" loses the pasta bowls, and "herb
   garden kit" keeps one product. The first tag is too narrow to be a filter. Rejected.
2. **The main word of the query** (chosen). In English the last word of a noun phrase names
   the thing ("leather *notebook*", "wireless *speaker*"). Over the 67 cases it fixes the nine
   comments and changes one approved case: "fig candle" drops a fig perfume, which is not a
   candle either.
3. **Leave ranking as it is and let the agent discard.** That is the cheapest option, but the
   agent sees five products, and the noise takes some of those five places.

The review also showed the limit of keyword rules. What is still left after option 2 cannot be
told apart by words. Open-ear earbuds are not noise cancelling. Passive speakers are not
wireless. A camp mug might replace a tumbler. The model reads those well. What the model lacks
is the *reason* a product was listed. Hence `missing_terms`.

## Decision

1. **Main word.** When a query has two or more meaningful words, the last specific one names
   the product. If at least one searched product has it, or a synonym of it, in a strong field
   (name, subcategory, tags, occasions, brand), only those products are listed. Otherwise the
   query is not narrowed. Rarity is still counted over the whole catalogue. A one-word query is
   never narrowed, so "coffee" keeps the travel mug.
2. **Generic words.** `search.generic` in `data/decisions.yaml` lists words that say how a
   product is packaged, not what it is: set, kit, pack, pair, collection, bundle, trio, duo.
   They are dropped when the query has another word ("tea set" searches for tea) and kept when
   alone ("kit"). "box" stays out of the list because it can be the product.
3. **Two synonym groups**, `[wood, wooden]` and `[notebook, journal]`. Both spellings appear in
   the development conversations.
4. **A synonym counts half.** A field that holds only a synonym of the query word scores half
   its weight. "earbuds" finds headphones, but earbuds come first.
5. **`missing_terms`.** Each listed product that lacks some query words carries them. For
   "leather notebook", the plain notebooks say `["leather"]`. The open-ear buds in "sony noise
   cancelling headphones" say `["sony", "anc"]`. The field is absent when a product matches
   every word.
6. **Several recipients.** `recipient` takes one value or several, comma-separated
   (`her,couple`), like `exclude`. Products for any of them, or for `anyone`, are listed, and
   those for the recipients asked for come first (ADR-005 rule 7). The server validates the
   values. The OpenAPI schema gives a pattern in place of the enum, and the description lists
   the values.
7. **Near misses under a filter.** When `recipient` or `occasion` is set, the shopper has said
   who or what the gift is for:
   - `out_of_stock_matches` is reported on every page of a browse, not only the last;
   - `over_budget_matches` is reported without a query too. The order is the best match, then
     the recipients asked for, then the nearest price above the budget.

   Without those filters, a plain category listing behaves as before. Applying these blocks to
   every request changed about twenty approved cases, most of them with noise.
8. **The subcategory in the error.** This one needed no code. The `unknown_category` error for
   "garden" already said "Call get_products_by_category with category 'home-living' and
   subcategory 'Garden'", but the review sheet did not show `hint`. Error cases now record it.

## Freeze

Ranking stops changing here. After two review rounds, each new rule risks fitting the
reviewed cases rather than the catalogue. From now on, a disagreement with the order of
results becomes a rule only if the level-2 evaluation shows the agent recommending the wrong
product because of it.

## Consequences

- The level-1 set moves to v3: 74 cases, including six new held-out cases registered in git
  before this decision was implemented. The six of ADR-005 informed these rules, so they no
  longer count as held out.
- Known cases the words cannot settle stay with the agent, which now sees `missing_terms`:
  open-ear buds (l1-031), mugs for a tumbler (l1-036), incense for children (l1-049, a data
  issue), chess and backgammon as board games and a console out of stock (l1-062), bath salts
  as scented (l1-063), planners for a notebook (l1-064), passive speakers (l1-066).
- Response size: the largest default page is 620 tokens and the largest page 1,044, both
  under their limits.
