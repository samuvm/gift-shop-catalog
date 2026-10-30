"""`python -m catalog.ingest`: exit codes, and a stopped ingest never overwrites the served catalogue."""

import csv
import shutil
from pathlib import Path

from catalog.ingest.__main__ import main


def run(root: Path, csv_path: Path, out: Path) -> int:
    return main(
        ["--csv", str(csv_path), "--decisions", str(root / "data" / "decisions.yaml"), "--out", str(out)]
    )


def test_clean_export_writes_catalogue_and_report(root: Path, tmp_path: Path) -> None:
    assert run(root, root / "data" / "gift-shop-catalog.csv", tmp_path) == 0
    assert (tmp_path / "catalog.json").exists()
    assert '"status": "ok"' in (tmp_path / "ingest-report.json").read_text(encoding="utf-8")


def test_stopped_ingest_keeps_the_previous_catalogue(root: Path, tmp_path: Path) -> None:
    assert run(root, root / "data" / "gift-shop-catalog.csv", tmp_path) == 0
    served = (tmp_path / "catalog.json").read_bytes()

    broken = tmp_path / "broken.csv"
    shutil.copy(root / "data" / "gift-shop-catalog.csv", broken)
    with broken.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    rows[0]["category"] = "Garden Furniture"
    with broken.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    assert run(root, broken, tmp_path) == 1
    assert (tmp_path / "catalog.json").read_bytes() == served
    report = (tmp_path / "ingest-report.json").read_text(encoding="utf-8")
    assert '"status": "stopped"' in report
    assert "unknown_category" in report


def test_second_run_reports_no_changes(root: Path, tmp_path: Path, capsys: object) -> None:
    run(root, root / "data" / "gift-shop-catalog.csv", tmp_path)
    run(root, root / "data" / "gift-shop-catalog.csv", tmp_path)
    report = (tmp_path / "ingest-report.json").read_text(encoding="utf-8")
    assert '"added": []' in report
    assert '"removed": []' in report
    assert '"changed": {}' in report
