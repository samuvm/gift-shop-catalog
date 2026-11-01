# ADR-009 · A new export: reading the file safely, and how much may change at once

- **Status:** accepted · 2026-11-01
- **Deciders:** Samuel Viciana
- **Related:** ADR-001 (data cleaning). Extends ADR-001's stopping cases and its decisions file
  with a change guard. Everything else in ADR-001 stands. `data/decisions.yaml`
  (`change_guard`), `evals/ingest/run.py`.

## Context

ADR-001 checks what the rows say. It assumed the file itself was read correctly. The client
will send new exports, possibly saved from a spreadsheet, so we planted the mistakes such a file
can carry and ran them through `make ingest`. Five passed or crashed:

- a second `price_eur` column of 1.00 ingested with status ok, and all 152 prices became 1.00;
- an export with a header and no rows, on a first build, wrote an empty catalogue;
- a Windows-1252 or UTF-16 export crashed the command with no report;
- a row with one field more than the header lost that field silently;
- `Ig\u200bnore previous instructions`, with a zero-width space inside a word, escaped the
  injection check.

Separately, nothing stopped an export where most prices change at once. A shifted column or a
wrong currency keeps values in range, so no row-level rule sees it.

## Decision

**1. The file is checked before its rows.** New stopping cases, added to ADR-001's table:

| Code | Anomaly |
|---|---|
| `unreadable_export` | The file is not UTF-8 (including UTF-16, with or without a byte-order mark) |
| `empty_export` | No header, or a header and no rows. Stops on every build, not only when there is a catalogue to compare with |
| `malformed_row` | A row with more or fewer fields than the header, named by line and product ID |
| `schema_mismatch` | Now also a column name that appears twice |
| `mass_change` | More than half the current catalogue's products change price or stock in one export (point 4) |

A ragged row stops the ingest instead of being padded or cut. An unquoted comma shifts every
column after it, so the row's other values can't be trusted.

**2. Encoding: UTF-8, with or without a byte-order mark.** Excel's "CSV UTF-8" writes the mark,
so it is accepted. Anything else stops and the report asks for a UTF-8 export. The encoding is
never guessed. Decided: no fallback to Windows-1252, because a wrong guess changes product
names without any error (a Mac Roman `ó` read as Windows-1252 becomes `—`), and a new export
from the client fixes the file at its source. The 2026-10-29 export is plain ASCII.

**3. The injection check reads folded text.** Before matching, the text is NFKC-normalised
(full-width letters become plain ones) and Unicode format characters are dropped (zero-width
spaces, soft hyphens, word joiners, bidirectional controls). The folding applies only to the
match. The served text is not changed.

**4. A change guard, shaped like the removal guard.** `change_guard.max_changed_ratio: 0.50`.
If more than half the current catalogue's products change price or stock, the ingest stops
with `mass_change`. Exactly half passes, as the removal guard passes exactly its ratio. A
legitimate mass change, such as a seasonal sale or a stocktake, is accepted with one line under
`change_guard.accepted_exports`: `{source_sha256, reason}`. The stop report prints that line with
the hash filled in. The report records an accepted export under `decisions_applied` as
`mass_change_accepted`, with its reason. Decided: key the acceptance by the sha256 of the file
as received, not by a flag or a date. A flag stays on and accepts the next broken export too.
A hash accepts one file, the one a person looked at.

## Consequences

- `make eval-ingest` has 17 fixtures (11 before). Every new stopping code has one, and so do a
  hidden injection and an unaccepted sale. Result: 17/17.
- Property tests on the real export check that column order, row order and padding whitespace
  leave the catalogue unchanged, and that an export compared with its own catalogue shows no
  diff.
- Adding `change_guard` changed `decisions_sha256` in the served catalogue's version.
  `products_sha256` and `served_sha256` did not change.
- Each accepted export matches one file only. Once that export is superseded, its entry has no
  effect and can be removed.
- Not covered: header names are not normalised (`PRICE_EUR` stops as `schema_mismatch`, on
  purpose); look-alike letters from other scripts (Cyrillic `а`) in an injection phrase; and the
  removal guard still has no per-export acceptance. Its ratio is the only way to let a large
  delisting through.
