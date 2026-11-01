"""Definition of done for a phase: every goal that blocks it, read from its artifact.

For phase n the goals checked are the core goals with blocking_from_phase <= n, plus the extension
goals from phase 3 on (they are reported, as GOALS.yaml says they never block a core phase, but a
red extension still fails `make done F=3`). Each goal's artifact ("path :: key", the key dotted when
nested) is read and compared with its threshold. Nothing is measured here: the numbers come from
each goal's own command, which is printed when its artifact or key is missing.

docs/thresholds.lock must hold the sha256 of docs/GOALS.yaml; otherwise the thresholds are not the
sealed ones and the check fails.

Exit code 1 when any row is FAIL or MISSING.

    uv run python scripts/done.py <phase>
"""

import hashlib
import json
import operator
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXTENSION_PHASE = 3
OPS: dict[str, Callable[[float, float], bool]] = {
    "==": operator.eq,
    "<=": operator.le,
    ">=": operator.ge,
    "<": operator.lt,
    ">": operator.gt,
}


@dataclass(frozen=True)
class Row:
    goal: str
    value: str
    threshold: str
    status: str  # PASS | FAIL | MISSING
    command: str = ""


def goals_for_phase(goals: list[dict[str, Any]], phase: int) -> list[dict[str, Any]]:
    def blocks(g: dict[str, Any]) -> bool:
        if g["kind"] == "extension":
            return phase >= EXTENSION_PHASE
        return g["blocking_from_phase"] is not None and g["blocking_from_phase"] <= phase

    return [g for g in goals if blocks(g)]


def read_artifact(root: Path, artifact: str) -> Any:
    """The value at "path :: key" (key dotted when nested); KeyError when the file or key is absent."""
    path, _, key = (part.strip() for part in artifact.partition("::"))
    file = root / path
    if not file.is_file():
        raise KeyError(path)
    value: Any = json.loads(file.read_text())
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(key)
        value = value[part]
    return value


def compare(value: Any, threshold: dict[str, Any]) -> bool:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"not a number: {value!r}")
    return OPS[threshold["op"]](value, threshold["value"])


def check_goal(root: Path, goal: dict[str, Any]) -> Row:
    t = goal["threshold"]
    shown = f"{t['op']} {t['value']} {t.get('unit', '')}".strip()
    try:
        value = read_artifact(root, goal["artifact"])
    except KeyError:
        return Row(goal["id"], "-", shown, "MISSING", goal["command"])
    if value is None:
        return Row(goal["id"], "null", shown, "MISSING", goal["command"])
    try:
        ok = compare(value, t)
    except TypeError:
        return Row(goal["id"], repr(value), shown, "FAIL")
    return Row(goal["id"], str(value), shown, "PASS" if ok else "FAIL")


def check_lock(goals_path: Path, lock_path: Path) -> Row:
    """The lock is `sha256sum` output: "<hex>  <path>"."""
    actual = hashlib.sha256(goals_path.read_bytes()).hexdigest()
    sealed = lock_path.read_text().split()[0] if lock_path.is_file() else ""
    status = "PASS" if sealed == actual else "FAIL"
    return Row("thresholds.lock", actual[:12], f"== {sealed[:12] or '(no lock)'}", status)


def table(rows: list[Row]) -> str:
    head = ("goal", "value", "threshold", "status")
    cells = [head, *((r.goal, r.value, r.threshold, r.status) for r in rows)]
    widths = [max(len(c[i]) for c in cells) for i in range(len(head))]
    lines = ["  ".join(c.ljust(w) for c, w in zip(cell, widths, strict=True)).rstrip() for cell in cells]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def run(root: Path, phase: int) -> tuple[list[Row], bool]:
    goals_path, lock_path = root / "docs" / "GOALS.yaml", root / "docs" / "thresholds.lock"
    goals = yaml.safe_load(goals_path.read_text())["goals"]
    rows = [check_lock(goals_path, lock_path), *(check_goal(root, g) for g in goals_for_phase(goals, phase))]
    return rows, all(r.status == "PASS" for r in rows)


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not argv[0].isdigit():
        print("usage: done.py <phase>   (make done F=<phase>)", file=sys.stderr)
        return 2
    phase = int(argv[0])
    rows, ok = run(ROOT, phase)
    print(f"Definition of done, phase {phase}\n")
    print(table(rows))
    missing = [r for r in rows if r.status == "MISSING"]
    if missing:
        print("\nTo produce the missing artifacts:")
        for r in missing:
            print(f"  {r.goal}: {r.command}")
    print(f"\n{'DONE' if ok else 'NOT DONE'}: {sum(r.status == 'PASS' for r in rows)}/{len(rows)} pass")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
