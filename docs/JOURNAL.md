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
