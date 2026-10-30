"""Secrets in the repository that are not in the reviewed baseline (goal G-SECRETS)."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / ".secrets.baseline"
REPORT = ROOT / "evals" / "reports" / "secrets-latest.json"

listed = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
tracked = [f for f in listed.stdout.split() if f != BASELINE.name]  # the baseline holds hashes by design
scan = subprocess.run(
    ["detect-secrets", "scan", *tracked], cwd=ROOT, capture_output=True, text=True, check=True
)
found = {(f, r["hashed_secret"]) for f, rs in json.loads(scan.stdout)["results"].items() for r in rs}
known = {(f, r["hashed_secret"]) for f, rs in json.loads(BASELINE.read_text())["results"].items() for r in rs}
new = sorted(found - known)
REPORT.write_text(json.dumps({"new_findings": len(new), "detail": [f for f, _ in new]}, indent=2) + "\n")
print(f"secrets: {len(new)} new findings outside the baseline" + "".join(f"\n  ✗ {f}" for f, _ in new))
sys.exit(1 if new else 0)
