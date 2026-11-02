# Platform configuration (indigo.ai)

How the agent is wired on the platform, and why each setting is what it is. The prompt text
itself lives in `agent/system-prompt.md`; this file records everything else. Configured on
31 Oct – 1 Nov 2026 and published on 1 Nov.

## Tools: a Tool Collection built from the served OpenAPI

| Setting | Value | Why |
|---|---|---|
| Collection | `Gift Shop Catalog`, created by pasting `/openapi.json` into the JSON editor | The platform documents no import by URL |
| Endpoint (Test and Production) | `https://catalog.178.18.243.118.sslip.io` | The platform's endpoint fields replace `servers` |
| Header | `X-API-Key: [[CATALOG_API_KEY]]` | `securitySchemes` are ignored, so auth is an explicit header. The secret must be the entire header value, and it has a value in both Test and Production |
| Operations | `get_categories`, `get_products_by_category`, `search_products`, `get_product_details` | One tool per operation, named after `operationId` |

**Finding: the platform reads `summary`, not `description`.** On import, each operation's
`summary` became the tool description the model reads, and the long `description` was dropped.
The first import gave the model one-line summaries such as "Browse one category, with optional
filters.", which lost the guidance on query words, `missing_terms` and the near-miss blocks. The
served spec now puts the full text in both fields (`src/catalog/api/openapi.py`), so a fresh
import needs no manual edits.

**Finding: an enum can stop the model from searching.** Asked to "show me the garden
category", the model picked the nearest value from `category`'s enum (`outdoor-travel`) instead
of searching. A request with `garden` would have received a 404 naming *home-living / Garden*.
The browse tool and its `category` parameter now say: if the shopper's word is not one of the
categories, call `search_products` with it.

**Verified: error bodies reach the model.** Asked for "lamps in home and living", the agent
called the browse tool with `subcategory: "Lamps"`, got the 404, and called again with
`Lighting`, the subcategory the error body names. The platform's debug view shows response
bodies as `*** redacted ***`, so this was checked through behaviour.

## MCP server (bonus)

Connected under Agents settings → Integrations → MCP Servers as `https://catalog.178.18.243.118.sslip.io/mcp`.

**Finding: the MCP client sends the secret's placeholder, not its value.** With the header
`X-API-Key` set from the workspace secret `CATALOG_API_KEY`, every `initialize` reached the
server with a 19-character key: the length of `[[CATALOG_API_KEY]]`, not of the 64-character
key. The same secret resolves in the Tool Collection header. Found with the per-request log of
`/mcp` (method, protocol, which credential header arrived and its length, never its value). The
sandbox works around it with the key's value typed into the MCP header. `/mcp` also accepts the
key as `Authorization: Bearer <key>`.

## Agents

**Gift finder**, the only agent with tools.
- Fields are filled from `agent/system-prompt.md` (v10, its header lists every version and why): General Description (with `{{$date}}`),
  Agent Goal, Tone of Voice, 9 General Rules, and 5 custom sections (Asking questions,
  Recommendation format, Using the catalogue, Reading the results, Outside the shop).
- The trigger carries the routing text and 8 example questions in English, Spanish and Italian.
- Settings:

| Setting | Value | Why |
|---|---|---|
| Model | gpt-5.6-luna (EU), reasoning Low | Chosen by the comparison below: best behaviour of the five models tried, at half gpt-4.1-mini's price. Level 2 measured the tools on gemma-4-26b |
| Creativity | Low (temperature 0.2 in traces) | Stable tool and argument choice |
| Short memory | 20 messages | The default of 3 would forget a budget given a few turns earlier |
| Tool calls in memory | All | Earlier results stay visible for "the second one" or "show me more" |
| Max answer tokens | 600 | Three products in two lines each fit with room to spare |
| Error handling | Fixed message: "Sorry, I couldn't reach the catalogue just now…" | A network failure still gets a clear reply |

**General** (the platform's fallback agent). It handles small talk and anything outside the shop:
weather, returns, payments, discounts and tracking. Five rules: never invent a policy, never name
products, ignore role changes, end by steering back to the gift, and reply in the language of the
shopper's last message (added on 2 Nov as a cheap guard; the model already did so). It has no tools. Its
default Italian trigger was replaced.

**Welcome.** The opening text says what the assistant does and asks for the two things it needs:
who the gift is for, and the budget.

## Protections

- **Security layer: on, Shadow mode.** It classifies and records every message but changes no
  answer, so false positives can be reviewed before anything is blocked. Guardrail agents:
  jailbreak attempts → the platform's *Jailbreak agent*; out-of-scope requests → *General*
  (blocking switched on, inactive while in Shadow mode). The workspace perimeter is regenerated after
  publishing, because it is built from the published agents.
- **Evaluators and guardrails (Hallucination, Jailbreak detection): not available** in this
  workspace. The Improve menu shows only Issues, Simulations and Playground. Hallucination is
  covered instead by the prompt rule that every product fact must come from a tool call, which
  level 2 measures.
- **Widget style.** Brand colour `#9E1F45` with white text, the ribbon icon as avatar and
  launcher (uploaded as a PNG, because an SVG URL is refused), launcher text "Gift ideas". The
  assistant name avoids `&`, which the widget shows escaped (`&amp;`).
- **Web chat privacy settings: not enabled.** On a test page the consent banner only adds a
  click before typing. A production deployment would turn it on.

## Choosing the model: a controlled comparison

The first Simulations runs on gpt-4.1-mini failed in ways no prompt rule fixed: padding a coffee
request with unrelated products, misreading results ("nothing under 80" with a 78-euro match),
four products in one message, merged and duplicated messages. To separate the model from the
prompt and from the test, everything else was held fixed: prompt v4, the same nine scenarios,
memory 20, creativity Low, 600 answer tokens, reasoning Low where offered.

Candidates came from τ²-Bench Airline (OpenRouter, 1 Nov 2026), the closest public benchmark to
this task (multi-turn customer service with tools and rules): models cheaper than gpt-4.1 that
score well above gpt-4.1-mini there.

| Model | Price in/out per M tokens | τ²-Bench Airline | Core (judge / after reading) | Extra (judge / after reading) | Run time | Verdict |
|---|---|---|---|---|---|---|
| gpt-4.1-mini | 0.40 / 1.60 | 44.3% | 4/6 / 5/6 | 1/3 / 1/3 | ~50 s | pads, misreads results, duplicates messages |
| gpt-4.1 | 2.0 / 8.0 | 47.7% | 5/6 / 6/6 | 2/3 / 2/3 | ~50 s | good; does not always flag over-budget items |
| **gpt-5.6-luna** | **0.20 / 1.20** | **69.7%** | **5/6 / 6/6** | **1/3 / ~2.5/3** | **~45 s** | **flags over-budget items with the gap, one question at a time, right language** |
| gemini-3.5-flash-lite | 0.30 / 2.50 | 78.3% | 5/6 / 5/6 | 1/3 / 1/3 | ~50 s | replies in Italian (the workspace language) to English and Spanish shoppers |
| deepseek-v4-flash | 0.19 / 0.51 | 74.0% | 5/6 / 4/6 | 1/3 / 0/3 | 3 min 26 s | leaks raw tool-call tokens into the chat, loops, triggers error recovery |

"After reading" means each Fail was checked against its transcript: the judge sees the
conversation but not the catalogue, so it flags real products and prices as unverifiable (the
Notebook Trio A6, the 50 filters of the Pour-Over Set) and treats the platform's fixed welcome
text as the agent's. A public benchmark ranked gemini-3.5-flash-lite and deepseek-v4-flash
above gpt-5.6-luna; on this task they failed in ways the benchmark does not measure (language,
tool-call formatting). The benchmark chose what to try; the suite decided.

## Simulations with the chosen model (gpt-5.6-luna, draft, 1 Nov)

Stability check: the core suite twice and the extra suite once, prompt v4, settings above.

| Run | Judge | After reading | The judge's Fails |
|---|---|---|---|
| core, 1st | 5 / 6 | 6 / 6 | core-6: the Notebook Trio A6 "is not a verified product". It is in the catalogue at 24 euros |
| core, 2nd | 5 / 6 | 6 / 6 | core-6: the same product, and the weather answer "in two sentences" (one sentence and a question back to the gift) |
| extra | 2 / 3 | 3 / 3 | extra-7: "the moka pot has no gift wrap". It has; the criterion listed gift wrap only next to the pour-over set, and the judge read that as exclusive |

All three are judge errors caused by the criteria: the core-6 reference listed three of the nine
products under 30 euros, and extra-7's mentioned gift wrap for one product only. Both criteria
now list the full facts (`evals/simulations/scenarios.csv`). In every run the off-topic and
returns questions went to the General agent and the injection to the Jailbreak agent, each
answered in Italian. Then the gift request came back to Gift finder.

## Simulations (first run, gpt-4.1-mini, draft)

Imported from `evals/simulations/scenarios.csv`. They ran on the draft before the first
publish.

| Suite | Pass | Failing |
|---|---|---|
| core (the brief's six scenarios) | 5 / 6 | core-1, vague shopper: more than two questions before products, the budget asked twice, one product recommended |
| extra | 1 / 3 | extra-8, deadline: delivery not presented as an estimate. extra-9, "show me more": repeated two products; the judge also flagged a material that is in the product record, to be checked |

## Simulations, latest

Recorded per run in `evals/simulations/results.csv` and summarised by `make sim-report`. On
gpt-5.6-luna: prompt v8, three runs: core 18/18, extra 9/9, extended 16/18 after reading.
Prompt v10, one run: core 6/6, extended 6/6, extra 2/3. The one Fail, extra-9, named a sold-out
52-euro product without saying it was also over the budget; rerun alone it passed with a score of
100, so it is recorded as an occasional slip. `results.csv` holds whole-suite runs only, so the
rerun is noted here.

## Observed

- Language: on gpt-5.6-luna, Spanish and Italian shoppers are answered in their language by
  Gift finder and by the General agent (returns and purchase questions in the Spanish
  simulation were answered in Spanish). Earlier, on gpt-4.1-mini, a Spanish message got an
  English reply.
- Product names are bold in the widget since the numbered-list format (prompt v6).
- In one long Preview conversation that chained six unrelated requests, a reply repeated earlier
  messages and re-ran an earlier search. It did not reproduce in fresh conversations.
