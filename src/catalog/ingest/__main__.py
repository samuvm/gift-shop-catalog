"""`python -m catalog.ingest`: build the served catalogue and the ingest report.

Exit code 0 when the export is fully explained by the rules and decisions; 1 when a person has
to decide something. On 1 the previous catalogue is left untouched and only the report is written.
"""

import argparse
import sys
from pathlib import Path

from catalog.domain.models import Product
from catalog.ingest.decisions import load_decisions
from catalog.ingest.pipeline import ingest_export
from catalog.storage import dumps, encode_catalog, read_catalog, sha256

ROOT = Path(__file__).resolve().parents[3]


def build(
    csv_path: Path, decisions_path: Path, previous: list[Product] | None
) -> tuple[bytes, dict[str, object]]:
    """Run the ingest. Returns the catalogue bytes (empty when stopped) and the report."""
    decisions_raw = decisions_path.read_bytes()
    decisions = load_decisions(decisions_raw.decode("utf-8"))
    export, result = ingest_export(csv_path.read_bytes(), decisions, previous)

    catalog = b""
    version: dict[str, str] = {
        "source_sha256": export.source_sha256,
        "decisions_sha256": sha256(decisions_raw),
    }
    if result.status == "ok":
        catalog, version = encode_catalog(
            result.products,
            version["source_sha256"],
            version["decisions_sha256"],
            decisions.search.model_dump(),
        )
    report: dict[str, object] = {
        "status": result.status,
        "pending_decisions": len(result.anomalies),
        "counts": {
            "rows": len(export.rows),
            "products": len(result.products),
            "distinct_products": sum(p.search_primary for p in result.products),
            "categories": len({p.category for p in result.products}),
        },
        "catalog_version": version,
        "anomalies": [a.model_dump() for a in result.anomalies],
        "quality_warnings": [w.model_dump() for w in result.quality_warnings],
        "rules_applied": [f.model_dump() for f in result.rules_applied],
        "decisions_applied": [f.model_dump() for f in result.decisions_applied],
        "diff": result.diff.model_dump(),
    }
    return catalog, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m catalog.ingest", description=__doc__)
    parser.add_argument("--csv", type=Path, default=ROOT / "data" / "gift-shop-catalog.csv")
    parser.add_argument("--decisions", type=Path, default=ROOT / "data" / "decisions.yaml")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "build")
    args = parser.parse_args(argv)

    catalog_path, report_path = args.out / "catalog.json", args.out / "ingest-report.json"
    previous = read_catalog(catalog_path)[1] if catalog_path.exists() else None
    catalog, report = build(args.csv, args.decisions, previous)

    args.out.mkdir(parents=True, exist_ok=True)
    report_path.write_bytes(dumps(report))
    if catalog:
        catalog_path.write_bytes(catalog)

    print(f"ingest {report['status']}: {report['counts']} · pending decisions: {report['pending_decisions']}")
    for anomaly in report["anomalies"]:  # type: ignore[attr-defined]
        print(f"  ✗ {anomaly['code']} {anomaly['product_ids']}: {anomaly['detail']}")
    if previous is None:
        print("  no current catalogue: first build, nothing to compare with")
    else:
        print(f"  diff vs current catalogue: {report['diff']}")
    print(f"  report: {report_path.relative_to(ROOT) if report_path.is_relative_to(ROOT) else report_path}")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
