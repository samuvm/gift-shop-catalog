"""Line coverage over the packages under mandatory TDD (goal G-COVERAGE), from coverage's JSON."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "evals" / "reports" / "coverage-raw.json"
REPORT = ROOT / "evals" / "reports" / "coverage-latest.json"
TDD_REQUIRED = ("src/catalog/domain/", "src/catalog/ingest/")

files = json.loads(RAW.read_text())["files"]
picked = {f: v["summary"] for f, v in files.items() if f.startswith(TDD_REQUIRED)}
statements = sum(s["num_statements"] for s in picked.values())
covered = sum(s["covered_lines"] for s in picked.values())
percent = round(100 * covered / statements, 2)
REPORT.write_text(
    json.dumps(
        {"line_percent": percent, "statements": statements, "covered": covered, "files": sorted(picked)},
        indent=2,
    )
    + "\n"
)
print(f"coverage over domain + ingest: {percent}% ({covered}/{statements} lines)")
sys.exit(0)
