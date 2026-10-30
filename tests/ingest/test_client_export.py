"""The client's real export: it must ingest on its own, and always to the same bytes."""

from pathlib import Path

import pytest

from catalog.ingest.__main__ import build


@pytest.fixture(scope="module")
def outputs(root: Path) -> tuple[bytes, dict[str, object]]:
    return build(root / "data" / "gift-shop-catalog.csv", root / "data" / "decisions.yaml", previous=None)


def test_ingests_with_no_decision_pending(outputs: tuple[bytes, dict[str, object]]) -> None:
    _, report = outputs
    assert report["status"] == "ok"
    assert report["pending_decisions"] == 0


def test_counts_match_the_audit(outputs: tuple[bytes, dict[str, object]]) -> None:
    _, report = outputs
    counts = report["counts"]
    assert counts == {"rows": 152, "products": 152, "distinct_products": 150, "categories": 11}  # type: ignore[comparison-overlap]


def test_is_byte_identical_across_runs(root: Path, outputs: tuple[bytes, dict[str, object]]) -> None:
    again, _ = build(root / "data" / "gift-shop-catalog.csv", root / "data" / "decisions.yaml", previous=None)
    assert again == outputs[0]


def test_known_data_quality_issues_are_reported(outputs: tuple[bytes, dict[str, object]]) -> None:
    _, report = outputs
    warnings = {(w["code"], tuple(w["product_ids"])) for w in report["quality_warnings"]}  # type: ignore[attr-defined]
    assert ("thin_description", ("BS-015", "HL-013")) in warnings
    assert ("missing_rating", ("BS-014", "EX-001", "EX-002", "HL-008", "HL-026")) in warnings
