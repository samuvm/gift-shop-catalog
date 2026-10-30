# ADR-004 · Serve the catalogue from an in-memory snapshot

- **Status:** accepted · 2026-10-30
- **Deciders:** Samuel Viciana
- **Related:** ADR-001 (data cleaning), ADR-002 (tool interface), ADR-003 (no LLM enrichment)

## Context

The client hands over the catalogue as a CSV export. The question is where the service reads
products from when the agent calls a tool: the CSV itself, a database, a search engine, or
something in between.

## How data flows today

1. `make ingest` is the only code that reads the CSV. It cleans it with the rules and
   `data/decisions.yaml` (ADR-001) and writes `data/build/catalog.json`. That file holds 152
   validated products plus a version block with the hashes of the export, the decisions and the
   result.
2. The JSON file ships inside the container image.
3. At startup the service loads the file, validates every product, and builds the in-memory
   lookups: products by ID, category names, and the word sets per field used for scoring.
4. Every request is answered from memory. Nothing is read from disk after startup, and the CSV
   is never opened by the service.
5. A new export means: run `make ingest`, review the diff, commit, redeploy. Each export
   replaces the catalogue, guarded against mass removal (ADR-001).

## Options considered

1. **In-memory snapshot from a JSON file.** One artefact, versioned in git, no moving parts.
2. **SQLite file built by the ingest**, with FTS5 for text search and indexes on category and
   price. Still one file and still a snapshot, but queried instead of scanned.
3. **A database server or search engine** (PostgreSQL with full-text or trigram search,
   OpenSearch, Meilisearch). Supports live updates and large volumes.

## Analysis

- **Size.** 152 products is 200 KB of JSON. Measured with `uv run python scripts/scale_probe.py`:

  | Catalogue | Build at startup | Peak memory | Search p50 | Search p95 |
  |---|---|---|---|---|
  | 152 products (served) | 4 ms | 0.6 MB | 0.13 ms | 0.20 ms |
  | 15,200 products (×100 synthetic) | 356 ms | 64 MB | 14 ms | 35 to 39 ms |

  Each search scans every product, so cost grows linearly with the catalogue: ×100 products
  gives roughly ×100 time and memory. Network and TLS dominate any request at today's size.
- **Read-only and rarely updated.** The brief describes a single export and read-only tools.
  Nothing writes while the service runs, so there is no concurrency, no migration and no
  consistency problem to solve.
- **Reproducibility.** The served data is a file in git with a content hash. Every response
  carries `meta.catalog_version`, so any answer can be traced to the exact export that
  produced it. A reviewer who clones the repository gets the same catalogue byte for byte.
- **Cost of options 2 and 3.** Both add a component to run, back up and explain. At this size
  they buy no measurable speed. Option 3 also adds a network hop to every call.

## Decision

Option 1. The service loads `data/build/catalog.json` once at startup and answers from memory.
Only `Catalog` (`src/catalog/domain/catalog.py`) knows how products are held. The tools, the
OpenAPI document, the error contract and the MCP server (when added) only see `Catalog`'s
methods. Replacing the storage changes that one class and the loader, not the interface the
agent was designed against.

## Consequences

- No database to operate. Startup fails loudly if the file is missing or a product does not
  validate.
- **Stock is only as fresh as the last export.** An item that sold out after the export still
  shows as available until the next ingest and redeploy. Acceptable for an assignment with one
  export. For a live shop it is the first thing to change (see below).
- A new export needs a redeploy. That keeps every catalogue change reviewed and in git, which
  is a feature at this scale.

## When to revisit, and what would change

The design stops fitting long before "millions of rows". The thresholds below are estimates
extrapolated from the linear measurement above, not measured limits:

- **Tens of thousands of products** (search p95 approaching tens of milliseconds per call,
  hundreds of MB per worker). Move to option 2: the ingest writes a SQLite file with FTS5
  (BM25 ranking) and indexes on category, price and stock. It is still one versioned
  artefact, and nothing else changes.
- **Hundreds of thousands to millions of products, or frequent updates.** A linear scan would
  take on the order of a second per search and several GB of memory per worker. Move to
  option 3, plus:
  - **Incremental ingest** keyed by product ID and a per-row hash, instead of replacing the
    whole snapshot.
  - **Stock and price from a live source**, separate from descriptive data. Stock changes far
    more often than descriptions.
  - **Cursor pagination** instead of `offset`, which degrades on deep pages.
  - **Category plus filters stop narrowing to a handful of items**, so retrieval quality
    becomes the bottleneck. At that point semantic search, and the enrichment ADR-003 set
    aside, are worth reconsidering, under the same grounding rules.
