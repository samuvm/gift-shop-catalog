"""Judgements a person made about the export, loaded from `data/decisions.yaml`."""

import yaml
from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Category(_Strict):
    name: str
    slug: str
    id_prefix: str


class CrossListing(_Strict):
    ids: list[str]
    primary: str
    reason: str


class StockRules(_Strict):
    unlimited_sentinel: int
    low_stock_max: int


class ShippingRules(_Strict):
    digital_days: int


class RemovalGuard(_Strict):
    max_removed_ratio: float


class QualityRules(_Strict):
    thin_description_max_chars: int


class Decisions(_Strict):
    version: int
    categories: list[Category]
    recipients: list[str]
    occasions: list[str]
    cross_listed: list[CrossListing]
    stock: StockRules
    shipping: ShippingRules
    removal_guard: RemovalGuard
    quality: QualityRules


def load_decisions(text: str) -> Decisions:
    """Parse and check the decisions file. A malformed decision is an error, never a silent default."""
    decisions = Decisions.model_validate(yaml.safe_load(text))
    for pair in decisions.cross_listed:
        if len(pair.ids) != len(set(pair.ids)) or len(pair.ids) < 2:
            raise ValueError(f"cross_listed {pair.ids}: needs two or more distinct IDs")
        if pair.primary not in pair.ids:
            raise ValueError(f"cross_listed {pair.ids}: primary {pair.primary!r} is not one of its IDs")
    prefixes = [c.id_prefix for c in decisions.categories]
    if len(prefixes) != len(set(prefixes)):
        raise ValueError("categories: two categories share an ID prefix")
    return decisions
