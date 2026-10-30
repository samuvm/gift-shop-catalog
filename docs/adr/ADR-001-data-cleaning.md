# ADR-001 · Cleaning the catalogue export: rules in code, judgements in a file

- **Status:** accepted · 2026-10-30
- **Deciders:** Samuel Viciana
- **Related:** ADR-003 (no LLM enrichment), `data/decisions.yaml`, `scripts/audit_csv.py`

## Context

The client's only artefact is a CSV export (152 rows, 17 columns). The audit found inconsistent
category spellings, two products listed twice under different IDs, sentinel values (stock 999,
shipping 0) and missing fields. The client will send new exports. So cleaning must be repeatable
without anyone editing the CSV by hand, and anything new and unexpected must reach a person
before it reaches a shopper.

## Decision

`make ingest` reads the raw export and `data/decisions.yaml` and writes the catalogue the
service serves (`data/build/catalog.json`) plus a report (`data/build/ingest-report.json`).
Both outputs are committed: a new export shows up as a reviewable diff.

**1. General rules live in code, with unit tests.** They hold for any export:
trim whitespace; empty means missing (`null`), never zero; category spellings compare
case-insensitively with `and` read as `&`; `|`-separated fields become lists of lower-case
values; `yes`/`no` becomes a boolean.

**2. Judgements live in `data/decisions.yaml`.** Each one was made once by a person and has a
reason next to it: the 11 canonical categories and their ID prefixes, the allowed recipient
and occasion values, each cross-listed pair, the meaning of stock 999 and shipping 0, the low
stock threshold, and how much of the catalogue may disappear in one export.

**3. Anything the rules and decisions do not explain stops the ingest.** The report lists each
pending anomaly with its code and rows, and the previous catalogue stays in place. Stopping
cases:

| Code | Anomaly |
|---|---|
| `unknown_category` | A category that matches no canonical name after the general rules |
| `prefix_mismatch` | An ID prefix that disagrees with its category |
| `duplicate_id` | The same product ID twice in one export |
| `undeclared_cross_listing` | Two IDs identical in every field except category, not declared |
| `stale_decision` | A declared cross-listed pair that is no longer identical, or with only one of its IDs left (both gone is reported as an unused decision, not a stop) |
| `invalid_value` | A required field missing, a number that does not parse or is out of range, a recipient or occasion outside the allowed list, `gift_wrap` not yes/no |
| `schema_mismatch` | Missing or unexpected columns |
| `mass_removal` | More products removed than the allowed share, compared with the current catalogue |

**4. Data-quality issues are reported, not blocked.** Missing ratings, missing occasions and
descriptions too short to say anything ("Great gift.", "A card.") are listed for the client.
The service exposes them as missing; nothing is invented.

**5. Each export replaces the catalogue.** An export is a full snapshot, so the report shows
products added, changed and removed against the current catalogue. Upsert alone was rejected:
it never removes a product the client delisted, and the agent would keep recommending it.

**6. Cross-listed products keep both IDs.** Orders in the client's system may reference
either. Browsing a category shows the product under that category's ID. A catalogue-wide search
shows it once, under the declared primary ID, with `also_listed_as`. Details resolve both.

**7. Derived fields, computed by code, never typed in:** `availability` (`in_stock`,
`low_stock`, `out_of_stock`, `unlimited`), `is_digital`, `category_slug`, `search_text`
(every attribute including the description) and `search_text_compact` (without it).

## Consequences

- Same export plus same decisions gives a byte-identical catalogue (goal G-INGEST-CLEAN, and a
  determinism test).
- Seeded-anomaly fixtures, one per stopping code, prove the ingest stops and names exactly
  that anomaly (goal G-INGEST-STOPS).
- The client's text is served as-is. Descriptions that refer to neighbouring products ("Lighter
  than the Ember") are left alone; the agent's prompt handles them.
- Not built: partial (delta) exports, an upload page, live reload. A new export is a commit and
  a redeploy.
