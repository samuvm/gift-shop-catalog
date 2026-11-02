# Gift Shop Catalog

A catalogue service and a gift-finding agent for a small online gift shop, built for the
indigo.ai AI Forward Deployed Engineer assignment.

- **Catalog Service** (Python, FastAPI): four read-only tools over REST, described by an
  OpenAPI document written for a language model, and the same four tools over MCP
  (Streamable HTTP). It serves a catalogue cleaned from the client's CSV export by a
  repeatable, guarded ingest.
- **Gift finder agent** on the indigo.ai platform: it turns a vague or precise request into at
  most three products, each with a reason, in the shopper's language, inside a narrow web-chat
  widget.
- **Landing page** of an invented shop, *Ribbon & Co.*, with the web chat embedded.

## Links

| What | Where |
|---|---|
| Landing page with the chat | https://catalog.178.18.243.118.sslip.io/ |
| OpenAPI document (no key needed) | https://catalog.178.18.243.118.sslip.io/openapi.json |
| MCP endpoint (Streamable HTTP) | https://catalog.178.18.243.118.sslip.io/mcp |
| Health | https://catalog.178.18.243.118.sslip.io/health |
| Agent test page | `<TEST_PAGE_URL>` |
| How AI tools were used in this work | [`AI_WORKFLOW.md`](AI_WORKFLOW.md) |

Every data endpoint and `/mcp` need the header `X-API-Key`. Without it they answer 401 with a
body that says how to send it. The landing page, `/openapi.json` and `/health` are public.

The hostname uses sslip.io, which embeds the server's IP address in the name. Decided: no
domain was bought for a demo, because sslip.io gives a valid Let's Encrypt certificate at no
cost and a server IP is not a secret. A client deployment would sit behind the client's own
domain and proxy.

## Repository layout

| Path | What it holds |
|---|---|
| `src/catalog/tools.py` | The four tools, defined once: name, description for the model, parameters, response schema |
| `src/catalog/service.py` | `execute()`: one entry point per tool call, shared by REST and MCP; input normalisation; response bodies |
| `src/catalog/domain/` | The catalogue in memory: search, browse, details, ranking, near misses. No web framework imports |
| `src/catalog/ingest/` | CSV + decisions → served catalogue and report, with every stopping rule |
| `src/catalog/api/` | FastAPI app (`app.py`), generated OpenAPI (`openapi.py`), MCP server (`mcp.py`), landing page |
| `data/gift-shop-catalog.csv` | The client's export, as received. Never edited |
| `data/decisions.yaml` | Human judgements with a reason each: categories, cross-listings, sentinels, guards, search vocabulary |
| `data/build/` | `catalog.json` (what the service serves) and `ingest-report.json`. Committed, so a new export is a diff |
| `agent/system-prompt.md` | The agent's prompt, field by field as the platform takes it, with a version history |
| `evals/` | Level-1 tool cases, level-2 cases and recordings, simulation scenarios, ingest and MCP evals, reports |
| `docs/adr/` | Architecture decisions (append-only) |
| `docs/GOALS.yaml` | Every goal with its threshold, command and artefact, sealed by `docs/thresholds.lock` |
| `docs/PLATFORM.md` | How the agent is configured on the platform, and the model comparison |
| `docs/JOURNAL.md` | Engineering journal: what was tried, measured, kept and discarded, block by block |
| `scripts/` | Spec lint, secrets check, coverage summary, remote checks, scale probe, raw CSV audit |

## Architecture

```
 client CSV ──┐
              ├─ make ingest ──► data/build/catalog.json ──► (image) ──► Catalog in memory
 decisions ───┘   rules + guards     + ingest-report.json                      │
                  stop on anything                                             ▼
                  not explained                                service.execute(tool, args)
                                                                 ▲                   ▲
                               tools.py ──► OpenAPI (REST) ──────┘                   │
                                   └──────► MCP tool list (/mcp) ────────────────────┘
```

**One service, one tool definition, two transports.** `tools.py` holds each tool's name,
descriptions and parameters once. The OpenAPI document and the MCP tool list are both generated
from it, and every REST route and every MCP `tools/call` goes through `service.execute`.
Decided: generate both from one source, because two hand-written copies of a tool description
drift, and the model's behaviour depends on every word of it. `make eval-mcp` checks that MCP
returns the same bytes as REST on every level-1 case (ADR-002, ADR-008).

**The ingest is the only code that reads the CSV** (ADR-001, ADR-009). General rules live in
code with tests (trim, case, `and` → `&`, empty means missing, never zero). One-off judgements
live in `data/decisions.yaml`, each with its reason (11 categories, two cross-listed products,
stock 999 = unlimited gift card, the search vocabulary). Anything else stops the ingest with a
named code and keeps the previous catalogue: unknown category, duplicate ID, invalid value,
instruction-like product copy, wrong schema, non-UTF-8 or empty file, ragged row, mass removal
or mass price change. Each export is a full snapshot, diffed against the current catalogue, and
the output is byte-identical for the same inputs.

**In-memory snapshot** (ADR-004). The service loads `catalog.json` (152 listings, 150 products)
at startup and answers from memory; search p95 is 0.20 ms in process. Search is a linear scan:
a ×100 synthetic catalogue measured 35–39 ms p95 and 64 MB. Decided: no database, because at
this size it adds a component and no measurable gain. The real weakness is stock freshness:
stock is as fresh as the last export. Every response carries `meta.catalog_version`, so any
answer traces back to the export behind it.

## Tool design for an LLM

The platform turns each OpenAPI operation into a tool, and the model decides what to call
**from the names and descriptions alone**. So the descriptions are the interface, and the
responses are written to be read by a model that must not invent anything (ADR-002).

### Four tools, one job each

| Tool | Route | Job |
|---|---|---|
| `get_categories` | `GET /categories` | What the shop sells: categories, subcategories, counts, price ranges, allowed filter values |
| `get_products_by_category` | `GET /categories/{category}/products` | Browse one category the shopper named |
| `search_products` | `GET /products/search` | Find products across the catalogue from a description |
| `get_product_details` | `GET /products/{product_id}` | Everything about one product, including caveats and in-stock alternatives |

The brief requires the first, second and fourth. Decided: add `search_products`, because a
100-conversation stress test (671 shopper messages in English, Spanish and Italian) showed that most requests
name a kind of product, a hobby or a brand, not a category. Search takes no `category`
parameter on purpose, so the model never chooses between two tools that do the same thing.
Rejected, with reasons in ADR-002: similar-products, batch details, shop policies (there is no
policy data, and a tool would invite the model to fill the gap), `recommend_gift` (that is the
agent's job and it would hide the reasoning), and a "guard" tool for injection (it only runs if
the manipulated model chooses to call it).

Shared filters: price range, `recipient` (one or several, `her,couple`), `occasion`,
`max_shipping_days`, `exclude` (words matched in name, subcategory, tags and material, never the
description), `include_out_of_stock`, `sort`, `limit` (1–10, default 5) and `offset`.

### What a response tells the model

A list item carries everything a recommendation needs without a second call: price,
availability, rating and review count, recipient, occasions, shipping days, gift wrap and the
shop's own description, where the caveats live ("needs an amplifier"). Optional blocks appear
only when they carry information:

| Block | Answers |
|---|---|
| `out_of_stock_matches` | "Do you have the City Map jigsaw?" It exists but is out of stock, so the agent never says the shop does not sell it |
| `in_stock_alternatives` (details) | What to offer instead of an out-of-stock product: same subcategory first, closest in price |
| `over_budget_matches` | "A chef's knife under €100": the only one costs €149. Better matches above the budget, with `over_by_eur` |
| `unmatched_terms` | "Sony headphones": the shop does not carry Sony, so the agent says so, then offers the closest |
| `missing_terms` | Per product, the query words its record does not mention. The plain notebook for "leather notebook" says `["leather"]` |
| `suggestions` | When results are few: the filter change that adds results, e.g. `max_price` → 149 adds 3. An exclusion is never suggested for removal |
| `meta` | `total_matches`, `returned`, `next_offset` for "show me more", the filters applied, today's date, catalogue version |

An empty result is a 200 with `total_matches: 0` and suggestions, not an error. Page size is
measured in tokens (`o200k_base`) on every level-1 case, against limits of 1,150 (default page)
and 1,800 (10 items); see *Measured*.

### Tolerant inputs, recoverable errors

The server resolves what it can and says so in a `note`: a category by slug, name in any
spelling or one word ("kitchen"); a product ID as `kd-7`, `KD7` or `kd-007`; closed-set values
in any case (`HER`, `Birthday`); a `limit` above 10 clamped. Decided: tolerate these, because a
model that capitalises a value should not pay a round trip for it. What cannot be resolved is a
4xx with one shape:

```json
{"error": {"code": "unknown_category",
           "message": "'garden' is not a category; Garden is a subcategory of Home & Living.",
           "hint": "Call get_products_by_category with category 'home-living' and subcategory 'Garden'.",
           "allowed_values": ["beauty-wellness", "..."], "did_you_mean": ["home-living"]}}
```

Strict where strictness informs: `nan`, `inf` and `min_price > max_price` are 400s with a hint.
An inverted range used to return an empty 200, which a model reads as "the shop has nothing".

### Search, deterministic

Keyword scoring, called that, with no model in the loop (ADR-003, ADR-005, ADR-006, ADR-007).
Strong fields say what a product is (name, subcategory, tags, occasions, brand); weak fields
describe it (material, colour, description). Results order by coverage of the query in strong
fields, then any coverage, then word rarity, then rating. In a multi-word query the last
specific word names the product ("leather *notebook*"), so a leather watch strap is not
listed. A small, reviewed vocabulary in `decisions.yaml` maps shopper words to catalogue words
("noise cancelling" → `anc`, "kindle" → e-reader). Ranking was frozen after three human
reviews. What words cannot settle (open-ear buds are not noise cancelling) is left to the agent,
which sees `missing_terms` for exactly that reason.

### What the platform taught us

Found on screen, acted on, recorded in `docs/PLATFORM.md`:

- **The platform reads `summary`, not `description`.** The first import gave the model
  one-line summaries. The served spec now puts the full text in both, so a fresh import needs no
  hand edits.
- **An enum can stop the model from searching.** Asked for "the garden category", the model
  picked the nearest enum value (`outdoor-travel`). The browse tool now tells it to search when
  the shopper's word is not a category.
- **4xx bodies reach the model.** Asked for "lamps", the agent got the 404 and called again with
  `Lighting`, the subcategory the error names.
- The served spec is OpenAPI 3.0.3 with every schema and enum inline (no `$ref`, `oneOf`), so
  the platform's form editor can still edit each operation. `make spec-lint` enforces it.

## The agent

### Platform setup

| Piece | Configuration |
|---|---|
| **Gift finder** | The only agent with tools. Prompt fields from `agent/system-prompt.md`. Model gpt-5.6-luna (EU), reasoning Low, creativity Low, short memory 20 messages, all tool calls kept in memory, 600 answer tokens |
| **General** | The platform's fallback agent, no tools: small talk, weather, returns, payments, tracking. Never invents a policy, never names products, steers back to the gift |
| **Jailbreak agent** | Receives jailbreak attempts routed by the Security layer |
| **Security layer** | On, in **Shadow** mode: it classifies and records every message, blocks nothing yet |
| **Tools** | One Tool Collection from `/openapi.json`, header `X-API-Key: [[CATALOG_API_KEY]]` from a workspace secret |

Decided: Shadow before Enforce, because Enforce on "out of scope" can block a mixed message that
also holds a real gift request, and the false positives should be read first. The platform's
Hallucination guardrail is not available in this workspace; the prompt rule "every product fact
comes from a tool call" covers that risk, and level 2 measures it.

### Model choice, by controlled comparison

gpt-4.1-mini padded answers and misread results ("nothing under 80" beside a 78-euro match),
and no prompt rule fixed it. Five models then ran the same nine scenarios with everything else
fixed; a public benchmark (τ²-Bench Airline) chose which to try, the scenarios decided.
**gpt-5.6-luna** passed the core six after reading every Fail, flagged over-budget items with
the gap and kept the shopper's language, at half gpt-4.1-mini's price. Two models ranked higher
by the benchmark failed here (wrong language; raw tool-call tokens in the chat). Full table:
`docs/PLATFORM.md`.

### Conversation design

The prompt (v8) is written in the platform's fields: description, goal, tone, ten general rules
and five sections (asking questions, recommendation format, using the catalogue, reading the
results, outside the shop). The rules that shape a conversation:

- **At most one question per message, and at most two before showing products.** As soon as
  the person, a budget or a kind of product is known, search and show, then ask. A vague
  "I need a gift" gets one light question: who is it for, and roughly how much?
- **Up to three products per message**, best first, as a numbered list with one line per
  product: `1. **Name** · €price · usually ships in N days — one reason tied to what the shopper
  said`. "Only N left" when stock is low. One short next step after the list. Decided: a list,
  because the widget's rendering ran two-line blocks together however the blank lines were
  placed (prompt v5 on the platform), and numbers let the shopper say "the second one".
- **Every product fact comes from a tool call.** Search again whenever a condition changes.
  Before saying the shop has or lacks something, search for it.
- **Reply in the language of the shopper's last message**; tool queries stay in English
  catalogue words.
- **Never guarantee delivery.** Shipping days are the shop's estimate: "usually ships in 3 days".
- **Read the blocks:** say "out of stock", never "we don't sell it"; state how far over budget a
  liked item is; say plainly when the shop does not carry a brand; "show me more" pages with
  `offset` and the same filters, and never raises the budget on its own.

### Off-topic and adversarial turns

Layered, with nothing that depends on the model choosing to protect itself:

1. **Before the model:** the Security layer classifies each message; jailbreak attempts go to
   the Jailbreak agent, out-of-scope requests to General.
2. **In the prompt:** weather or code gets one sentence and a question back to the gift.
   Returns, payments, discounts and tracking: "I have no information on that", a pointer to
   customer service, no guessing. Role changes and requests for the instructions are ignored.
   "Do you have AirPods?" is a shop question, so it is searched, not declined.
3. **In the service:** the tools only read public catalogue data, so a successful injection can
   only read what is already public. Product copy that reads like an instruction stops the
   ingest (`instruction_like_text`), matched on folded text so zero-width characters do not hide
   it.

Level 2 measures the second layer: none of the 36 off-topic cases calls a catalogue tool.

## Evaluation

Test ≠ eval. Tests pin code behaviour and must always pass (`make gate-fast`). Evals measure
quality against a threshold, each with its command and artefact in `docs/GOALS.yaml`. TDD was
mandatory in `domain` and `ingest`; the API layer is contract-tested, including a snapshot of
the served OpenAPI and a check that the route parameters match the spec.

- **Level 1, the tools (deterministic).** Cases across the four tools: arguments → exact product
  IDs, blocks and errors, run over HTTP. Expectations come from an independent reference
  implementation (`evals/golden/l1/oracle.py`, stdlib only). The owner then reviewed every case
  as a shop assistant would, in three rounds (`evals/golden/l1/review-v*.md`); the comments
  drove ADR-005 to ADR-007, and held-out cases were registered before each round of rules.
- **Level 2, sentence → tool and arguments, with a real model.** 150 cases (36 off-topic), each a
  conversation so far plus the latest message. The model reads only the served spec and the
  prompt, through function calling. It runs on Gemma 4 26B locally (the platform offers
  gemma-4-26b), temperature 0, and every response is recorded so the numbers re-score offline
  with no model and no key.
- **Level 3, conversations: the platform's Simulations.** 15 scenarios in
  `evals/simulations/scenarios.csv`: the brief's six (`core`), three more (`extra`) and six
  built from the tools' real output (`extended`). The judge sees the conversation, not the
  catalogue, so criteria judge behaviour and treat a fact as wrong only when it contradicts the
  reference. Every Fail is then read against the catalogue before a result is recorded; the
  table gives both numbers.

**G-L2-TOOL sat below its threshold for most of the project, and the threshold was not lowered.** Tool choice on the local model:
prompt v3 87.3%, v4 81.3%, v5 88.0%, v6 88.7%, v7 87.3%, v8 90.0%, against ≥ 90%. v8 meets it exactly, but
changes that did not touch tool choice moved this number by up to 6.7 points, so it is read as
"about 88–90%", not as a pass earned by v8. Most misses are the model answering from
earlier messages instead of calling a tool. Decided: keep 90%, because lowering it after the
fact would move the goalpost, and tuning the prompt further for a model that is not in
production would optimise the wrong thing. The production model passes the core scenarios. The
6.7-point swing from a layout-only change (v4 → v5) is recorded as this model's sensitivity to
wording, not claimed as an improvement.

### Measured

All numbers below are the latest run of each command. Reports are in `evals/reports/`.

| Metric | Value | Threshold | n | Command | Artefact |
|---|---|---|---|---|---|
| Unit and contract tests | 522 passed | all | 522 | `make test` | — |
| Line coverage, domain + ingest | 99.77% | ≥ 85% | 864 lines | `make test` | `coverage-latest.json` |
| Layer violations (domain ↛ api/mcp, api ↮ mcp) | 0 | 0 | — | `make test` | `arch-latest.json` |
| Data endpoints rejecting a missing, wrong or empty key | 12/12 | all | 12 | `make test` | `auth-latest.json` |
| Level 1: exact product IDs | 81/81 | all | 81 | `make eval-l1` | `l1-latest.json` |
| Level 1: largest response, default / max page | 621 / 1,045 tokens | ≤ 1,150 / 1,800 | 81 | `make eval-l1` | `l1-latest.json` |
| Level 1: cases approved by the owner | 60 approved, 3 deferred to level 2, 18 pending | — | 81 | review sheet | `evals/golden/l1/REVIEW.md` |
| Level 2: right tool (gemma4:26b, prompt v8) | 90.0% | ≥ 90% (met at the threshold; see the note on noise) | 150 | `make eval-l2` | `l2-latest.json` |
| Level 2: right arguments, given the right tool | 95.5% | ≥ 85% | 150 | `make eval-l2` | `l2-latest.json` |
| Level 2: off-topic cases that call a tool | 0% | ≤ 5% | 36 | `make eval-l2` | `l2-latest.json` |
| Level 2: replay mismatches | 0 | 0 | 150 | `make eval-l2` | `l2-latest.json` |
| Simulations, core (gpt-5.6-luna), judge / after reading | 79% / 92% | 100% | 24 (4 runs × 6) | `make sim-report` | `simulations-latest.json` |
| Simulations, extra, judge / after reading | 56% / 89% | — | 9 (3 runs × 3) | `make sim-report` | `simulations-latest.json` |
| Simulations, extended, judge / after reading | 5/6 / 6/6 | — | 6 (1 run) | `make sim-report` | `simulations-latest.json` |
| Ingest: client export, decisions pending | 0 | 0 | 152 rows | `make ingest` | `data/build/ingest-report.json` |
| Ingest: seeded anomalies stopped exactly | 17/17 | all | 17 | `make eval-ingest` | `ingest-latest.json` |
| MCP: same result as REST | 81/81 | all | 81 | `make eval-mcp` | `mcp-latest.json` |
| MCP: protocol checks over Streamable HTTP | 16/16 | all | 16 | `make eval-mcp` | `mcp-latest.json` |
| OpenAPI rule violations | 0 | 0 | — | `make spec-lint` | `spec-lint-latest.json` |
| New secrets outside the reviewed baseline | 0 | 0 | — | `make secrets` | `secrets-latest.json` |
| Deployed p95 latency, list and search | 193.4 ms over one reused connection (357.9–384.9 ms opening a new TLS connection per call) | ≤ 300 ms | 3 runs × 200 calls, 20 warm-up |  `make latency URL=…` | `latency-latest.json` |
| Public checks from outside | 7/7 | all | 7 | `make check-public URL=…` | `public-latest.json` |

Simulations are recorded per run in `evals/simulations/results.csv` with both verdicts; runs
of the same model and agent version count together, so re-running cannot turn a result green.
The numbers above are prompt v4 on gpt-5.6-luna. The only real core failures (one run) share one
cause, vocabulary: "she likes cooking" found only the cookbook, and "tech gadgets" missed the
speaker and the camera because category names were not searched. ADR-010 fixes both. Latency is measured over one reused connection, as a server-to-server client such as the
platform calls; from the client machine a new TCP and TLS handshake per call adds about 115 ms
(journal blocks 29–30).

## Running it locally

Requirements: [uv](https://docs.astral.sh/uv/) (Python 3.13 is pinned in `.python-version`).
Level 2 refresh also needs Ollama with `gemma4:26b`; replaying the recordings does not.

```bash
uv sync
cp .env.example .env          # set CATALOG_API_KEY
make run                      # http://localhost:8000
curl -H "X-API-Key: $CATALOG_API_KEY" "localhost:8000/products/search?query=candle&max_price=40"
```

| Variable | Required | Meaning |
|---|---|---|
| `CATALOG_API_KEY` | yes | The key callers send in `X-API-Key`. The service refuses to start without one |
| `WIDGET_TOKEN` | no | The platform's workspace token for the web chat on `/`. Without a valid one, the page renders without the chat |
| `SHOP_TIMEZONE` | no | The zone for `meta.today`. Default `Europe/Rome` |
| `CATALOG_URL` | no | Runs `make eval-l1` against a deployment instead of in process |
| `TEST_PAGE_URL` | no | The agent's test page, checked by `make check-public` |

| Target | What it does |
|---|---|
| `make gate-fast` | Lint, types and the full test suite: what must stay green after each change |
| `make test` | pytest with the coverage, auth and layer reports (`make lint`, `make typecheck` run the rest) |
| `make ingest` | CSV + `decisions.yaml` → `data/build/catalog.json` and the report; exit 1 means a decision is needed |
| `make eval-ingest` | Seeded-anomaly fixtures must each stop the ingest with exactly their anomaly |
| `make eval-l1` | Level-1 cases over HTTP: exact match and response size in tokens |
| `make golden-l1` | Rebuild the level-1 cases from the reference implementation, plus the review sheet |
| `make eval-l2` | Level 2 replayed from the recorded model responses |
| `make eval-l2-refresh` | Level 2 calling the local model for cases without a recording |
| `make eval-mcp` | MCP against REST on the level-1 cases, plus protocol checks; `URL=` for a deployment |
| `make spec-lint` | Lint the served OpenAPI against the platform's rules |
| `make secrets` | Secrets in tracked files that are not in the reviewed baseline |
| `make latency URL=…` · `make check-public URL=…` | p95 latency and public checks against a deployment |
| `make audit-csv` | Independent audit of the raw export, standard library only |

**Docker.** `docker build -t gift-shop-catalog . && docker run -p 8000:8000 -e
CATALOG_API_KEY=change-me gift-shop-catalog`. The image ships the committed catalogue (no ingest
step), runs as a non-root user and declares its own health check. It is deployed on a Contabo VPS
with Coolify and Traefik. A new export is `make ingest`, a reviewed diff, a commit and a redeploy.

## Time spent

Approximate durations from the engineering journal, which records each block of work.

| Day | Main work | Time |
|---|---|---|
| Thu 29 Oct | Brief, platform guide, goals, hosting choice, data audit, pipeline design | ≈ 7 h |
| Fri 30 Oct | Ingest and domain test-first, 100-conversation stress test, tool interface, REST and OpenAPI, three human reviews of the level-1 cases | ≈ 7 h 20 |
| Sat 31 Oct | Deployment, level 2 on a local model, prompt v2–v3, platform configuration, first simulations | ≈ 6 h 15 |
| Sun 1 Nov | Prompt v4–v5, model comparison, simulation criteria, re-export safety, MCP, landing page, 15-scenario run | ≈ 5 h 55 |
| **Total so far** | | **≈ 26 h 30** (to be finalised at submission) |

| Area | Time |
|---|---|
| Understanding the brief and the platform, goals, working rules | ≈ 4 h 15 |
| Data: audit, ingest, re-export safety | ≈ 3 h 25 |
| Tool interface and search, including three review rounds | ≈ 6 h 55 |
| Hosting and deployment | ≈ 1 h 30 |
| Agent: prompt, level 2, platform setup, model choice, simulations | ≈ 9 h 50 |
| Extensions: MCP and landing page (review and merge time) | ≈ 35 min |

## What was left out, and what I would do next

Left out on purpose, each with its reason in the ADR named:

- **A `/catalog/report` page** showing anomalies, decisions and the catalogue version. Cut for
  time; the same information is in `data/build/ingest-report.json`. A data-upload portal was
  rejected outright: a write path and a second auth scheme on a public sandbox (ADR-001).
- **LLM enrichment of product data** (ADR-003). Revisit when the catalogue reaches thousands of
  products or level 1 shows misses from vocabulary no column holds, with a grounding check by
  code and human review of changed rows.
- **A real search engine** (ADR-004): SQLite FTS5 at tens of thousands of products, then a search
  service with incremental ingest, live stock and cursor pagination.
- **Ingest gaps** (ADR-009): the removal guard has no per-export acceptance, only its ratio;
  header names are not normalised (`PRICE_EUR` stops, on purpose); look-alike letters from other
  scripts (Cyrillic `а`) can still hide an injection phrase.
- **Mutation testing.** Dropped from the goals: a new dependency, and it blocks nothing.

Next, in order:

1. **Enforce mode for the Security layer**, after reading the Shadow logs for false positives on
   mixed messages.
2. **More simulation repetitions.** One or two runs per suite can be luck; a pass rate needs
   several runs per scenario.
3. **Ranking comments deferred by the freeze** (ADR-006): a sauna blanket as a throw, incense for
   children (a client data issue), a pepper mill for "coffee grinder", chess as a wooden board
   game. They become rules only if the agent recommends the wrong product because of the order.
4. **`over_budget_matches` ordering:** for "coffee" it lists the €115 grinder above the €78
   pour-over set, because a name match beats a tag match. The nearer price is the better offer.
5. **The General agent's language:** it answers off-topic turns in the workspace language
   (Italian), not the shopper's.
6. **Bold product names:** the model rarely writes the `**` the format asks for, so names are
   not bold in the widget.
7. **Review the level-2 cases the model passed**, and the pending level-1 cases. Only level-2
   failures were reviewed by a person.

## Further reading

The decisions are in [`docs/adr/`](docs/adr/): data cleaning (001), tool interface (002), no LLM
enrichment (003), in-memory catalogue (004), search relevance (005–007), MCP server (008),
re-export safety (009). The reasoning behind them, including what failed, is in the
[engineering journal](docs/JOURNAL.md). Also: [platform configuration](docs/PLATFORM.md),
[goals](docs/GOALS.yaml), [agent prompt](agent/system-prompt.md), [AI workflow](AI_WORKFLOW.md).
