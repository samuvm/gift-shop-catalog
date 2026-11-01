"""Properties of the ingest over the client's real export: what an export tool may vary must not matter."""

import csv
import io
import random
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from catalog.domain.models import Product
from catalog.ingest.decisions import Decisions, load_decisions
from catalog.ingest.pipeline import EXPECTED_COLUMNS, ingest_export, read_export, run_ingest

Rows = list[dict[str, str]]


@pytest.fixture(scope="module")
def decisions(root: Path) -> Decisions:
    return load_decisions((root / "data" / "decisions.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rows(root: Path) -> Rows:
    return read_export((root / "data" / "gift-shop-catalog.csv").read_bytes()).rows


@pytest.fixture(scope="module")
def baseline(rows: Rows, decisions: Decisions) -> list[Product]:
    return run_ingest(rows, list(EXPECTED_COLUMNS), decisions).products


def export_bytes(rows: Rows, columns: list[str]) -> bytes:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


@given(st.permutations(EXPECTED_COLUMNS))
def test_column_order_does_not_change_the_catalogue(
    rows: Rows, decisions: Decisions, baseline: list[Product], columns: list[str]
) -> None:
    _, result = ingest_export(export_bytes(rows, list(columns)), decisions)
    assert result.products == baseline


@given(st.randoms(use_true_random=False))
def test_row_order_does_not_change_the_catalogue(
    rows: Rows, decisions: Decisions, baseline: list[Product], rnd: random.Random
) -> None:
    shuffled = rnd.sample(rows, len(rows))
    _, result = ingest_export(export_bytes(shuffled, list(EXPECTED_COLUMNS)), decisions)
    assert result.products == baseline


@given(st.lists(st.sampled_from(["", " ", "  ", "\t", "\u00a0"]), min_size=8, max_size=8))
def test_padding_whitespace_does_not_change_the_catalogue(
    rows: Rows, decisions: Decisions, baseline: list[Product], pads: list[str]
) -> None:
    # Cells cycle through the drawn paddings, so each column gets different padding row by row.
    padded = [
        {c: f"{pads[(i + j) % 8]}{v}{pads[(i + j + 3) % 8]}" for j, (c, v) in enumerate(r.items())}
        for i, r in enumerate(rows)
    ]
    _, result = ingest_export(export_bytes(padded, list(EXPECTED_COLUMNS)), decisions)
    assert result.status == "ok"
    assert result.products == baseline


@given(st.randoms(use_true_random=False))
def test_an_export_compared_with_its_own_catalogue_shows_no_change(
    rows: Rows, decisions: Decisions, baseline: list[Product], rnd: random.Random
) -> None:
    shuffled = rnd.sample(rows, len(rows))
    _, result = ingest_export(export_bytes(shuffled, list(EXPECTED_COLUMNS)), decisions, previous=baseline)
    assert result.status == "ok"
    assert (result.diff.added, result.diff.removed, result.diff.changed) == ([], [], {})
