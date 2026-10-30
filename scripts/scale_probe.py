"""How the in-memory catalogue scales: build time, peak memory and search latency (ADR-004).

Runs on the served catalogue and on a synthetic copy repeated `--factor` times with fresh IDs.
In-process only; network latency is measured separately against the deployed service.

    uv run python scripts/scale_probe.py [--factor 100]
"""

import argparse
import statistics
import time
import tracemalloc
from pathlib import Path

from catalog.domain.catalog import Catalog, Filters
from catalog.domain.models import Product
from catalog.domain.text import Vocabulary
from catalog.storage import read_catalog, read_vocabulary

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ["chef knife", "candle", "headphones", "gift for her", "board game", "tea", "wallet", "yoga"]


def probe(products: list[Product], vocabulary: Vocabulary, label: str, reps: int) -> None:
    tracemalloc.start()
    start = time.perf_counter()
    catalog = Catalog(products, vocabulary)
    build_ms = (time.perf_counter() - start) * 1000
    peak_mb = tracemalloc.get_traced_memory()[1] / 1e6
    tracemalloc.stop()
    times = []
    for _ in range(reps):
        for q in QUERIES:
            start = time.perf_counter()
            catalog.search(q, Filters(max_price=100), None, limit=5, offset=0)
            times.append((time.perf_counter() - start) * 1000)
    times.sort()
    p95 = times[int(len(times) * 0.95)]
    print(
        f"{label}: products={len(products)} build={build_ms:.0f}ms peak_mem={peak_mb:.1f}MB "
        f"search_p50={statistics.median(times):.2f}ms search_p95={p95:.2f}ms calls={len(times)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factor", type=int, default=100)
    factor = parser.parse_args().factor
    path = ROOT / "data" / "build" / "catalog.json"
    _, products = read_catalog(path)
    vocabulary = read_vocabulary(path)
    probe(products, vocabulary, "served", reps=50)
    big = [
        p.model_copy(update={"product_id": f"{p.product_id[:2]}-{i:04d}{p.product_id[3:]}"})
        for i in range(factor)
        for p in products
    ]
    probe(big, vocabulary, f"x{factor} synthetic", reps=5)


if __name__ == "__main__":
    main()
