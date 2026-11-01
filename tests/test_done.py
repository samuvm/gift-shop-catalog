"""`make done`: artifact lookup, threshold comparison, phase selection and the lock check."""

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("done", ROOT / "scripts" / "done.py")
assert _spec and _spec.loader
done = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(done)


def goal(
    gid: str, artifact: str, op: str, value: float, phase: int | None = 1, kind: str = "core"
) -> dict[str, Any]:
    return {
        "id": gid,
        "threshold": {"op": op, "value": value, "unit": "ratio"},
        "command": f"make {gid.lower()}",
        "artifact": artifact,
        "blocking_from_phase": phase,
        "kind": kind,
    }


@pytest.fixture
def reports(tmp_path: Path) -> Path:
    (tmp_path / "evals" / "reports").mkdir(parents=True)
    (tmp_path / "evals" / "reports" / "x.json").write_text(
        json.dumps({"rate": 0.9, "count": 0, "nested": {"p95": 250}, "flag": True})
    )
    return tmp_path


def test_reads_top_level_and_nested_keys(reports: Path) -> None:
    assert done.read_artifact(reports, "evals/reports/x.json :: rate") == 0.9
    assert done.read_artifact(reports, "evals/reports/x.json :: nested.p95") == 250


@pytest.mark.parametrize("artifact", ["evals/reports/absent.json :: rate", "evals/reports/x.json :: nope"])
def test_absent_file_or_key_is_missing(reports: Path, artifact: str) -> None:
    row = done.check_goal(reports, goal("G-X", artifact, "==", 1.0))
    assert (row.status, row.command) == ("MISSING", "make g-x")


@pytest.mark.parametrize(
    ("op", "threshold", "status"),
    [
        (">=", 0.9, "PASS"),
        (">=", 0.91, "FAIL"),
        ("<=", 0.9, "PASS"),
        ("<=", 0.89, "FAIL"),
        ("==", 0.9, "PASS"),
        ("==", 1.0, "FAIL"),
        ("<", 0.9, "FAIL"),
        (">", 0.8, "PASS"),
    ],
)
def test_compares_with_the_threshold(reports: Path, op: str, threshold: float, status: str) -> None:
    assert (
        done.check_goal(reports, goal("G-X", "evals/reports/x.json :: rate", op, threshold)).status == status
    )


def test_a_non_number_fails(reports: Path) -> None:
    assert done.check_goal(reports, goal("G-X", "evals/reports/x.json :: flag", "==", 1)).status == "FAIL"


def test_phase_selects_core_goals_up_to_it_and_extensions_from_three() -> None:
    goals = [goal("A", "", "==", 1, 1), goal("B", "", "==", 1, 2), goal("E", "", "==", 1, None, "extension")]
    ids = {p: [g["id"] for g in done.goals_for_phase(goals, p)] for p in (1, 2, 3)}
    assert ids == {1: ["A"], 2: ["A", "B"], 3: ["A", "B", "E"]}


def test_lock_must_match_the_goals_file(tmp_path: Path) -> None:
    goals, lock = tmp_path / "GOALS.yaml", tmp_path / "thresholds.lock"
    goals.write_text("goals: []\n")
    lock.write_text(f"{hashlib.sha256(goals.read_bytes()).hexdigest()}  docs/GOALS.yaml\n")
    assert done.check_lock(goals, lock).status == "PASS"
    goals.write_text("goals: [changed]\n")
    assert done.check_lock(goals, lock).status == "FAIL"
    lock.unlink()
    assert done.check_lock(goals, lock).status == "FAIL"


def test_run_is_done_only_when_every_row_passes(reports: Path) -> None:
    docs = reports / "docs"
    docs.mkdir()
    rows = [goal("G-OK", "evals/reports/x.json :: count", "==", 0)]
    (docs / "GOALS.yaml").write_text(json.dumps({"goals": rows}))
    (docs / "thresholds.lock").write_text(hashlib.sha256((docs / "GOALS.yaml").read_bytes()).hexdigest())
    assert done.run(reports, 1)[1] is True
    rows.append(goal("G-GONE", "evals/reports/gone.json :: x", "==", 0))
    (docs / "GOALS.yaml").write_text(json.dumps({"goals": rows}))
    (docs / "thresholds.lock").write_text(hashlib.sha256((docs / "GOALS.yaml").read_bytes()).hexdigest())
    result, ok = done.run(reports, 1)
    assert not ok
    assert [r.status for r in result] == ["PASS", "PASS", "MISSING"]


def test_every_repository_goal_has_a_known_operator_and_a_keyed_artifact() -> None:
    goals = done.yaml.safe_load((ROOT / "docs" / "GOALS.yaml").read_text())["goals"]
    assert all(g["threshold"]["op"] in done.OPS and "::" in g["artifact"] for g in goals)
