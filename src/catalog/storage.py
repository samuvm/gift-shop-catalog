"""The served catalogue on disk: `data/build/catalog.json`, written by the ingest, read by the service.

It holds the products and the search vocabulary (ADR-005). `served_sha256` covers both, so a change
of synonyms is as traceable in a response's `catalog_version` as a change of data.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from catalog.domain.models import Product
from catalog.domain.text import Vocabulary


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dumps(payload: Any) -> bytes:
    """Stable JSON: same input, same bytes."""
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def encode_catalog(
    products: list[Product], source_sha256: str, decisions_sha256: str, search: dict[str, Any]
) -> tuple[bytes, dict[str, str]]:
    """Serialise the catalogue with its version: which export, which decisions, which result."""
    rows = [p.model_dump() for p in products]
    version = {
        "source_sha256": source_sha256,
        "decisions_sha256": decisions_sha256,
        "products_sha256": sha256(dumps(rows)),
        "served_sha256": sha256(dumps({"products": rows, "search": search})),
    }
    return dumps({"version": version, "search": search, "products": rows}), version


def read_catalog(path: Path) -> tuple[dict[str, str], list[Product]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["version"], [Product.model_validate(p) for p in payload["products"]]


def read_vocabulary(path: Path) -> Vocabulary:
    search = json.loads(path.read_text(encoding="utf-8")).get("search") or {}
    return Vocabulary(search.get("phrases"), search.get("synonyms") or [])
