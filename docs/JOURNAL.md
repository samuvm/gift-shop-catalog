# Engineering journal

Append-only. One entry per block of work: rough duration (no clock times), the approach we
started with, where we ended up and why, what was discarded, and any number with the command
that produced it. Negative results stay; they are what stops us repeating them.

---

## Day 1 · Thu 29 Oct · Block 1 · Sources and access (~1 h 15 min)

**Starting point.** The brief, a CSV and an email with a workspace token. The platform guide
(guide.indigo.ai) is the declared source of truth for building the agent.

**What happened.** The guide redirects to a login page for any non-browser client, so neither
`curl` nor a web fetch can read it. It does expose a GitBook MCP endpoint. Connecting to it
(OAuth) gave full-text search and page reads. We mirrored the whole guide locally (98 pages,
184 images) so that every later design decision can cite a page instead of memory. The
workspace export the sandbox offers contained only headers: the workspace is empty, as the
brief says ("starting from zero").

**Conclusion.** Every source is reachable and stored once. Nothing about the platform will be
assumed; when the guide is silent (tool-call timeout, which status codes reach the model), the
assumption is written down and checked in the Playground.

## Day 1 · Block 2 · Understanding the platform, planning, hosting (~2 h 30 min)

**Starting point.** Build a FastAPI service, import its OpenAPI, write a prompt.

**What the guide changed.**
- `securitySchemes` in the spec are ignored; auth is configured as tool headers. A secret must be
  the *entire* header value (`X-Api-Key: [[KEY]]` works, `Bearer [[KEY]]` is sent literally).
  So the service authenticates with an `X-API-Key` header: it is the scheme the platform
  supports without workarounds.
- `$ref`, `oneOf`, header parameters and nested bodies make an operation read-only in the
  platform's form editor. They still work, but the client's business team could no longer
  tweak a description without editing JSON. So the served spec will be flattened (inline
  schemas, inline enums) for the people who will maintain it after us.
- The guide says outright that product catalogues are integrated through APIs, not through
  the knowledge base (RAG). Search over the catalogue is therefore tools, not embeddings.
- Tool usage is decided by the model from the descriptions alone. The descriptions are the
  interface.

**Hosting.** Options: managed free tiers, a home desktop left on, or an existing VPS (Contabo)
that already runs Coolify with Traefik and automatic Let's Encrypt. We chose the VPS. It is
always on, gives HTTPS with no extra work, and costs nothing new. The hostname uses sslip.io,
which embeds the server IP. That is acceptable for a sandbox (a server IP is not a secret),
and the README explains what a client deployment would do instead (a domain behind a proxy).

**Testing strategy.** Three levels, kept separate because they answer different questions:
1. Tools: query → exact set of product IDs. Deterministic, must be 100%.
2. Interface: user phrase → expected tool and arguments, with a real model reading only our
   spec. This measures the brief's first priority directly. 150 cases with at least 15%
   off-topic negatives, enough to detect a ~6-point change between two versions of the
   descriptions with a paired bootstrap.
3. Conversation: the platform's own Simulations on the brief's scenarios.

**Conclusion.** The measurable goals are written before any code (`docs/GOALS.yaml`). Core
work (service, agent, delivery) is separated from extensions (MCP, landing page), which never
block.

## Day 1 · Block 3 · Data audit (~1 h 45 min)

**Starting point.** Expected a few typos to normalise.

**Findings** (`python scripts/audit_csv.py data/gift-shop-catalog.csv`, file sha256 `3e32e993…`):
- 152 rows, 17 columns, CRLF line endings, no BOM.
- Category spellings collapse from 18 to 11 (`Home and Living`, `home & living`,
  ` Home & Living`, `Tech and Gadgets`, …). The ID prefix agrees with the corrected category
  in 152 of 152 rows, which independently confirms the mapping.
- Two products are listed twice under different IDs and categories, identical in every other
  field: HL-021 = KD-024 (Herb Garden Kit), HL-024 = KD-023 (Amber Glass Tumbler Set).
  152 rows, 150 distinct products.
- 11 products out of stock. Gift cards use stock 999 and shipping 0 as "unlimited, digital".
- Missing values: rating and review count (5 products, always together), occasion (3), colour
  and material (2 gift cards).
- Two descriptions carry no information ("Great gift.", "A card."). Several refer to
  neighbouring products the shopper cannot see ("Lighter than the Ember", "the risk above").
- Several descriptions contain honest caveats that are the best material for a recommendation
  ("Subscription required after the first year", "need an amplifier the recipient may not
  own", "Fits the 7in only").

**The finding that shapes the interface.** The brief's "specific user" example, *a chef's
knife under a hundred euros*, has no exact answer: the only chef's knife costs €149. A search
tool that returns an empty list leaves the agent two bad options: say "nothing found", or
improvise. So the tools must report near misses: what matched except for the price, and by
how much. "Nothing suitable" and "out of stock" are not edge cases in this catalogue; they
are built into it.

## Day 1 · Block 4 · Designing the data pipeline (~1 h)

**Starting point.** Two ideas on the table: (a) a programmed cleaning step with human review
for what code cannot decide; (b) an LLM, possibly a local model, writing a richer description
or taxonomy per product, because some descriptions never say what the product is.

**Where we ended up.**
- (b) was rejected. Most of the "missing" information is already in other columns; the
  agent is itself an LLM and does the inference at conversation time; and at 150 products,
  category plus filters already narrows any request. A deterministic concatenation of the
  columns gives the search the same material with zero hallucination risk. Full reasoning and
  the conditions to revisit it: ADR-003.
- (a) was kept, with two refinements that came out of challenging the first version:
  1. **Upsert is not enough.** "Same ID replaces, new ID is added" never removes a product
     the client delisted, so the agent would keep recommending it. An export is a full
     snapshot. The new export replaces the catalogue and the ingest reports what was added,
     changed and removed. If more than a set share of the catalogue disappears, the ingest
     stops, because a truncated export is likelier than a client closing half the shop.
  2. **Rules and decisions are different things.** General rules (trim, case, "and" → "&",
     empty → missing, `|` splitting) live in code with tests. One-off judgements (the
     canonical category list, each duplicate pair, the meaning of stock 999) live in
     `data/decisions.yaml`. A decision can go stale: if a later export makes a declared
     duplicate pair differ, the ingest stops instead of applying it blindly.
- Duplicate IDs: no ID is dropped, because orders in the client's system may reference
  either. Browsing a category shows each under its own ID; a catalogue-wide search shows the
  product once and notes the other listing; details resolve both IDs.
- A read-only `/catalog/report` page (anomalies found, decisions applied, catalogue version)
  is planned as an extension. A data-upload portal in the landing page was rejected: it would
  add a write path, a second auth scheme and persistent storage to a public sandbox for a
  feature nobody asked for. `make ingest` is the update path, and the portal is listed as a
  next step.

**Acceptance for this part.** The client's CSV ingests with zero pending decisions and a
byte-identical result on every run. Each seeded-anomaly fixture (unknown category spelling,
new duplicate, non-numeric price, half the catalogue missing, stale decision) stops the
ingest and reports exactly that anomaly.
