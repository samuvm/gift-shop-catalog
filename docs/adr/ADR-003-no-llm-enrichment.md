# ADR-003 · No LLM enrichment step in the catalogue pipeline

- **Status:** accepted · 2026-10-29
- **Deciders:** Samuel Viciana
- **Related:** ADR-001 (data cleaning), ADR-002 (tool interface)

## Context

Some descriptions say little about what the product actually is. TG-001 reads *"Thirty hours
with noise cancelling on. The case is slim enough for a laptop bag…"*. It never says
"headphones", "wireless" or what the product is made of. The question was whether to add a
derived column, written by an LLM, that merges every attribute into one richer text so search
and recommendations have more to work with.

## What we wanted to do

Run each row through an LLM once, at ingest time, and store the output as a new column, never
over the client's own text. The first candidate was a local model (Ollama on a separate machine
reached over an OpenAI-compatible API), so that the client's data never leaves the premises.

## Options considered

1. **LLM-written column (local or hosted).** Can infer uses and synonyms ("good for flights",
   "for someone who works from home").
2. **Deterministic column built by code.** Concatenates name, category, subcategory, brand,
   material, colour, recipient, occasions, tags and description.
3. **Nothing.** Serve the cleaned columns only.

## Analysis

- **Most of the "missing" information is already in other columns.** The name says "Wireless
  Headphones ANC". Subcategory, material and tags fill in the rest. Option 2 recovers it with
  zero hallucination risk, unit tests and free regeneration on every export.
- **What only an LLM adds is inference, and inference is exactly where it invents facts.** A
  generated "Bluetooth 5.3" or "waterproof" would be presented to a shopper as the shop's word.
  Containing that risk needs constrained output, a grounding check and human review of every
  changed row on every export. That is a permanent cost per export, not a one-off.
- **The agent is already an LLM.** At conversation time it reads the attributes and does the
  inference itself ("a turntable suits someone who collects records"). A second model upstream
  moves the same reasoning to another place and adds a component to run, version and explain.
- **Retrieval is the real bottleneck, and at this size it is not a bottleneck.** The agent only
  reasons about products a tool returned. With 150 products in 11 categories (at most 28 per
  category), a category plus structured filters narrows any request to a handful of items. The
  vocabulary gap between shopper and catalogue is also closed by the agent itself: it calls the
  tool with "headphones", whatever language the shopper used.
- **Operational cost.** A pipeline that depends on a model (local or hosted) must pin model,
  digest, prompt and temperature to be reproducible. A reviewer cloning the repo would not have
  the same model.

## Decision

Option 2. At ingest, code derives two columns:

- `search_text`: every attribute including the description. Used for matching, never returned
  in full.
- `search_text_compact`: the same attributes without the description. A fallback when a
  response must be lighter. Whether responses use it is decided in ADR-002 and measured in
  tokens.

No LLM runs in the ingest pipeline or in the service.

## Consequences

- Ingest stays deterministic: same CSV and same `decisions.yaml` give the same catalogue, byte
  for byte.
- Thin descriptions ("Great gift.", "A card.") are reported as a data-quality issue for the
  client, not hidden.

## When to revisit

- The catalogue grows to the point where category plus filters no longer narrow to a few items
  (order of thousands of products).
- The interface eval (level 2) or the search set (level 1) shows misses caused by vocabulary
  that no column contains.

In either case the revised design would be: structured output, a grounding check by code
(every number, material or brand in the output must exist in the source row), a separate
column marked as inferred, incremental per-row hashing, and human review of changed rows.
