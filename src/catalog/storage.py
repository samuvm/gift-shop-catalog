"""The served catalogue on disk: `data/build/catalog.json`, written by the ingest, read by the service."""

import hashlib
import json
from pathlib import Path
from typing import Any

from catalog.domain.models import Product


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dumps(payload: Any) -> bytes:
    """Stable JSON: same input, same bytes."""
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def encode_catalog(
    products: list[Product], source_sha256: str, decisions_sha256: str
) -> tuple[bytes, dict[str, str]]:
    """Serialise the catalogue with its version: which export, which decisions, which result."""
    rows = [p.model_dump() for p in products]
    version = {
        "source_sha256": source_sha256,
        "decisions_sha256": decisions_sha256,
        "products_sha256": sha256(dumps(rows)),
    }
    return dumps({"version": version, "products": rows}), version


def read_catalog(path: Path) -> tuple[dict[str, str], list[Product]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["version"], [Product.model_validate(p) for p in payload["products"]]
