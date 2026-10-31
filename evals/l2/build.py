"""Merge the labelled drafts into the level-2 set, validate every case, and write the review sheet.

    uv run python evals/l2/build.py

Cases are drafted from the 100 development conversations (one draft file per direction) and
reviewed by a person in REVIEW.md. A case that names a tool, an argument, a category or a product
that does not exist is an error here, not a silent miss in the evaluation.
"""

import json
from pathlib import Path
from typing import Any

from catalog.tools import SLUGS, TOOLS

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PARAMS = {t.name: {p.name for p in t.params} for t in TOOLS}
MATCHERS = {"eq", "between", "any_of", "words", "absent"}
KINDS = {"positive", "negative", "clarify"}


def check(case: dict[str, Any], ids: set[str]) -> list[str]:
    problems = []
    if case.get("kind") not in KINDS:
        problems.append(f"kind {case.get('kind')!r}")
    expect = case.get("expect") or {}
    tools = [expect.get("tool"), *expect.get("accept_tools", [])]
    for tool in tools:
        if tool is not None and tool not in PARAMS:
            problems.append(f"tool {tool!r}")
    if case.get("kind") == "negative" and any(t is not None for t in tools):
        problems.append("a negative case accepts a tool call")
    allowed = set().union(*(PARAMS.get(t, set()) for t in tools if t))
    for name, rule in (expect.get("args") or {}).items():
        if name not in allowed:
            problems.append(f"argument {name!r} is not a parameter of {tools}")
        if not isinstance(rule, dict) or len(rule) != 1 or not set(rule) <= MATCHERS:
            problems.append(f"matcher for {name!r}: {rule}")
        if name == "category" and "eq" in rule and rule["eq"] not in SLUGS:
            problems.append(f"category {rule['eq']!r}")
        if name == "product_id" and "eq" in rule and rule["eq"] not in ids:
            problems.append(f"product {rule['eq']!r}")
    for turn in case.get("history", []):
        if turn.get("role") not in ("user", "assistant") or not turn.get("content"):
            problems.append("history turn without role or content")
    if not case.get("message"):
        problems.append("no message")
    return problems


def main() -> None:
    catalog = json.loads((ROOT / "data" / "build" / "catalog.json").read_text(encoding="utf-8"))
    ids = {p["product_id"] for p in catalog["products"]}
    drafts = sorted((HERE / "drafts").glob("*.jsonl"))
    cases, errors = [], []
    for path in drafts:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            case = json.loads(line)
            for problem in check(case, ids):
                errors.append(f"{path.name}:{n} ({case.get('source')}): {problem}")
            cases.append(case)
    if errors:
        raise SystemExit("invalid cases:\n  " + "\n  ".join(errors))
    lines, review = [], ["# Level-2 set · review sheet", ""]
    review += [
        "For each case: given the conversation, is the expected first move what a good shop assistant",
        "would do with these tools? Mark `ok`, or write what is wrong. The arguments listed are the only",
        "ones checked; anything else the model adds is ignored.",
        "",
    ]
    for n, case in enumerate(cases, 1):
        case = {"id": f"l2-{n:03d}", **case}
        lines.append(json.dumps(case, ensure_ascii=False))
        expect = case["expect"]
        accepted = " or ".join(str(t) for t in [expect["tool"], *expect.get("accept_tools", [])])
        review += [f"## {case['id']} · {case['kind']} · {case['source']} ({case['language']})", ""]
        for turn in case["history"][-4:]:
            review.append(f"> *{turn['role']}:* {turn['content']}")
        review += [f"> **user:** {case['message']}", "", f"- **expected:** `{accepted}`"]
        for name, rule in expect.get("args", {}).items():
            review.append(f"  - `{name}` {json.dumps(rule, ensure_ascii=False)}")
        review += [f"- *why:* {case['why']}", "", "Review: ", ""]
    (HERE / "cases.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (HERE / "REVIEW.md").write_text("\n".join(review), encoding="utf-8")
    kinds = {k: sum(c["kind"] == k for c in cases) for k in sorted(KINDS)}
    print(f"{len(cases)} cases from {len(drafts)} drafts -> cases.jsonl, REVIEW.md · {kinds}")


if __name__ == "__main__":
    main()
