"""Level 3: the platform's Simulations, summarised from the verdicts recorded by hand (goal G-SIM-CORE).

The platform has no export of Simulation results we can rely on, so every scenario of every run is
recorded in evals/simulations/results.csv, one row each:

    run, date, model, prompt_version, suite, scenario, judge, after_reading, note

- run: an id shared by the rows of one run (one suite, run once); date: ISO, e.g. 2026-11-01T18:59.
- prompt_version labels the agent configuration under test: the system prompt, the tool descriptions
  and the service behind them. Bump it when any of them changes, so runs of different
  configurations are never pooled.
- scenario: the short name of a scenario in scenarios.csv ("core-1" for "core-1 vague shopper").
- judge: the platform judge's verdict. after_reading: the verdict after reading the transcript
  against the catalogue, which is the one the goal counts. Both are pass | fail.
- note: why a verdict is fail, or why the two verdicts disagree.

Decided: the reported set for a suite is every run of that suite with the most recent run's model
and prompt_version, pooled, because counting only the last run would let a failing configuration
turn green by being re-run until one run passes.

The CSV is validated strictly; any unknown suite, scenario or verdict, a run that does not cover its
suite exactly once, or a run whose rows disagree on date, model or prompt_version is an error.

    uv run python evals/simulations/report.py
"""

import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results.csv"
SCENARIOS = HERE / "scenarios.csv"
REPORT = ROOT / "evals" / "reports" / "simulations-latest.json"
COLUMNS = ["run", "date", "model", "prompt_version", "suite", "scenario", "judge", "after_reading", "note"]
VERDICTS = {"pass", "fail"}
CORE = "core"


@dataclass(frozen=True)
class Row:
    run: str
    date: datetime
    model: str
    prompt_version: str
    suite: str
    scenario: str
    judge: bool
    after_reading: bool
    note: str


def load_scenarios(path: Path) -> dict[str, str]:
    """Short scenario name -> suite, from scenarios.csv."""
    with path.open(newline="") as f:
        return {r["name"].split()[0]: r["suite"] for r in csv.DictReader(f)}


def load_results(path: Path, scenarios: dict[str, str]) -> list[Row]:
    """Parse and validate results.csv; raise ValueError naming the line on the first problem."""
    rows: list[Row] = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"{path.name}: columns must be {COLUMNS}, got {reader.fieldnames}")
        for line, r in enumerate(reader, start=2):
            where = f"{path.name}:{line}"
            if any(r[c] in (None, "") for c in COLUMNS if c != "note"):
                raise ValueError(f"{where}: empty field")
            if r["suite"] not in set(scenarios.values()):
                raise ValueError(f"{where}: unknown suite {r['suite']!r}")
            if scenarios.get(r["scenario"]) != r["suite"]:
                raise ValueError(f"{where}: scenario {r['scenario']!r} is not in suite {r['suite']!r}")
            for c in ("judge", "after_reading"):
                if r[c] not in VERDICTS:
                    raise ValueError(f"{where}: {c} must be pass or fail, got {r[c]!r}")
            if "fail" in (r["judge"], r["after_reading"]) and not r["note"]:
                raise ValueError(f"{where}: a fail needs a note")
            try:
                when = datetime.fromisoformat(r["date"])
            except ValueError:
                raise ValueError(f"{where}: date must be ISO, got {r['date']!r}") from None
            verdicts = {c: r[c] == "pass" for c in ("judge", "after_reading")}
            header = {c: r[c] for c in ("run", "model", "prompt_version", "suite", "scenario", "note")}
            rows.append(Row(date=when, **header, **verdicts))
    check_runs(rows, scenarios)
    return rows


def check_runs(rows: list[Row], scenarios: dict[str, str]) -> None:
    """Each run is one suite, run once: same header on every row, every scenario exactly once."""
    for run in sorted({r.run for r in rows}):
        mine = [r for r in rows if r.run == run]
        if len({(r.date, r.model, r.prompt_version, r.suite) for r in mine}) != 1:
            raise ValueError(f"run {run}: rows disagree on date, model, prompt_version or suite")
        expected = sorted(s for s, suite in scenarios.items() if suite == mine[0].suite)
        got = sorted(r.scenario for r in mine)
        if got != expected:
            raise ValueError(f"run {run}: must cover {expected} exactly once, got {got}")


def latest_set(rows: list[Row], suite: str) -> list[Row]:
    """Every run of the suite with the model and prompt_version of its most recent run."""
    mine = [r for r in rows if r.suite == suite]
    if not mine:
        return []
    last = max(mine, key=lambda r: r.date)
    return [r for r in mine if (r.model, r.prompt_version) == (last.model, last.prompt_version)]


def rate(hits: int, n: int) -> float | None:
    return round(hits / n, 4) if n else None


def summarise_suite(picked: list[Row]) -> dict[str, Any]:
    n = len(picked)
    return {
        "model": picked[0].model if picked else None,
        "prompt_version": picked[0].prompt_version if picked else None,
        "runs": sorted({r.run for r in picked}),
        "n": n,
        "pass_rate": rate(sum(r.after_reading for r in picked), n),
        "judge_pass_rate": rate(sum(r.judge for r in picked), n),
        "fails": [
            {
                "run": r.run,
                "scenario": r.scenario,
                "judge": "pass" if r.judge else "fail",
                "after_reading": "pass" if r.after_reading else "fail",
                "note": r.note,
            }
            for r in sorted(picked, key=lambda r: (r.date, r.scenario))
            if not (r.judge and r.after_reading)
        ],
    }


def summarise(rows: list[Row], suites: list[str]) -> dict[str, Any]:
    per_suite = {s: summarise_suite(latest_set(rows, s)) for s in suites}
    core = per_suite[CORE]
    return {
        "source": "evals/simulations/results.csv",
        "core_pass_rate": core["pass_rate"],
        "core_judge_pass_rate": core["judge_pass_rate"],
        "n": core["n"],
        "model": core["model"],
        "prompt_version": core["prompt_version"],
        "runs": core["runs"],
        "fails": core["fails"],
        "suites": per_suite,
    }


def main() -> int:
    scenarios = load_scenarios(SCENARIOS)
    try:
        rows = load_results(RESULTS, scenarios)
    except ValueError as e:
        print(f"invalid results: {e}", file=sys.stderr)
        return 1
    suites = list(dict.fromkeys(scenarios.values()))  # the order of scenarios.csv
    report = summarise(rows, suites)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    for suite, s in report["suites"].items():
        print(
            f"{suite:<9} {s['model']} {s['prompt_version']} runs {','.join(s['runs'])}: "
            f"after reading {s['pass_rate']} · judge {s['judge_pass_rate']} (n={s['n']})"
        )
    for f in report["fails"]:
        print(f"  core fail {f['run']} {f['scenario']} judge={f['judge']} after_reading={f['after_reading']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
