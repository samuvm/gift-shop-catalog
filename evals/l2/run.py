"""Level 2: from a shopper's message to the right tool and arguments, with a real model.

The tools are built from the served OpenAPI document, the way the platform builds them, and the
system prompt is agent/system-prompt.md. Each case gives the conversation so far and the latest
message; the model's FIRST move is scored: which tool (or none), and whether the key arguments
match. Model: Gemma 4 26B on a local Ollama (gemma4:26b, the GGUF build; the platform offers
gemma-4-26b), temperature 0, no reasoning, fixed seed. --model gemma4:12b runs a smaller model
for comparison; its report goes to its own file.

Every model response is recorded under evals/l2/recordings/, keyed by model, prompt and tools.
Without --refresh the recording is replayed, so the published numbers can be re-scored offline
(G-L2-REPRODUCIBLE). A changed prompt or tool description gets a new recording.

    uv run python evals/l2/run.py [--refresh] [--cases evals/l2/cases.jsonl]

Case schema (one JSON object per line):
    id, source, language, kind (positive | negative | clarify), history [{role, content}],
    message, expect {tool | null, accept_tools [..], args {name: matcher}}, why
Matchers: {"eq": v} · {"between": [lo, hi]} · {"any_of": [..]} · {"words": [[..], [..]]}
(at least one word of each group, case-insensitive substring) · {"absent": true}.
Only the matchers for parameters of the tool actually called are checked.
"""

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from catalog.api.app import create_app
from catalog.tools import TOOLS

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PROMPT = ROOT / "agent" / "system-prompt.md"
REPORT = ROOT / "evals" / "reports" / "l2-latest.json"
PARAMS = {t.name: {p.name for p in t.params} for t in TOOLS}
MODEL = "gemma4:26b"  # the gate model (GOALS); --model runs another for comparison
OLLAMA = "http://localhost:11434/api/chat"
TODAY = "2026-10-31"  # {{$date}}: YYYY-MM-DD in the workspace timezone
SEED = 20261029


def tools_from_spec() -> list[dict[str, Any]]:
    """One function per operation: operationId, description, and the parameters as its arguments."""
    spec = TestClient(create_app("l2-eval")).get("/openapi.json").json()
    tools = []
    for ops in spec["paths"].values():
        op = ops["get"]
        properties = {p["name"]: {**p["schema"], "description": p["description"]} for p in op["parameters"]}
        required = [p["name"] for p in op["parameters"] if p["required"]]
        parameters = {"type": "object", "properties": properties, "required": required}
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": op["operationId"],
                    "description": op["description"],
                    "parameters": parameters,
                },
            }
        )
    return tools


ROUTING_ONLY = ("Trigger details", "Example questions")


def system_prompt(path: Path = PROMPT) -> str:
    """The Agent Block fields below the first horizontal rule, joined in order, without the fields
    that only route messages to the agent, and with the date the platform fills in. A prompt
    without {{$date}} (v1, v2) gets the date appended, as those versions were measured."""
    body = path.read_text(encoding="utf-8").split("\n---\n", 1)[1].strip()
    chunks = body.split("\n## ")
    kept = [chunks[0], *(f"## {c}" for c in chunks[1:])]
    text = "\n\n".join(
        c.strip() for c in kept if c.strip() and not c.removeprefix("## ").startswith(ROUTING_ONLY)
    )
    return text.replace("{{$date}}", TODAY) if "{{$date}}" in text else f"{text}\n\nToday is {TODAY}."


def sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:8]


def ask(model: str, messages: list[dict[str, str]], tools: list[dict[str, Any]]) -> dict[str, Any]:
    body = {
        "model": model,
        "stream": False,
        "think": False,
        # Only the first move is scored; the cap stops a model that runs on without ending.
        "options": {"temperature": 0, "seed": SEED, "num_predict": 512},
        "tools": tools,
        "messages": messages,
    }
    request = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:  # noqa: S310 (fixed local URL)
        message: dict[str, Any] = json.load(response)["message"]
    return message


def first_call(message: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    calls = message.get("tool_calls") or []
    if not calls:
        return None, {}
    fn = calls[0]["function"]
    args = fn.get("arguments") or {}
    return fn["name"], json.loads(args) if isinstance(args, str) else args


def matches(value: Any, rule: dict[str, Any]) -> bool:
    if "absent" in rule:
        return value is None
    if value is None:
        return False
    if "eq" in rule:
        return (
            str(value).strip().lower() == str(rule["eq"]).lower()
            if isinstance(rule["eq"], str)
            else value == rule["eq"]
        )
    if "between" in rule:
        lo, hi = rule["between"]
        return isinstance(value, int | float) and lo <= value <= hi
    if "any_of" in rule:
        normal = ",".join(v.strip() for v in str(value).lower().split(","))
        return normal in [str(v).lower() for v in rule["any_of"]]
    if "words" in rule:
        text = str(value).lower()
        return all(any(w.lower() in text for w in group) for group in rule["words"])
    raise ValueError(f"unknown matcher {rule}")


def score(case: dict[str, Any], message: dict[str, Any]) -> dict[str, Any]:
    tool, args = first_call(message)
    expect = case["expect"]
    accepted = [expect["tool"], *expect.get("accept_tools", [])]
    tool_ok = tool in accepted
    # Only the arguments the called tool has: a case that accepts two tools lists the arguments of
    # either, and the other tool cannot be failed for lacking them.
    rules = {k: r for k, r in expect.get("args", {}).items() if k in PARAMS.get(tool or "", set())}
    wrong = [k for k, rule in rules.items() if not matches(args.get(k), rule)]
    return {
        "id": case["id"],
        "kind": case["kind"],
        "tool": tool,
        "args": args,
        "tool_ok": tool_ok,
        "args_ok": tool_ok and tool is not None and not wrong,
        "wrong_args": wrong if tool_ok and tool is not None else [],
        "text": (message.get("content") or "")[:200],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="call the model instead of replaying")
    parser.add_argument("--cases", default=str(HERE / "cases.jsonl"))
    parser.add_argument(
        "--model", default=MODEL, help=f"Ollama model (default {MODEL}, the one the goals use)"
    )
    parser.add_argument("--prompt", default=str(PROMPT), help="prompt file (default: the current one)")
    opts = parser.parse_args()
    model = opts.model
    cases = [json.loads(line) for line in Path(opts.cases).read_text(encoding="utf-8").splitlines() if line]
    tools, prompt = tools_from_spec(), system_prompt(Path(opts.prompt))
    key = f"{model.replace(':', '-')}__prompt-{sha(prompt)}__tools-{sha(tools)}"
    path = HERE / "recordings" / f"{key}.jsonl"
    recorded = {}
    if path.exists():
        recorded = {
            r["id"]: r["message"] for r in map(json.loads, path.read_text(encoding="utf-8").splitlines())
        }
    missing = [c for c in cases if c["id"] not in recorded]
    if missing and not opts.refresh:
        print(f"{len(missing)} cases have no recording for {key}; run with --refresh (needs Ollama).")
        return 2
    start = time.perf_counter()
    for n, case in enumerate(missing, 1):
        messages = [
            {"role": "system", "content": prompt},
            *case["history"],
            {"role": "user", "content": case["message"]},
        ]
        recorded[case["id"]] = ask(model, messages, tools)
        print(f"\r  model calls {n}/{len(missing)}", end="", file=sys.stderr)
    if missing:
        print(file=sys.stderr)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps({"id": c["id"], "message": recorded[c["id"]]}, ensure_ascii=False) for c in cases]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    results = [score(c, recorded[c["id"]]) for c in cases]
    # Replay: re-score from the file on disk and compare (G-L2-REPRODUCIBLE).
    on_disk = {r["id"]: r["message"] for r in map(json.loads, path.read_text(encoding="utf-8").splitlines())}
    replay_mismatches = sum(1 for c, r in zip(cases, results, strict=True) if score(c, on_disk[c["id"]]) != r)
    called = [r for r in results if r["tool_ok"] and r["tool"] is not None]
    negatives = [r for r in results if r["kind"] == "negative"]
    report = {
        "model": model,
        "recording": str(path.relative_to(ROOT)),
        "n": len(results),
        "n_negative": len(negatives),
        "tool_accuracy": round(sum(r["tool_ok"] for r in results) / len(results), 4),
        "args_accuracy": round(sum(r["args_ok"] for r in called) / max(len(called), 1), 4),
        "negative_false_call_rate": round(
            sum(r["tool"] is not None for r in negatives) / max(len(negatives), 1), 4
        ),
        "replay_mismatches": replay_mismatches,
        "seconds_calling_model": round(time.perf_counter() - start, 1) if missing else 0,
        "failures": [r for r in results if not r["tool_ok"] or (r["tool"] is not None and not r["args_ok"])],
    }
    report_path = REPORT if model == MODEL else REPORT.with_name(f"l2-{model.replace(':', '-')}-latest.json")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"level 2 ({model}): tool {report['tool_accuracy']:.1%} · args {report['args_accuracy']:.1%} · "
        f"negatives calling a tool {report['negative_false_call_rate']:.1%} (n={report['n']}, "
        f"{report['n_negative']} negative) · replay mismatches {replay_mismatches} "
        f"-> {report_path.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
