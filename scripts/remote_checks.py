"""Checks against the deployed service, from the client machine. Stdlib only.

    latency URL   p95 of list and search calls over several runs (G-LATENCY-P95)
    public  URL   spec reachable, 401 without or with a wrong key, 200 with the key, HTTPS,
                  the shop's landing page public, and the agent's test page up (G-PUBLIC-CHECK)

The key comes from CATALOG_API_KEY and the test page from TEST_PAGE_URL, both in the
environment (a local .env, never the repository).
"""

import http.client
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPORTS = Path(__file__).resolve().parents[1] / "evals" / "reports"
LATENCY_CALLS = {
    "browse": "/categories/kitchen-dining/products?max_price=100",
    "search": "/products/search?query=chef%20knife&max_price=100",
}
RUNS, WARMUP, CALLS_PER_RUN = 3, 20, 200  # the latency protocol in docs/GOALS.yaml


def get(url: str, key: str | None = None) -> tuple[int, bytes]:
    if not url.startswith(("https://", "http://")):
        raise SystemExit(f"not an http(s) URL: {url!r}")
    headers = {"X-API-Key": key} if key is not None else {}
    request = urllib.request.Request(url, headers=headers)  # noqa: S310 (scheme checked above)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            return response.status, response.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def latency(base: str, key: str) -> dict[str, Any]:
    # Decided (option A, 2 Nov): one connection reused for the warm-up and every call, because the
    # sealed protocol's warm-up only means something if the connection survives it, and a
    # server-to-server client such as the platform keeps its connection open. Opening a new TCP and
    # TLS connection per call measured the network handshake (~115 ms of ~170 ms), not the service.
    parts = urllib.parse.urlsplit(base)
    if parts.scheme != "https":
        raise SystemExit(f"latency needs an https URL: {base!r}")
    conn = http.client.HTTPSConnection(parts.netloc, timeout=10)
    headers = {"X-API-Key": key}

    def timed(path: str) -> float:
        start = time.perf_counter()
        conn.request("GET", parts.path.rstrip("/") + path, headers=headers)
        response = conn.getresponse()
        response.read()
        if response.status != 200:
            raise SystemExit(f"{path}: HTTP {response.status}")
        return (time.perf_counter() - start) * 1000

    for _ in range(WARMUP):  # discarded
        timed(LATENCY_CALLS["search"])
    runs = []
    for _ in range(RUNS):
        run: dict[str, float] = {}
        for name, path in LATENCY_CALLS.items():
            times = sorted(timed(path) for _ in range(CALLS_PER_RUN))
            run[f"{name}_p50_ms"] = round(statistics.median(times), 1)
            run[f"{name}_p95_ms"] = round(times[int(len(times) * 0.95) - 1], 1)
        runs.append(run)
    conn.close()
    worst = max(v for run in runs for k, v in run.items() if k.endswith("p95_ms"))
    return {
        "base_url": base,
        "runs": runs,
        "connection": "reused",
        "warmup_calls": WARMUP,
        "calls_per_run": CALLS_PER_RUN,
        "p95_ms_max_of_runs": worst,
    }


def public(base: str, key: str, test_page: str | None) -> dict[str, Any]:
    checks: dict[str, bool] = {"https": base.startswith("https://")}
    status, body = get(base + "/openapi.json")
    checks["spec_reachable_without_key"] = status == 200 and "paths" in json.loads(body or b"{}")
    checks["401_without_key"] = get(base + "/categories")[0] == 401
    checks["401_with_wrong_key"] = get(base + "/categories", "wrong-key")[0] == 401
    checks["200_with_key"] = get(base + "/categories", key)[0] == 200
    checks["landing_page_without_key"] = get(base + "/")[0] == 200
    checks["test_page_up"] = bool(test_page) and get(test_page or "")[0] == 200
    return {"base_url": base, "checks": checks, "pass_rate": round(sum(checks.values()) / len(checks), 3)}


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in ("latency", "public"):
        raise SystemExit("usage: remote_checks.py latency|public <base url>")
    mode, base = sys.argv[1], sys.argv[2].rstrip("/")
    key = os.environ.get("CATALOG_API_KEY")
    if not key:
        raise SystemExit("CATALOG_API_KEY is not set")
    report = latency(base, key) if mode == "latency" else public(base, key, os.environ.get("TEST_PAGE_URL"))
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"{mode}-latest.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary = report["p95_ms_max_of_runs"] if mode == "latency" else report["checks"]
    print(f"{mode}: {summary} -> {out.relative_to(REPORTS.parents[1])}")


if __name__ == "__main__":
    main()
