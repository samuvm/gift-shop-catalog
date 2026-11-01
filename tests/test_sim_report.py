"""Simulation results recorded by hand: strict validation and the pooled latest set."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("sim_report", ROOT / "evals" / "simulations" / "report.py")
assert _spec and _spec.loader
report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(report)

SCENARIOS = {"core-1": "core", "core-2": "core", "extra-7": "extra"}
HEADER = "run,date,model,prompt_version,suite,scenario,judge,after_reading,note\n"


def write(tmp_path: Path, *lines: str) -> Path:
    path = tmp_path / "results.csv"
    path.write_text(HEADER + "".join(f"{line}\n" for line in lines))
    return path


def core_run(run: str, when: str, version: str, second: str = "pass,pass,") -> list[str]:
    head = f"{run},2026-11-01T{when},m,{version},core"
    return [f"{head},core-1,pass,pass,", f"{head},core-2,{second}"]


def test_the_recorded_results_are_valid() -> None:
    scenarios = report.load_scenarios(report.SCENARIOS)
    assert report.load_results(report.RESULTS, scenarios)


@pytest.mark.parametrize(
    ("line", "error"),
    [
        ("r1,2026-11-01T10:00,m,v1,nope,core-1,pass,pass,", "unknown suite"),
        ("r1,2026-11-01T10:00,m,v1,core,extra-7,pass,pass,", "not in suite"),
        ("r1,2026-11-01T10:00,m,v1,core,core-1,ok,pass,", "pass or fail"),
        ("r1,2026-11-01T10:00,m,v1,core,core-1,fail,pass,", "needs a note"),
        ("r1,yesterday,m,v1,core,core-1,pass,pass,", "ISO"),
    ],
)
def test_bad_rows_are_rejected(tmp_path: Path, line: str, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        report.load_results(write(tmp_path, line), SCENARIOS)


def test_a_run_must_cover_its_suite_exactly_once(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exactly once"):
        report.load_results(write(tmp_path, core_run("r1", "10:00", "v1")[0]), SCENARIOS)


def test_latest_pools_every_run_of_the_last_configuration(tmp_path: Path) -> None:
    lines = [
        *core_run("r1", "09:00", "v1", "fail,fail,old prompt"),
        *core_run("r2", "10:00", "v2", "fail,pass,judge only"),
        *core_run("r3", "11:00", "v2", "fail,fail,real fail"),
    ]
    rows = report.load_results(write(tmp_path, *lines), SCENARIOS)
    out = report.summarise(rows, ["core", "extra"])
    assert (out["runs"], out["n"], out["core_pass_rate"], out["core_judge_pass_rate"]) == (
        ["r2", "r3"],
        4,
        0.75,
        0.5,
    )
    assert [(f["run"], f["after_reading"]) for f in out["fails"]] == [("r2", "pass"), ("r3", "fail")]
    assert out["suites"]["extra"]["n"] == 0
