"""Judgements a person made about the export, loaded from `data/decisions.yaml`."""

import re

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class AcceptedExport(_Strict):
    """One export a person checked and accepted despite the change guard, e.g. a seasonal sale."""

    source_sha256: str
    reason: str


class ChangeGuard(_Strict):
    max_changed_ratio: float
    accepted_exports: list[AcceptedExport] = Field(default_factory=list)

    @field_validator("accepted_exports", mode="before")
    @classmethod
    def _none_is_empty(cls, value: object) -> object:
        return [] if value is None else value  # `accepted_exports:` with no line under it yet


class QualityRules(_Strict):
    thin_description_max_chars: int


class SearchVocabulary(_Strict):
    """Shopper words the catalogue spells differently (ADR-005), and packaging words (ADR-006)."""

    phrases: dict[str, str] = Field(default_factory=dict)
    synonyms: list[list[str]] = Field(default_factory=list)
    generic: list[str] = Field(default_factory=list)


class Decisions(_Strict):
    version: int
    categories: list[Category]
    recipients: list[str]
    occasions: list[str]
    cross_listed: list[CrossListing]
    stock: StockRules
    shipping: ShippingRules
    removal_guard: RemovalGuard
    change_guard: ChangeGuard
    quality: QualityRules
    search: SearchVocabulary = Field(default_factory=SearchVocabulary)


_WORD = re.compile(r"[a-z0-9]+")
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _check_change_guard(guard: ChangeGuard) -> None:
    hashes = [a.source_sha256 for a in guard.accepted_exports]
    for accepted in guard.accepted_exports:
        if not _SHA256.fullmatch(accepted.source_sha256):
            raise ValueError(f"change_guard {accepted.source_sha256!r}: not a lower-case hex sha256")
        if not accepted.reason.strip():
            raise ValueError(f"change_guard {accepted.source_sha256}: an accepted export needs a reason")
        if hashes.count(accepted.source_sha256) > 1:
            raise ValueError(f"change_guard {accepted.source_sha256}: accepted twice")


def _check_search(search: SearchVocabulary) -> None:
    seen: dict[str, int] = {}
    for n, group in enumerate(search.synonyms):
        if len(group) < 2:
            raise ValueError(f"search.synonyms {group}: a group needs two or more words")
        for word in group:
            if not _WORD.fullmatch(word):
                raise ValueError(f"search.synonyms {group}: {word!r} must be one lower-case word")
            if seen.setdefault(word, n) != n:
                raise ValueError(f"search.synonyms: {word!r} is in two groups")
    for phrase, word in search.phrases.items():
        if len(_WORD.findall(phrase)) < 2 or phrase != " ".join(_WORD.findall(phrase)):
            raise ValueError(f"search.phrases {phrase!r}: must be two or more lower-case words")
        if not _WORD.fullmatch(word):
            raise ValueError(f"search.phrases {phrase!r}: {word!r} must be one lower-case word")
    for word in search.generic:
        if not _WORD.fullmatch(word):
            raise ValueError(f"search.generic {word!r}: must be one lower-case word")
        if search.generic.count(word) > 1:
            raise ValueError(f"search.generic: {word!r} is listed twice")
        if word in seen:
            raise ValueError(f"search: {word!r} is both generic and in a synonym group")


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
    _check_change_guard(decisions.change_guard)
    _check_search(decisions.search)
    return decisions
