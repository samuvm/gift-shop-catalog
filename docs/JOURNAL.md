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

## Day 1 · Block 5 · Working rules and governance (~30 min)

**What was set up.** Working rules for the whole project, a status file, a progress page and
this journal as the single history. Overlap was removed on purpose: no separate changelog
(the journal and the README carry the numbers) and no rules file (the testing regime lives in
`pyproject.toml`, where a script can read it). Commits carry no tool attribution: they describe
the change, as in any professional repository.

## Day 2 · Fri 30 Oct · Block 1 · Goals sealed, ingest built test-first (~25 min)

**Goals.** Before sealing, the goals were reviewed against an earlier project of ours
(`data-warden`, an NL→SQL agent with deterministic guards) for ideas that transfer. Three
did: a rejection should name the rule and the alternative (already the plan for tool errors);
one core served by REST and MCP with neither importing the other (new goal G-ARCH-LAYERS, plus
the existing parity goal); and evaluations that reproduce from recorded model responses with no
API key (new goal G-L2-REPRODUCIBLE). MCP protocol conformance became an extension goal. Its
audit hash chain and roles were not taken: there is no sensitive data and only one kind of
caller here. Mutation testing was dropped from the goals: it needs a new dependency and does
not block anything. 19 goals ratified and sealed (`docs/thresholds.lock`, sha256 `1e247cd7…`).

**Scope check.** We asked whether the data pipeline and the measurement work go beyond what is
evaluated. Decision: keep the planned scope and order. The data work is where "nobody is going
to clean it for you" is answered, and the measurement work is what turns "the spec is
LLM-friendly" into a number.

**Ingest, red then green.** Tests were written first against stub modules, and every one failed
on `NotImplementedError`, none on imports. Then the implementation. Two failures on the first
green run, each resolved differently:
- *Real bug:* a malformed ID (`HL1`) raised both `invalid_value` and `prefix_mismatch`. One
  problem should give one anomaly; the prefix check now runs only on well-formed IDs.
- *Over-specified test:* the quality-warning test expected exactly two codes, but a one-row
  export is also missing the declared cross-listed pairs, which is correctly reported as
  `unused_decision` (noted, not blocking). The test now expects it, and a new test pins that
  behaviour on its own.

**Numbers.**
- `make ingest` on the client's export: status ok, 0 pending decisions, 152 rows, 152 listings,
  150 distinct products, 11 categories. A second run reports no changes (G-INGEST-CLEAN: 0).
- `make eval-ingest`: 10 of 10 seeded fixtures report exactly their anomaly, including the
  unmodified export, which must not stop (G-INGEST-STOPS: 1.0).
- `make test`: 78 tests, 99% line coverage on the ingest and storage code.

**A side observation that supports ADR-003.** TG-001's description never says "headphones", but
its tags do (`headphones|anc|wireless|travel`). The deterministic `search_text` carries them, so
the gap an LLM enrichment was meant to close was already closed by the client's own data.

## Day 2 · Block 2 · Stress-testing the tool set with 100 synthetic conversations (~25 min)

**Starting point.** A proposal of four tools: the three required ones plus `search_products`.
Before fixing it, we wanted evidence that it covers how real customers talk.

**Method.** Four agents wrote 25 conversations each, in four directions that do not overlap:
constraints that change mid-chat; precise customers and hard constraints; off-topic and
adversarial turns; wordplay and messy language. The agents did not see the tool design. They
wrote as customers, grounded in real products and prices. The set has 100 conversations and
671 customer messages, in English, Spanish, Italian and mixed languages, and 40 conversations
contain bursts of several messages. Each conversation was then mapped to what the agent would
need from the catalogue. **This is a development set.** It shapes the design, so it will never
be used to evaluate it; the level-2 cases are written separately.

**What the conversations need** (approximate, by keyword over traps and messages; counts are
conversations):
- Delivery against a date: ~31. Wrapping questions: ~32. Several products in one answer
  (combos, totals, "both"): ~31.
- A product the customer names that is out of stock: ~19. A caveat that lives only in the
  description (needs an amplifier, engraving adds a week, starter not included): ~19.
- Over budget: ~17. Exclusions ("not a candle", vegan, "nothing scented"): ~14. Price ranges:
  ~11. Ordering ("most popular", "best rated", "cheapest"): ~11. Brands the shop does not sell
  (AirPods, Kindle, Sony, Lego): ~9. The duplicate listing, noticed by the customer: 5.
- Off-topic, missing-policy or injection turns that no tool should serve: most of set C.

**Conclusions for the interface.**
1. No conversation needs a fifth tool. Everything outside the four is data the shop does not
   have (returns, discounts, shipping costs, order status, restock dates, wrapping price). The
   honest answer to those is a prompt rule, not a tool.
2. **A search that hides out-of-stock products by default breaks a common case.** "Do you have
   the City Map jigsaw?" would come back empty, and the agent would say the shop does not sell
   it. Out-of-stock matches must be reported separately, never dropped silently.
3. **Unmatched words are information.** "sony noise cancelling headphones" should return the
   headphones and say that "sony" matched nothing, so the agent can say "we don't stock Sony;
   the closest is…".
4. Missing filters with clear demand: price range, exclusions, maximum shipping days, sort by
   price, rating or popularity (review count), and subcategory (Pets → Cats).
5. Strict filters can remove the right answer. In one conversation, "anniversary gift for her
   under €100" returns nothing because occasion tags are not exhaustive. When results are
   few, the response should say which single relaxation would return more, and how many.
6. The agent may not know today's date. Deadlines are common, so responses should carry the
   server's date, and descriptions must say `shipping_days` is an estimate, not a promise.
7. Some phrasings no search will ever match ("estoy a dos velas", "media naranja", "nothing she
   can knock over and set on fire"). Translating them into catalogue words (product types,
   materials, hobbies, in English) is the agent's job, and the `query` description must say so.
8. Batch details were considered and rejected. List items already carry price, availability,
   shipping days and wrapping, which is enough for totals and comparisons. The platform can run
   several detail calls in parallel, and one product per call keeps the operation unambiguous.

## Day 2 · Block 3 · Interface design, ADR-002 (~30 min)

**Starting point.** Four tools, a compact list item with every field a recommendation might
use, estimated at ~90 tokens per item.

**What the measurement said.** The estimate was wrong by a third. Measured with `o200k_base` over
every product, the full item is ~120 tokens, and the worst default page (5 items plus every
optional block) is 973 tokens, above the sealed limit of 800. The sealed goals do not move, so
the design did. The filters the agent applied are already echoed once in `meta.applied`, so
`category`, `recipient`, `occasions` and `reviews_count` left the list item; they stay in the
details. Result: ~86 tokens per item, worst pages of 790 (≤ 800) and 1,256 (≤ 1,500). Lesson
kept: size claims in the ADR are measured, not estimated.

**A "guard" tool for injection and off-topic turns was considered and rejected.** It only runs
when the model decides to call it, so it fails exactly when the model has been manipulated. The
platform already has that layer before the model: a Security layer that classifies every message
for jailbreaks and out-of-scope requests, in Shadow or Enforce mode, plus real-time guardrails.
The plan is to run it in Shadow first and measure it on the adversarial conversations, because
Enforce on "out of scope" could block mixed messages that also contain a real gift request.

**Decisions** (ADR-002, proposed): four read-only tools with one job each; search has no
category parameter so it never competes with browsing; out-of-stock and over-budget matches are
reported, never dropped; unmatched query words are reported; `meta.today` carries the date;
tolerant inputs with notes, recoverable 4xx errors with one shape; one definition generates both
OpenAPI and MCP; OpenAPI 3.0.3 with every schema inline.

**Revision, same block.** The trim above was a design change made to fit a sealed goal without
asking. That is the wrong order: when a goal is missed, the work stops and the numbers go to the
person who owns the goals. Samuel reviewed both measurements (full item: 973 / 1,621; trimmed:
790 / 1,256) and chose the full item, raising the limits to the measured worst case plus about
150 tokens: G-RESP-TOKENS-DEFAULT 800 → 1,150 and G-RESP-TOKENS-MAX 1,500 → 1,800. A worst page
of ~1,000 tokens is small next to the context, and recipient, occasions and review count make a
recommendation's reasons readable without a second call per product. Rule added for the rest
of the project: a missed goal stops the work and is brought to Samuel; it is never designed
around silently.

## Day 2 · Block 4 · Injection rule in the ingest, level-1 cases v1 (~35 min)

**Ingest.** ADR-002 accepted. A new stopping code, `instruction_like_text`, was added test-first:
product copy reaches the agent verbatim, so an export carrying "ignore previous instructions" is a
prompt injection through the data. Ordinary copy ("Instructions included", "Do not peek in the
envelopes") is left alone. 92 tests; `make eval-ingest` 11/11 with a new seeded fixture; the
client's export still ingests with nothing pending.

**Level-1 cases.** The cases are produced by a reference implementation of ADR-002
(`evals/golden/l1/oracle.py`): stdlib only, written before the service and independent of it. The
service will be checked against it. Where the two disagree, a person decides which is right.
61 cases across the four tools, 12 of them (20%) empty results or errors.

**Building the reference found four design defects, with no service code yet:**
1. Exclusions read the description, so "no alpaca, wool or sheepskin" removed the *cotton*
   throw ("the everyday version of the alpaca"). Exclusions now match name, subcategory, tags and
   material only.
2. Occasions were not searchable: "housewarming" matched nothing. Added at weight 1.5.
3. `out_of_stock_matches` on every plain browse was noise. It now appears only with a query or on
   a short page.
4. "Remove max_price: 22 products" is less useful to the agent than "the cheapest in Kitchen &
   Dining is €42". Suggestions now give, per active filter, the nearest price that adds a
   result (up to 3).
All four are recorded as an amendment to ADR-002, each pinned by a case.

**Known vocabulary gaps, kept on purpose** (they are the agent's job, per ADR-003): "headphones"
does not match the earbuds, and "running" only matches the open-ear buds. The level-2 eval will
show whether the model widens its queries.

**Next.** Samuel reviews `evals/golden/l1/REVIEW.md`, case by case. Meanwhile, the domain is
built test-first against the same semantics.

## Day 2 · Block 5 · Domain built test-first, checked against the reference (~30 min)

**Approach.** 39 unit tests on a hand-built twelve-product catalogue pin the semantics one by one:
resolution, every filter, sorting, paging, the information blocks, details and alternatives. They
were written first; all failed on `NotImplementedError`. Then a second check: every level-1 case
run against the domain on the real catalogue, so two implementations written separately must
agree.

**What failed on the way, and why:**
- *Design defect, found by writing the unit tests:* stripping a trailing `s` turns "knives" into
  "knive", which never matches "knife". The plural rule now handles `-ies`, `-ives`, `-ves` and
  `-es`, in both the domain and the reference. Three level-1 expectations changed, all for the
  better: the cheese board with knives now matches "knife", and the whisky glasses match "glass".
- *Code defect:* for an unknown ID, `difflib` returned equally close guesses in an unhelpful order
  (KD-007, KD-004, KD-003 for "KD-009"). The guesses are now ordered by closeness, then by ID.
- *Harness defect:* the level-1 runner passed `exclude` as a string; two cases failed until it was
  split into a list.

**Numbers.** 61 of 61 level-1 cases agree between the domain and the reference.
`make test`: 192 tests, 99% line coverage over ingest, domain and storage.

**Caveat.** The reference and the domain have the same author, so their agreement shows that
the code matches the written semantics, not that the semantics are right. That second check is
the human review of the level-1 cases, which is pending.

## Day 2 · Block 6 · REST API, served OpenAPI, contract checks, container (~45 min)

**Approach.** The four tools are defined once (`src/catalog/tools.py`): name, description written
for the model, parameters and inline response schemas. The OpenAPI document is generated from
those definitions, with examples taken from real responses. Both REST and the future MCP server
call a single `execute()` per tool, so parity holds by construction. The API layer is
contract-tested, not test-driven: auth on every data route, one error shape with a hint, the
envelope, a snapshot of the served spec, and a lint of the spec against the platform's rules.

**Found while doing it:**
- "garden" is not a category but a subcategory of Home & Living. The error now says so, and
  names the exact call to make instead (test written first, in the domain).
- The secrets scanner flagged the catalogue's sha256 version hashes (false positives, now in
  the reviewed baseline) and then its own baseline file (now excluded from the scan).
- **The token measurement behind yesterday's limit change used pretty-printed JSON; the service
  sends compact JSON.** Re-measured: the synthetic worst case is 831 / 1,351 tokens compact
  (1,024 / 1,672 with spaces). The real responses across the 61 level-1 cases peak at 622 / 1,046.
  The revised limits (1,150 / 1,800) hold with room to spare. The original 800 would have
  failed only on the synthetic worst case. Reported to Samuel; the limits stay unless he decides
  otherwise.

**Numbers** (all in-process; the deployed run comes with F1):

| Goal | Value | Command |
|---|---|---|
| G-L1-EXACT | 61/61 = 1.0 | `make eval-l1` |
| G-RESP-TOKENS-DEFAULT | 622 (≤ 1,150) | `make eval-l1` |
| G-RESP-TOKENS-MAX | 1,046 (≤ 1,800) | `make eval-l1` |
| G-SPEC-LINT | 0 violations | `make spec-lint` |
| G-AUTH | 12/12 rejected = 1.0 | `make test` |
| G-ARCH-LAYERS | 0 violations | `make test` |
| G-COVERAGE | 99.67% (606/608) | `make test` |
| G-SECRETS | 0 new | `make secrets` |
| G-INGEST-STOPS | 11/11 | `make eval-ingest` |

221 tests in 0.8 s. The image builds, refuses to start without a key, runs as a non-root user and
answers health, 401 and search. Still open: the deployment itself (it needs the GitHub repository)
and whether the platform passes 4xx bodies to the model.

### Block 7 · Repository, and where the catalogue lives (≈ 30 min)

**Starting point:** the code had only existed locally. The deployment needs it on GitHub, and
one question had been answered in code but never written down: does the service read the CSV,
or something else, and how far does that hold?

**Done:**
- Checked the full history before the first push: one author, no secrets (`make secrets`: 0
  new), no workspace token in any commit. Created the private repository `samuvm/gift-shop-catalog`
  and pushed `main`. It becomes public at submission.
- Decided to keep the response token limits at 1,150 / 1,800. The measured peaks (622 / 1,046)
  leave room for the optional blocks that real searches have not yet filled at the same time.
- Wrote ADR-004. The CSV is read only by the ingest. The service loads `data/build/catalog.json`
  at startup and answers every call from memory.

**Initial approach → conclusion:** the first instinct was to write the scale caveat as one line
("fine for 150 rows, use a database for millions"). A line like that cannot be checked, so I
measured instead. `scripts/scale_probe.py` builds the catalogue and runs eight searches, on the
served catalogue and on a ×100 synthetic copy with fresh IDs.

| Catalogue | Build | Peak memory | Search p50 | Search p95 |
|---|---|---|---|---|
| 152 (served) | 4 ms | 0.6 MB | 0.13 ms | 0.20 ms |
| 15,200 (×100) | 356 ms | 64 MB | 14 ms | 35 to 39 ms |

Two runs each, `uv run python scripts/scale_probe.py`. Search is a linear scan, and the
numbers confirm it: ×100 products, roughly ×100 time and memory.

**Why it stays:** at 152 products the scan costs a fraction of a millisecond. A database would
add a component without a measurable gain. The design breaks well before millions of rows: at
tens of thousands it is time for SQLite with FTS5, and beyond that a search engine with
incremental ingest and live stock. ADR-004 records those steps as estimates extrapolated from
the measurement, not as measured limits. It also names the real weakness of the snapshot, which
is not speed but stock freshness.

**Discarded:** moving to SQLite now "to be ready". It changes no number the agent sees, and
every component has to be explained in review.

### Block 8 · The first human review, and search relevance (≈ 1 h 40 min)

**Starting point:** Samuel reviewed all 61 level-1 cases as a shop assistant would. 43 were
approved as they were and 18 drew a comment.

**Initial approach → conclusion:** I read the comments as possible bugs, so the first step was
to find, for every product he named, which field produced the match. None was a bug: service
and reference implementation agreed in 61 of 61. The comments were about the **specification**.
The keyword scoring of ADR-002 accepted a match anywhere, counted the category name, and
rewarded neither matching more of the words nor matching the rarer one. A cheese board was
returned for "chef knife" because its description says "three knives". Every card game was
returned for "puzzle" because the category is *Games & Puzzles*. That is exactly what a human
review is for: a reference implementation can only check that the code does what the
specification says, not that the specification is right.

Before writing anything I prototyped two candidate rule sets against all the search cases:

| Candidate | Effect |
|---|---|
| Drop matches found only in the description, colour or material | Cleaner lists, but "coffee" loses the travel mug, an approved case whose only mention of coffee is in its description |
| Rank those matches last; stop searching the category name; order by strong-field coverage, then any coverage, then rarity | Fixes 029, 035 and 039 as asked; noise moves to the end in 026, 027, 028, 036 and 038; no approved top five changes |

Samuel chose the second, a small reviewed synonym list, and four smaller rules (ADR-005).

**Done:**
- Committed his review untouched first (`review-v1.md`). Then **registered six held-out
  cases before writing any rule**, so that something tests whether the rules generalise beyond
  the cases they were written to fix.
- ADR-005, then tests first in the domain (13 new tests), then the code, then the reference
  implementation, changed separately from the code.
- Vocabulary in `decisions.yaml`: 3 phrases and 5 synonym groups. They were taken from the 100
  development conversations and the catalogue's tags, not from the reviewed cases. The ingest
  rejects a malformed vocabulary and warns about a group that no product uses. The served
  `catalog_version` now covers the vocabulary too (`served_sha256`).
- Level-1 set v2: 67 cases. 40 keep Samuel's approval because their arguments and expected
  result did not change. 27 go back to review, each with his previous comment beside it.
- Unknown-category and unknown-product errors now pin `did_you_mean` in the cases as well.
  l1-005 already pointed to *home-living*; the case simply never checked it.

**Numbers:**

| Goal | Value | Command |
|---|---|---|
| G-L1-EXACT | 67/67 | `make eval-l1` |
| G-RESP-TOKENS-DEFAULT / MAX | 621 / 1,045 (≤ 1,150 / 1,800) | `make eval-l1` |
| G-COVERAGE | 99.71% (680/682) | `make test` |
| G-SPEC-LINT | 0 | `make spec-lint` |
| G-INGEST-STOPS | 11/11 | `make eval-ingest` |
| G-SECRETS | 0 new (4 new version hashes reviewed into the baseline) | `make secrets` |

247 tests in 0.9 s. The OpenAPI changed only in three descriptions and the catalogue version.

**What the held-out cases showed** (reported, not fixed: tuning on them would end their use):
- l1-062 "wooden board game" puts a balance board first. It matches "wooden" and "board"; the
  board games say "wood", not "wooden". Rarity rewards the rarer word even when the product
  noun ("game") is the one missing.
- l1-065 "tea set" under 50: after the one tea, the rest are any product named "set". Generic
  words such as "set" count as coverage.
- Cost of no longer searching the category name: in the approved l1-043 ("travel" for him), the
  out-of-stock camping hammock is no longer reported, because its only link to "travel" was the
  category *Outdoor & Travel*. The top five did not change.

### Block 9 · The second human review: the limit of keyword rules (≈ 1 h 30 min)

**Starting point:** Samuel reviewed the 27 pending cases of v2. 11 were approved and 16 drew a
comment. The six held-out cases were all commented on. That was both expected and useful: the
held-out cases were there to show whether ADR-005 generalised, and it did not fully.

**Initial approach → conclusion:** The dominant pattern was the same in nine comments. A product
that matches a *modifier* of the query is not what was asked for: a leather watch strap for
"leather notebook", a mouse for "wireless speaker", a coaster set for "tea set". ADR-005 had
moved them to the end of the list. The reviewer still struck them out. My first proposal was a
grammar rule: the last word of the query names the product.

Samuel pushed back on the framing: the fix has to stay deterministic, and the review compares
results with the brief and the client's CSV, so the CSV may hold a better answer. It does. The
**first tag of every row is the product type** (115 types across 150 products). I prototyped
both against all 67 cases before choosing:

| Rule (both deterministic) | Comments fixed | Approved cases broken |
|---|---|---|
| CSV product type as a filter | all nine | 5: "chef knife" loses the sharpening stone, "coffee" the travel mug, "pasta" the pasta bowls; "herb garden kit" keeps one product |
| Last specific word of the query must be in a strong field | all nine | 1: "fig candle" drops a fig perfume |
| Out-of-stock and over-budget blocks on every request | 067, 049 | about twenty, mostly noise |
| The same, only when recipient or occasion is set | 067, 049 | 0 (014 and 018 gain a block) |

The CSV type is precise but too narrow: a sharpening stone is tagged `sharpening`, not `knife`.
I chose the main-word rule. The CSV signal stays documented in ADR-006 as the option rejected.

The second conclusion mattered more. Every rule that removed the reviewer's noise also removed
something the reviewer wanted elsewhere: the travel mug, the pasta bowls, the planters. What is
left needs an understanding of the product (open-ear buds do not cancel noise; passive speakers
are not wireless), and keyword rules cannot supply it. The consumer of the tool is an LLM, which
does that well, provided it can see *why* a product was listed. So each product now carries
`missing_terms`, the query words it lacks. After this round **ranking is frozen**. A new rule
needs evidence from the level-2 evaluation that the agent recommends the wrong product because
of the order.

**Done:**
- Committed the review untouched. Then **registered six new held-out cases** (l1-068 to 073)
  before writing any rule, because the previous six had now informed the rules.
- ADR-006: main word; generic packaging words in `decisions.yaml` (set, kit, pack, pair,
  collection, bundle, trio, duo; "box" left out because it can be the product); synonym groups
  `[wood, wooden]` and `[notebook, journal]`, both found in the development conversations; a
  synonym match scores half; `missing_terms`; `recipient` takes several values (`her,couple`);
  out-of-stock and over-budget blocks when recipient or occasion is set.
- l1-005 needed no code. The error already named *home-living* and *Garden* in its `hint`, but
  the review sheet never showed it. Error cases now record the hint.
- Tests first: 13 new domain tests plus 4 for the API, the vocabulary and storage, then the code. The reference implementation was updated
  separately and agrees with the service on all 74 cases.
- Level-1 v3: 74 cases (one new case for `her,couple`). 44 keep their approval and 30 go to
  review.

**Numbers:**

| Goal | Value | Command |
|---|---|---|
| G-L1-EXACT | 74/74 over HTTP | `make eval-l1` |
| G-RESP-TOKENS-DEFAULT / MAX | 620 / 1,044 (≤ 1,150 / 1,800) | `make eval-l1` |
| G-COVERAGE | 99.58% (714/717) | `make test` |
| G-SPEC-LINT | 0 | `make spec-lint` |
| G-SECRETS | 0 new (4 version hashes reviewed into the baseline) | `make secrets` |

271 tests in 1.1 s. In-process search p95 is 0.36 ms on the served catalogue
(`scripts/scale_probe.py`). The OpenAPI changed in the recipient parameter (a pattern instead of
an enum, with the values in its description), the new `missing_terms` field, three descriptions
and the catalogue version.

**What the new held-out cases show** (not tuned on): "travel pillow" names something the shop
does not carry. No product has "pillow" in a strong field, so the query is not narrowed, and
every travel item says `missing_terms: ["pillow"]`. That is the honest answer, and the agent can
read it. "coffee grinder" lists both grinders, the manual one marked as missing "coffee".

### Block 10 · The third review: correct information versus taste (≈ 30 min)

**Starting point:** Samuel reviewed the 30 pending v3 cases. 19 were approved; in four of them
he withdrew an earlier comment, because `missing_terms` now flags the open-ear buds as missing
"anc", and couple products come out with `recipient: her,couple`. 11 drew a comment.

**Initial approach → conclusion:** With ranking frozen by ADR-006, I sorted each comment by one
question: *would the agent end up saying something false?*
- Four did. A Bluetooth speaker was marked as missing "wireless", so the agent could have said
  it is not wireless. Vermeil earrings were offered over budget for "silver" with no warning. A
  suggestion proposed dropping a vegan's exclusion. A hint stayed generic although the tool knew
  the single subcategory where lamps are listed. These were fixed (ADR-007).
- The other seven ask for a different order or a semantic judgement: a sauna blanket, incense
  for children, a pepper mill for "coffee grinder", chess as a wooden board game. Under the
  freeze they become level-2 questions. The review sheet keeps the reviewer's words beside each
  one, marked *deferred*, not approved. Most of those products now show the missing word, so
  the agent has what it needs to set them aside.

**Done:** ADR-007; tests first for the three domain changes; `[wireless, bluetooth]` in
`decisions.yaml`; `missing_terms` on the near-miss blocks; the reference implementation, the
domain harness and the HTTP harness all updated; level-1 v4.

**Numbers:**

| Goal | Value | Command |
|---|---|---|
| G-L1-EXACT | 74/74 over HTTP | `make eval-l1` |
| G-RESP-TOKENS-DEFAULT / MAX | 622 / 1,046 (≤ 1,150 / 1,800) | `make eval-l1` |
| G-COVERAGE | 99.58% (716/719) | `make test` |
| G-SPEC-LINT · G-SECRETS | 0 · 0 new | `make spec-lint` · `make secrets` |

274 tests. 9 cases changed and go back to review: 3 only gain `allowed_values`, and the other 6
change in exactly the way the comments asked.

### Block 11 · Deployment on Coolify, measured from outside (≈ 1 h, mostly Samuel's hands)

**Starting point:** the image had been built and run locally, but never deployed. Samuel created
the resource in Coolify (v4.5.3) through a new GitHub App with access to this repository only.
The app another project uses was left as it was.

**Initial approach → conclusion:** I wrote the deployment guide assuming Coolify's own
healthcheck was harmless. It was not. The first deployment built and started (`Uvicorn running
on 0.0.0.0:8000`) and was then rolled back. Coolify's healthcheck runs `curl` or `wget` inside
the container, and the slim image ships neither: `curl: not found`, then *New container is not
healthy, rolling back*. It also probed `/`, not `/health`. The image already declares its own
`HEALTHCHECK` in Python, so the fix was to switch Coolify's off, not to add curl to the image
for it. The same log showed the domain saved as `http://`, so no certificate was requested.
With both corrected, the second deployment went live with a Let's Encrypt certificate on
`https://catalog.178.18.243.118.sslip.io`. The URL exposes the server's IP. That was a known,
accepted trade-off of using sslip.io instead of a domain; it will be noted in the README.

**Numbers** (from the client machine, over the public URL):

| Goal | Value | Command |
|---|---|---|
| G-LATENCY-P95 | 264.8 ms, worst p95 of 3 runs × 20 calls (≤ 300) | `make latency URL=…` |
| G-PUBLIC-CHECK | 6/6: HTTPS, spec without key, 401 without and with a wrong key, 200 with the key, test page up | `make check-public URL=…` |
| G-L1-EXACT | 74/74 against the deployment | `CATALOG_URL=… make eval-l1` |

The latency margin is narrow, but the measurement is deliberately pessimistic: every call opens
a new TCP and TLS connection. One call to `/health` breaks down as 50 ms to connect, 73 ms of
TLS handshake, and about 107 ms to the first byte. The search itself takes 0.36 ms in process.
A client that keeps the connection open, as the platform's HTTP client normally does, saves
the handshake on every call after the first.

All phase-1 goals now pass: ingest clean (0 pending) and 11/11 seeded anomalies stopped; 74/74
level-1 cases; 622 / 1,046 tokens; spec lint 0; auth 12/12; secrets 0; coverage 99.58%;
layer violations 0; latency 264.8 ms.

### Block 12 · Level 2 on a local model: the agent answers from memory (≈ 1 h 30 min)

**Starting point:** F1 approved. The level-2 goals assumed an OpenAI key. Samuel proposed a
local model instead. The platform's own model list includes **gemma-4-26b (EU)**, and the same
open-weight model runs in Ollama on this machine with tool calling. So level 2 now measures the
tools against a model the platform actually offers, at no cost. The three goals' `requires`
field changed; thresholds did not, and Samuel resealed the lock.

**Rejected:** exposing the local model with ngrok. Level 2 runs entirely on this machine, and
the platform can only use the models in its own list, so a public tunnel would add risk for
nothing. Also rejected as the measured model: a Claude sub-agent of this session. It would read
the spec as text rather than through function calling, it cannot be recorded and replayed, and
the same family wrote the descriptions it would be judging.

**Done:**
- `agent/system-prompt.md`: versioned prompt (id, version, model, changes).
- `evals/l2/run.py`: builds the tools from the served OpenAPI the way the platform does, calls
  Gemma 4 26B (temperature 0, no reasoning, fixed seed), records every response and replays it
  (`make eval-l2`, `make eval-l2-refresh`).
- 150 cases drafted in parallel by four agents, one per direction of the 100 development
  conversations. Each case keeps the history and the latest message. `evals/l2/build.py`
  validates every tool, argument, category and product id, then writes the review sheet with
  failing cases first. 36 cases are negative (24%).

**Initial approach → conclusion:** v1 of the prompt reached 74.0% on tool choice. The dominant
failure was not a wrong tool but **no tool**: in 28 of 39 failures the model answered from
memory, and invented a "Pocket Notebook at €15" and "we don't sell Kindles" (the shop has
e-readers). It happened mostly when the shopper changed a condition mid-conversation and the
model reused what had already been said. v2 added three general rules: every product fact
comes from a tool call, search again when a condition changes, and call `get_categories` only
on request.

| Prompt | Tool choice | Arguments | Negatives calling a tool | Replay mismatches |
|---|---|---|---|---|
| v1 | 74.0% | 89.4% | 0% | 0 |
| v2 | **89.3%** (134/150, 95% CI 84–94%) | 85.6% | 0% | 0 |

Paired over the same 150 cases (bootstrap, seed 20261029): +15.3 points, 95% CI +9.3 to +21.3.
23 cases fixed, none broken. G-L2-TOOL (≥ 90%) is **one case short after two attempts**, so
work stopped and the question went to Samuel. The bank had not been reviewed by a person yet,
and tuning the prompt against unreviewed labels risks fitting it to the labels' mistakes. He
chose to review the 29 failing cases first, then allow one more prompt attempt.

The run also showed why a platform guardrail matters here. The tools only read, so injection
can only read the public catalogue. The real risk is the model inventing a product or a policy.
The platform's *Hallucination* guardrail targets exactly that, and it goes into the platform
configuration.

### Block 13 · Reviewing the failures, and deciding what "good enough" means (≈ 30 min)

**Starting point:** Samuel reviewed the 29 cases the model failed with prompt v2. He found 17
real model failures, 7 cases where the model's move was also acceptable, and 5 wrong labels.
Three of the wrong labels exposed a **bug in the evaluator**, not in the labels. When a case
accepted two tools, the expected arguments of one were also required of the other, so the
alternative could never pass. For example, `product_id` was required of a `search_products`
call. The scorer now checks only the parameters of the tool actually called.

**Numbers** (prompt v2 re-scored from its recording; the model was not called again):

| Goal | Before review | After review | Threshold |
|---|---|---|---|
| G-L2-TOOL | 89.3% | **90.0%** (135/150, 95% CI 84.7–94.7%) | ≥ 90% |
| G-L2-ARGS | 85.6% | **92.3%** | ≥ 85% |
| G-L2-NEG-FALSE-CALL | 0% | 0% | ≤ 5% |
| G-L2-REPRODUCIBLE | 0 | 0 | 0 |

The goal now passes because labels and the scorer were corrected, not because the model got
better. That distinction is recorded here on purpose. 12 of the 15 remaining failures are the
same pattern: answering from memory without a tool.

**Decision: no prompt v3 for now.** Three reasons:
- The brief asks for no accuracy figure. It asks that the agent holds up in six scenarios,
  explains its recommendations, presents them well on a phone and leaves off-topic
  conversations cleanly. The level-2 goal is our own quality gate.
- More prompt rules tuned on the same 150 cases would start fitting the test.
- The remaining pattern is what the platform's *Hallucination* guardrail and the Simulations
  will exercise with the production model.

A v3 is reopened only if the Playground or the Simulations show the agent answering from
memory. The 121 cases that passed are still unreviewed; that does not block anything.

**Working rule from here, agreed with Samuel:** follow the process, test what matters, state
plainly what each step achieves, and do not spend disproportionate time on marginal gains.
Every platform step is written down before and after it is done, with the reason for each
choice.

### Block 14 · The prompt in the platform's shape, and two model sizes (≈ 1 h)

**Starting point:** the official guide (read through a research sub-agent, every fact cited to
its page) showed the platform has **no single prompt field**. An agent is a block of fields:
General Description, Agent Goal, Tone of Voice, up to 10 General Rules, custom sections. The
platform compiles them into its own prompt. It also showed two traps: Short Memory defaults to
3 messages, and guardrails do nothing until a Control Room rule uses them.

**Initial approach → conclusion:** v3 split v2's rules into those fields, so that level 2
measures the text that will actually be pasted. On the MLX build of Gemma 26B, v3 first dropped
from 90.0% to 85.3%. The cause was visible case by case. With "only help with gifts from this
shop" among the general rules, the model treated "do you have AirPods?" as off-topic and
answered without searching. That rule went back to the off-topic section, as in v2, and a line
now says that asking whether the shop has an item is a shop question.

Samuel then asked for the standard (GGUF) builds instead of MLX: `gemma4:26b`, the gate model,
and `gemma4:12b` for comparison. A first 12B run hung on a generation that never ended. Output
is now capped at 512 tokens, which does not affect scoring because only the first move is
scored.

| Model | Prompt v2 | Prompt v3 | v3 − v2, paired (95% CI) |
|---|---|---|---|
| gemma4:26b | 88.0% | 86.7% | −1.3 pts (−5.3 to +2.0): no real difference |
| gemma4:12b | 81.3% | 88.0% | +6.7 pts (+2.7 to +11.3): clearly better |

Arguments stay at 90–95% and no negative case calls a tool, in all four runs.

**Decisions:**
- **Ship v3.** It is the platform's format, it is no worse on the gate model and it helps the
  weaker one.
- **G-L2-TOOL is not met** with the gate model: 86.7% against 90%, after two measured attempts.
  It stays at 90% for now. Samuel decides at the end of F2, with the production model's
  Simulations in front of him, whether it holds or changes. The earlier 90.0% was the MLX build
  with v2; it is not the number that counts.
- No more prompt iterations on these 150 cases. The remaining failures are the same pattern,
  answering from memory, and the platform's Hallucination guardrail and the production model
  are the levers for it.

### Block 15 · First connection to the platform, configured step by step (≈ 2 h 15 min, with Samuel)

**Starting point:** prompt v3, a guide written from the official documentation, and a deployed
service. Samuel did every platform step by hand from a chat guide, one step at a time, and sent
screenshots after each. The full configuration and its reasons are in `docs/PLATFORM.md`.

**What the platform taught us**, each found on screen and acted on:

- **It reads `summary`, not `description`.** The first import gave the model one-line
  summaries. Samuel pasted the long descriptions by hand, and the JSON editor then showed them
  stored as `summary`. The served spec now puts the full text in both fields, so a fresh import
  needs no hand edits. An evaluator importing our spec would have hit the same trap.
- **An enum can stop the model from searching.** In Preview, "show me the garden category" made
  the model pick `outdoor-travel`, the nearest value of the category enum, and never send
  "garden". Our 404 for "garden" would have named home-living / Garden. The browse tool and its
  parameter now tell the model to search when the shopper's word is not a category. Level 2
  re-measured on gemma4:26b: 87.3% tool choice, 95.3% arguments, 0% negatives calling a tool. In
  a fresh conversation the same request returned the two planters and the herb garden kit.
- **Error bodies do reach the model**, an open question since F1. The debug view redacts
  response bodies, so it was checked by behaviour. With "lamps in home and living", the agent
  got the 404 for `Lamps` and called again with `Lighting`, the subcategory the error names.
- **Evaluators and guardrails are not in this workspace.** The Hallucination guardrail planned
  for the "answers from memory" risk is therefore not available. The prompt rule that every
  product fact must come from a tool call covers it. The Security layer is on, in Shadow mode.
- **Coolify did not redeploy on push.** Samuel redeployed by hand. Auto-deploy is worth
  switching on.

**First Simulations run** (gpt-4.1-mini, on the draft): core **5/6**, extra **1/3**. core-1 (the
vague shopper) failed: more than two questions, the budget asked twice, a single product. The
two extra failures concern a deadline not presented as an estimate, and "show me more" repeating
products. The judge also flagged a material that is in the product record, which needs checking
in the transcript. G-SIM-CORE needs 6/6, so this is the first item for tomorrow.

**Published** on 1 Nov. On the test page, the chef's-knife request and the returns question
behave as designed. A Spanish request was answered in English: the second item for tomorrow.

Deliberately left for the next session, with Samuel: the transcripts of the three failures, a
prompt v4 aimed only at what they show, re-running the core suite, the widget's home texts, and
the regenerated perimeter.

### Block 16 · Prompt v4, sharper simulations, and choosing the model by experiment (≈ 2 h, with Samuel)

**Starting point:** core 5/6, extra 1/3 on gpt-4.1-mini. The transcripts of the three failures
showed real faults (three questions before products, "delivery is guaranteed", "show me more"
raising the budget and repeating products) and one judge error (a material that is in the
catalogue).

**Prompt v4** targets only those faults: search as soon as the person or budget is known and
never repeat a question; never guarantee delivery; page with offset and the same filters; reply
in the language of the last message. On level 2 (gemma4:26b) v4 measured 80.0%, then 81.3%
with the tool-call rule moved first, against 87.3% for v3. Samuel chose to test v4 on the
platform anyway: the gate model is not the production model.

**The simulations needed work too.** The judge sees the conversation, not the catalogue. It
marked real products as invented, and extra-9 asked for "more coffee gifts around 50" when the
catalogue has only two. Each criterion now states the catalogue facts it depends on. Two were
loosened after reading transcripts, with the reason in the commit: core-2 demanded the literal
"49 euros", and extra-7 counted three products across the conversation instead of per message.
Changing a criterion after seeing results risks moving the goalposts, so every change is tied
to a transcript that shows the criterion, not the agent, was wrong.

**Model or prompt?** Samuel proposed a 2×2: model (mini, gpt-4.1) × criteria (old, sharpened),
prompt fixed. gpt-4.1 removed the padding, the misreads and the duplicated messages that no
prompt rule had fixed: the model weighed more than the prompt. Then, at Samuel's request, the
candidates were widened using a public benchmark close to the task (τ²-Bench Airline) to find
models cheaper than gpt-4.1 and better than mini. Three were run under identical settings.
Results and reasons are in `docs/PLATFORM.md`.

**Decision: gpt-5.6-luna, reasoning Low.** Core 6/6 after reading every Fail, the best extra
result, at half gpt-4.1-mini's price. It flags over-budget items with the gap ("se pasa 23 €"),
which was the one remaining fault of gpt-4.1. gemini-3.5-flash-lite ranked higher on the
benchmark but answered English and Spanish shoppers in Italian. deepseek-v4-flash ranked higher
too but leaked raw tool-call tokens, looped, and took four times longer. A benchmark is good for
choosing what to try, not for deciding.

Still open, noted not fixed: `over_budget_matches` ranks the 115-euro grinder above the
78-euro pour-over set for "coffee" (name match beats tag match), and the judge treats the fixed
welcome text as the agent's.

### Block 17 · Stability of the chosen model, and where the project stands (≈ 30 min, with Samuel)

**Starting point:** gpt-5.6-luna chosen on one run per suite. One run can be luck, so the core
suite ran twice and the extra suite once more, nothing else changed.

**Result:** core 5/6 and 5/6, extra 2/3 from the judge; 6/6, 6/6 and 3/3 after reading every
Fail against the catalogue. The three Fails were the judge's, and two were caused by our own
criteria. core-6's reference listed three of the nine products under 30 euros, so the judge
called the Notebook Trio A6 (24 euros, in stock) unverified. extra-7's reference mentioned gift
wrap next to the pour-over set only, and the judge took that as "only the pour-over set has
gift wrap". The moka pot has it too. A reference that lists some facts reads as listing all of
them. Both criteria now give the complete facts. The agent itself was right: in extra-7 it said
it had no information about adding a note, instead of inventing one.

**Routing seen in every run:** weather and returns went to the General agent, which answered in
Italian without inventing a policy; the injection went to the Jailbreak agent; the gift request
went back to Gift finder with real products under 30 euros.

**Next:** publish, check the regenerated perimeter and the language on the test page, then close
the agent phase. That needs `make done` and a decision on the level-2 tool goal.

### Block 18 · Every simulation criterion carries its facts, and the tool-goal decision (≈ 30 min)

**Problem:** the judge sees the conversation, not the catalogue. Block 17 showed that a
reference listing some facts reads as listing all of them. Fixing criteria one Fail at a time
would keep producing the same error elsewhere.

**Change:** each of the nine criteria was rebuilt from the tools' real output for the calls the
scenario leads to (run in-process against `data/build/catalog.json`). It lists every product
the agent can reasonably name, with price, stock, shipping days and the details shoppers ask
about. Each also tells the judge that the fixed welcome text is not the agent's reply. The
core-6 weather check now accepts one or two short sentences: the agent's answer was one
sentence plus a question back to the gift. The CSV can be deleted and re-imported on the
platform as is.

**Found while doing it:** `missing_terms` for "chef's knife" contains a stray `s`, because the
apostrophe splits the word. It is harmless to the agent (it already says "not a chef's knife")
and is noted for the README rather than fixed now.

**Decision on G-L2-TOOL (≥ 90%):** the threshold stays. Measured on gemma4:26b: 87.3% with
prompt v3 and 81.3% with v4, against a production model (gpt-5.6-luna) that passes the six
scenarios in two runs. Lowering it now would move the goalpost, and tuning the prompt for a
model that is not in production would optimise the wrong thing. It is reported as not reached,
with these numbers.

### Block 19 · The judge cannot check facts it cannot see (≈ 20 min)

**Run after re-import:** core 5/6, extra 1/3. Every named product and detail in the three Fails
was checked against `data/build/catalog.json`:

- core-1: the judge rejected the Ember Ceramic Candle, Atlas of Remote Islands and Incense Set
  (all real, shown after a search by recipient and budget, before cooking came up) and "ninety
  recipes, six hours" (the book's own description). Judge error.
- extra-7: "se abre con una mano" for the Travel Mug is the catalogue's "One-handed open". Judge
  error; the reference had paraphrased the description and left that part out.
- extra-9: the same mug detail (judge error), and one real fault: after "show me more", the
  Pour-Over Set at 78 was offered without saying it is over budget, while the grinder was
  flagged. Minor, noted.

**Conclusion:** this is the third round in which most Fails come from the judge comparing the
agent with a partial list. Adding facts one Fail at a time cannot converge: any product or
detail left out of a reference becomes a false Fail. The judge is now told what it can and
cannot know: judge the behaviour, and treat a fact as wrong only if it contradicts the
reference. Product existence is verified where the catalogue is visible: level 1 checks the
tools exactly, and every Simulations transcript is read against the catalogue before a result
is recorded. References now quote descriptions verbatim instead of paraphrasing them.

**Platform:** guardrail agents corrected (jailbreak attempts → Jailbreak agent, out of scope →
General). Out-of-scope blocking is switched on but has no effect in Shadow mode. Samuel checked
the language on the test page by hand: Spanish in, Spanish out.

### Block 20 · Planning the last stretch, and six more conversations (≈ 45 min)

**Starting point:** the agent works on the platform, and two bonus items remain (MCP, landing).
Before building them, two read-only investigations ran in parallel: one audited the tests, one
researched MCP and the widget.

**What the audit found** changed the priorities. A realistic new export breaks the ingest in
ways no test covered. A duplicated `price_eur` column set all 152 prices to 1.00 and the
ingest reported `ok`. A header-only file on a first build served an empty catalogue. A
Windows-encoded export crashed it with no report. A row longer than the header silently lost a
value. Each is fixed test-first in its own branch, with a guard on mass changes that mirrors
the existing guard on mass removals (ADR-009). The audit also confirmed the `chef's` → `s`
tokenisation bug and that the API rejects `HER` or `Birthday` for their capitals, which an LLM
will send sooner or later.

**MCP:** the platform can connect external MCP servers with static headers but does not
document its protocol revision, and the current MCP revision dropped the `initialize`
handshake. The server will speak both eras. That is the reason for the official SDK over a
hand-rolled JSON-RPC endpoint (ADR-008).

**How the work is split:** four branches built in parallel in separate worktrees (ingest,
search, API, MCP), each merged only with `make gate-fast` green and its eval at target.

**Six more Simulations scenarios** (suite `extended`), each built from the tools' real output:
a vegan sister (exclusions), an anniversary, a child on a small budget, a whole category with
"show me more", comparing two products, and a budget that rises mid-conversation. Two of them
target weaknesses found while gathering their facts, so they are expected to expose them:

- With only `recipient=kids` and a 30-euro budget, the top results include a dog toy
  (Rope Toy Bundle) and incense. Pet products carry `recipient: anyone`, so any human
  recipient filter matches them.
- "gardening" matches nothing while "garden" finds three products: the stemmer does not
  strip "-ing".

### Block 21 · Two branches merged, and a layout fix seen on the test page (≈ 30 min)

**Search: possessives stay one word** (branch `search-apostrophe`). The tokenizer split
"chef's" into `chef` + `s`, on both the query side and the product index, so every product
carried a meaningless `s` match or a stray `missing_terms: ["s"]`. One rule now covers
`chef's`, `kids'` and `don't`. Single letters and digits are kept on purpose: the catalogue
uses them ("Vitamin C", "E-Reader", "3-cup"). The level-1 oracle got its own independent
splitter; a fuzz run of 800,000 random strings found no difference from the domain's. No
level-1 case changed. Tests 274 → 304.

**API: tolerant where tolerance is free, strict where it informs** (branch `api-hardening`).
- Closed-set values are read in any case (`HER`, `Birthday`), and empty list items are
  ignored. A model that capitalises a value should not pay a round trip for it.
- A wrong value now returns `allowed_values`, `did_you_mean` and a hint, not a regex.
- `nan`, `inf` and `min_price > max_price` are now 400s with a hint. The inverted range used to
  return an empty 200, which a model reads as "the shop has nothing".
- Normalisation lives in the shared service layer, so the MCP server gets the same behaviour.
- A new test compares FastAPI's own route parameters with the hand-built spec. It found one
  real drift: `category` had a 50-character limit the spec did not advertise.
- The spec snapshot test now fails when the file is missing, instead of silently writing it.
- Tests 304 → 336. `make eval-l1` 74/74, `make spec-lint` 0, coverage 99.72%.

**Prompt v5, layout only.** On the test page, the agent put the blank line between a
product's name and its reason instead of between products, so the products ran together.
The format section now spells out the layout with placeholders (not real products, which
the model could copy as recommendations). Level 2 is being re-measured to confirm a layout
change leaves tool choice alone.

**Level 2 with prompt v5** (`make eval-l2-refresh`, gemma4:26b, n=150, 36 negatives): tool 88.0%,
args 95.3%, negatives calling a tool 0.0%, replay mismatches 0. With v4 it was 81.3% / 97.3%.
The prompt change was layout only, and the tool schemas changed in one place (`category`
maxLength). A swing of 6.7 points from a layout edit says more about this model's sensitivity
to wording than about a real improvement; it is recorded, not claimed. G-L2-TOOL (≥ 90%) stays
not reached, as decided.

### Block 22 · A new export that cannot quietly break the shop (merge of `ingest-hardening`, ≈ 15 min to review)

ADR-001 checked what the rows say and assumed the file was read correctly. Planting the
mistakes a spreadsheet export really makes showed four ways it was not. Each now stops with a
named code, the previous catalogue stays live, and each has a seeded fixture (ADR-009):

- `schema_mismatch` covers a duplicated column. This one used to set all 152 prices to 1.00
  and report `ok`.
- `empty_export` stops a 0-byte or header-only file on every build, including the first.
- `unreadable_export` stops anything that is not UTF-8. A UTF-8 BOM, which Excel writes, is
  accepted. Decided: never guess cp1252, because a wrong guess changes product text with no
  error at all.
- `malformed_row` stops a row longer or shorter than the header, naming the line. Rows are now
  read with `csv.reader`; `DictReader` silently dropped or padded fields.
- The injection check matches on an NFKC-folded copy with invisible characters removed. Before,
  4 of 5 hidden-character variants passed. The served text is unchanged.
- **Change guard:** if more than 50% of products change price or stock, the ingest stops. A
  real sale is accepted with one line in `decisions.yaml`, keyed by the hash of that exact
  file, with a reason. The stop report prints the line to paste.

Numbers on main after the merge: `make gate-fast` 409 passed, coverage 99.75%;
`make eval-ingest` 17/17 (was 11/11); `make ingest` 0 pending, empty diff, served products
byte-identical; `make eval-l1` 74/74; `make spec-lint` 0.

Left out, and listed in ADR-009: a per-export acceptance for the removal guard (today only
the ratio can be raised), header names in other cases (`PRICE_EUR` stops), and look-alike
letters from other alphabets inside injection phrases.

### Block 23 · The same four tools over MCP (merge of `mcp-server`, ≈ 20 min to review)

The platform documents an MCP client (full endpoint URL, static headers, no OAuth) but not
its protocol revision. So the server speaks both eras: the `initialize` handshake and the
2026-07-28 revision without it (ADR-008). It runs on the official SDK (`mcp==2.3.0`, with
`jsonschema` declared), uses its low-level server, and is mounted at `/mcp` in the same
service behind the same key.

**Why REST and MCP cannot drift:** the MCP tool list is built from `tools.TOOLS`, and every
call goes through `service.execute`. A result carries the REST body as `structuredContent`
plus a text block with exactly the bytes REST sends, so a model reads the same text over both.
Arguments are read as REST reads them: jsonschema checks types, bounds and lengths, while
closed-set values go through the shared normalisation (`HER` works on both). A domain error
comes back as `isError` with the REST error body, so the model can still follow
`did_you_mean`.

**Measured** (`make eval-mcp`, in-process): parity 74/74 level-1 cases byte-identical with REST,
and conformance 16/16 protocol checks:
- initialize and version negotiation;
- tools/list against `tools.TOOLS`;
- tools/call success, domain error and invalid argument;
- malformed JSON and an invalid request;
- 401 without the key;
- 405 on GET;
- no session required.

The same eval run over real HTTP against a local server gave the same numbers. The check was
also tested against planted defects: changing the text bytes dropped parity to 0/74, so it
does catch drift. On main after the merge: `make gate-fast` 449 passed, `make eval-l1` 74/74,
`make eval-ingest` 17/17, `make spec-lint` 0, `make secrets` 0 (the new catalogue version
hashes were reviewed into the baseline).

One deliberate addition: `GET /mcp` returns 405. Without it the SDK holds the GET open
indefinitely, which a stateless JSON server has no use for.

### Block 24 · First run of the fifteen scenarios: two real weaknesses, both in the vocabulary (≈ 30 min)

One run per suite, prompt v4 still on the draft (the v5 layout had not been pasted yet): core
4/6, extra 2/3, extended 5/6. Every Fail was read against the tools' real output:

- **core-1, real.** "She likes cooking" → `search_products("cooking")` returns only the
  cookbook. The agent said truthfully "the only cooking match within 50", but a shopper means
  kitchen things: the Herb Garden Kit and the Moka Pot fit. The tool is right by its own rules
  and wrong for the shopper. This is a vocabulary gap, not a prompt problem.
- **core-4, real.** "Tech gadgets for a 12-year-old" → "gadget" matches nothing and "tech"
  matches three products by description (alarm clock, noise machine, smart plug). The category
  is literally "Tech & Gadgets", but category names are not searched, so the speaker and the
  Instant Camera never came up.
- **extra-7, judge.** The agent said the catalogue does not mention a gift note, which is the
  honest answer. The criterion is now explicit that pointing to customer service is optional.
- **ext-13, judge.** The agent offered to look above the budget without raising it. The
  criterion now separates offering from raising.

Both real failures share a cause with the two found while writing the scenarios (pets matching
human recipients, "gardening" ≠ "garden"). Samuel approved fixing them as one change: branch
`search-quality`, ADR-010, measured on level 1 before and after.

The format problem Samuel reported (products running together in the widget) was observed on
the published v4. The v5 layout has not been on the platform yet, so it is not yet known
whether it fixes it.

### Block 25 · A landing page that belongs to the shop (merge of `landing`, ≈ 15 min to review)

The brief asks for the widget embedded and customised so it feels like the client's brand. The
shop is now **Ribbon & Co.** (invented). Its page is served at `/` by the same service, with no
key, outside both specs. It has a brand header, a hero, four example prompts that open the
chat and send themselves, a three-step "how it works", and a footer that names the demo, the
OpenAPI spec and the MCP endpoint.

Decisions:
- **The chat opens on its own on desktop only, once per visit.** On a phone it would cover
  the page, so a pop-up message invites instead.
- **The workspace token is not in the repository.** It is read from `WIDGET_TOKEN` at start,
  embedded only if it is `[A-Za-z0-9-]{1,64}`, and otherwise the page renders without the
  chat.
- **No web font and no other third-party script**, so the widget is the page's only outside
  dependency.
- **Contrast at AA everywhere.** The lowest is 5.9:1.
- **Security headers stop framing by other sites, but scripts are not restricted.** The
  platform does not document the widget's script origins, and a guessed policy could break it.

The colours, texts and launcher icon (`/ribbon.svg`) the platform needs are entered by hand in
Web Chat → Style/Home. Checked: `make gate-fast` 460 passed, `make spec-lint` 0,
`make eval-mcp` 74/74 and 16/16, `make secrets` 0. The page was also rendered headless at 390 px
and 1440 px; that caught two layout faults, both fixed. The widget itself is untested until
the deploy carries `WIDGET_TOKEN`.

### Block 26 · README, and what writing it uncovered (≈ 20 min to review)

The README was drafted from the ADRs, this journal, `docs/PLATFORM.md` and the reports, with
every number kept in a single "Measured" table so it can be refreshed in one place before
submission. The test page link is a placeholder until submission.

Writing it was also an audit, and it turned up three gaps between what is sealed and what runs:

- **Latency protocol.** `docs/GOALS.yaml` seals "20 warm-up requests discarded, then 200
  requests per run, 3 runs". The script ran 20 per run with no warm-up, so the published p95
  (264.8 ms) was measured on n=20 per run. The script now follows the sealed protocol, and the
  goal is re-measured after the next deploy. The old number stays in history as what it was.
- **`make sim-report` and `make done`** are named in the goals and `CLAUDE.md`-level rules but
  did not exist. They are being built: Simulations results are recorded by hand per run (the
  platform has no reliable export), and `make done F=<n>` reads every goal's artifact and
  compares it with its sealed threshold.
- `docs/PLATFORM.md` still says the agent fields come from prompt v3. It is updated once v5 is
  confirmed on the platform.

### Block 27 · Vocabulary fixed, and a gate that says "not done" (≈ 30 min to review and merge)

**Search vocabulary (branch `search-quality`, ADR-010).** The simulations and the scenario
writing found four queries that failed a shopper while following the search's own rules. All
four were fixed with data judgements, not ranking changes:

- **Pets get their own recipient.** A `recipient_overrides` entry reads the export's `anyone`
  as `pet` for the Pets category. `anyone` now means any person, so a dog toy no longer
  answers "toy for kids".
- **Two synonym groups:** `[garden, gardening, gardener]` and `[cooking, cook, kitchen]`.
- **Chosen category-name words** (`kitchen`, `tech`, `gadget`, `pet`) are searchable as the
  weakest field. Four options were measured on the 74 approved cases, and this was the only
  one that fixed the queries and changed none of them. A whole category name as a field
  changed two or three approved cases.
- **The unused-synonym check had a blind spot.** It looked in text that included category
  names, so a group found only there passed while matching nothing. It now runs the search.

Before → after:
- "cooking" (her, ≤50): the cookbook only → cookbook, Herb Garden Kit, Moka Pot, Tea Flight.
- "gardening" (him, ≤60): nothing → three garden products.
- "tech gadget" (kids, ≤100): 3 → 10 matches.
- "toy" (kids, ≤30): a dog toy → nothing in budget, and the right over-budget items.

Level 1 is now v5: 81 cases, including "chef's knife" over HTTP. 18 cases await Samuel's
review. No approved case changed.

**`make sim-report` and `make done F=<n>`.**
- Simulation verdicts are recorded by hand per run in `evals/simulations/results.csv`, with
  both the judge's verdict and the verdict after reading.
- A suite's result counts every run of the same model and agent version together, so
  re-running until one run passes cannot turn a setup green.
- `make done F=<n>` reads each goal's artifact, compares it with the sealed threshold and
  checks the lock.

Today: `make done F=3` → 17/19.
- G-L2-TOOL fails (0.88 < 0.90), as known.
- G-SIM-CORE fails (0.9167 < 1.0): the two real core-1/core-4 failures of run r6 are counted
  with the earlier v4 runs. They were fixed by ADR-010, which is not deployed yet. Runs after
  the deploy carry a new agent version label (v6), so they are counted on their own.

On main: `make gate-fast` 517 passed, coverage 99.77%; `make eval-l1` 81/81; `make eval-mcp`
81/81 and 16/16; `make eval-ingest` 17/17; `make spec-lint` 0; `make secrets` 0. Level 2 is
being re-recorded, because the recipient description changed the tools hash.

### Block 28 · Prompt v6 for the widget's rendering, and closing the loose ends (≈ 45 min)

**Format, second attempt.** Samuel pasted v5 into the platform and the products still ran
together in Preview: a gap after each name line, none between products. The model followed the
layout; the widget's Markdown rendering decides the spacing. Rather than guess the renderer's
rules, v6 removes the dependency on blank lines: each product is one numbered list item on a
single line (`1. **Name** · €price · usually ships in N days — reason`). A list separates
items in any renderer, and the numbers let a shopper say "the second one". Level 2 with v6
and the ADR-010 tool descriptions (`make eval-l2-refresh`, n=150): tool 88.7%, args 95.3%,
negatives calling a tool 0%, replay mismatches 0. It is to be confirmed on the platform.

**Loose ends.**
- The README's single "Measured" table was refreshed: tests 517, level 1 81/81, MCP 81/81,
  simulations through `make sim-report`. The latency row is marked as measured before the
  sealed protocol was enforced.
- `.env.example` now lists every variable (`WIDGET_TOKEN`, `SHOP_TIMEZONE`, `TEST_PAGE_URL`),
  as the deliverables checklist expects.

**Waiting on the deploy:** latency under the sealed protocol, public checks including the
landing page, level 1 and MCP against the public URL, re-import of the tool descriptions on
the platform (the recipient description changed), MCP connection on the platform, and the
final Simulations under agent version v6.

### Block 29 · The deploy, measured from outside, and a latency goal that fails (≈ 30 min)

Samuel added `WIDGET_TOKEN` in Coolify and redeployed commit f2ecc6e. Coolify also shows
webhook deploys now, so pushes to `main` deploy on their own. Measured from the client
machine against https://catalog.178.18.243.118.sslip.io:

- `make check-public`: 7/7, now including the landing page answering without a key.
- Level 1 over the public URL (`CATALOG_URL=… evals/golden/l1/run.py`): 81/81 exact.
- `make eval-mcp URL=…`: parity 81/81, conformance 16/16.
- Prompt v6 on the platform: the numbered list renders with each product clearly apart.

**G-LATENCY-P95 (≤ 300 ms) fails under the sealed protocol.** Two measured attempts, 20 warm-up
calls, 3 runs × 200 calls per endpoint: max p95 384.9 ms, then 357.9 ms. The medians are
200–250 ms. A curl breakdown of one call from this machine: TCP connect ≈ 50 ms, TLS done at
≈ 115 ms, first byte at ≈ 170 ms. The script opens a new TCP and TLS connection for every
call, so about two thirds of each measurement is the handshake across the network, not the
service. The same protocol over one reused connection (keep-alive, as a server-to-server
client such as the platform would use) gives a max p95 of 145.8 ms, medians ≈ 60 ms.

The sealed protocol says "20 warm-up requests discarded", which only means something if the
connection survives the warm-up. Even so, changing how the number is measured after it failed
is Samuel's call, not mine. Stopped and asked, with the three options and the numbers. The
first published value (264.8 ms at 20 calls per run) was below the threshold only because of
its small sample.

### Block 30 · Latency option A, an MCP connection that fails on the platform, and prompt v7 (≈ 40 min)

**Latency: option A, decided by Samuel.** The script now reuses one connection for the warm-up
and every call. It records `"connection": "reused"` in the report, and its comment says why.
Both numbers stay in the record: 357.9–384.9 ms opening a connection per call, 145.8 ms over a
reused one. It is re-measured after the deploy.

**MCP on the platform: "Connected", then nothing.** Adding the server showed Connected, but the
Agent Block's tool dropdown stayed empty, and a later Save reported "connection failed". From
here, every probe of the public endpoint answers as the spec expects:
- `initialize` for 2025-03-26 and 2025-06-18;
- `tools/list` with or without a prior initialize and with or without the version header;
- `notifications/initialized` → 202, `ping`, and the modern `server/discover` envelope check;
- `Accept: application/json` alone is accepted; `text/event-stream` alone gets 406;
- GET, DELETE, OPTIONS and HEAD get 405.

The two candidates left are clients that expect SSE responses, or that call
`resources/list`/`prompts/list` and treat "method not found" as a failure. Guessing would be
cheap but blind. Decided: log one line per `/mcp` request instead — HTTP method, JSON-RPC
method, protocol header, session header, Accept, user agent and status, never the key. The
container log then shows exactly what the platform sends. Tests first:
`TestRequestLog` (2 tests).

**Prompt v7, one line.** On the landing page, over-budget products were shown as "shipping time
not listed". Near-miss products are pointers by design (ADR-007) and carry no shipping time, so
the model filled the format line with that phrase. They are now listed as "**Name** · €price ·
€N over budget". Decided: a prompt line rather than adding `shipping_days` to every near-miss
reference, because the reference is deliberately small, and the change would rewrite the
expectations of every level-1 case that has one, the night before submission. Level 2 is
being re-recorded.

**Latency, re-measured with option A** (`make latency URL=…`, 20 warm-up calls, 3 runs × 200 per
endpoint, one reused connection): max p95 193.4 ms, medians 60–73 ms. G-LATENCY-P95 passes.
The first attempt after the change hit a 502 during a webhook deploy's container switch, so it
was rerun once the deploy had finished. Level 2 with prompt v7: tool 87.3%, args 95.2%,
negatives 0%, replay mismatches 0, within the noise of v6 (88.7%).

### Block 31 · The MCP failure explained by its own log, a budget slip, and the first v7 runs (≈ 40 min)

**MCP.** The new request log answered the question in one deploy. Every request from the
platform's client (`mint/1.9.3`, from AWS addresses) was an `initialize` refused with 401. The
transport was fine; the credential was not arriving as expected. Two changes:
- `/mcp` also accepts the same key as `Authorization: Bearer <key>`. The platform describes MCP
  auth as "a bearer token or an API key", and many MCP clients send the first. REST keeps
  `X-API-Key` only, as its spec documents.
- The log line now records which credential header arrived and its length, never its value.
  So if the next attempt still fails, it shows whether the header is missing, renamed or
  carries a different value.

Tests first (`TestBearer`, one more `TestRequestLog`). `make gate-fast` 522 passed,
`make eval-mcp` 81/81 and 16/16.

**Simulations on prompt v7** (gpt-5.6-luna, draft): core 5/6, extra 3/3, extended 6/6. The
judge and the reading agree on every verdict (`make sim-report`, runs r9–r11).
- The one Fail is real. core-3, Italian: "budget sui 40". The model used the margin the
  `max_price` description allows for an approximate budget, then called the 42-euro candle
  "entro il budget" and said it "rientra", while also saying it was 2 euros over.
- Prompt v8 adds one line: the budget is the number the shopper said, and anything above it is
  reported as over, with the amount. The margin stays, because it is what lets the agent show
  the liked item at all.

**Widget.** The platform would not take the SVG URL as the avatar or launcher icon, so a
512 px PNG of the same ribbon was rendered for upload.

**Level 2 with prompt v8** (`make eval-l2-refresh`, n=150): tool 90.0%, args 95.5%, negatives 0%,
replay mismatches 0. G-L2-TOOL is met, exactly at its threshold. Recorded as it is: the line
added in v8 is about budgets, not tool choice, and layout-only edits earlier moved this number
by up to 6.7 points. The honest reading is "about 88–90% on this local model", and the README
says so next to the number.

### Block 32 · The platform sends the secret's name, not its value (≈ 15 min)

The credential log closed the MCP question. Every `initialize` from the platform's client
carries `x-api-key` with **19 characters**. The service key has 64. `[[CATALOG_API_KEY]]`, the
platform's placeholder for that secret, has exactly 19. So the MCP client sends the
placeholder unresolved. The same secret is resolved in the Tool Collection's header, where
REST works, and the platform's documentation says secrets in MCP server headers "are resolved
server-side at runtime". Our server cannot fix this, and it should not accept the placeholder.

Workaround for the sandbox: enter the key's value directly in the MCP header instead of as a
secret. Decided: acceptable here, because the workspace is a test sandbox, and the cost (the
key visible to workspace members in that one field) is written down. In production the right
move is to report it to the platform and keep the secret.

Two smaller platform findings while styling the widget:
- The platform rejects an SVG URL for the avatar and launcher icon, so a 512 px PNG with a
  transparent background is uploaded instead.
- An `&` in the assistant name is shown escaped ("Ribbon &amp; Co."), so the widget uses
  "Ribbon and Co.".

Prompt v8 checked in Preview: "about 40" → the Ember candle is listed as "€2 over budget" and
the agent asks before stretching.
