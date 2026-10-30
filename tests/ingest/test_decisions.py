"""A malformed decisions file is an error at load time, never a silent default."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from catalog.ingest.decisions import load_decisions


@pytest.fixture
def raw(root: Path) -> dict[str, object]:
    loaded: dict[str, object] = yaml.safe_load((root / "data" / "decisions.yaml").read_text(encoding="utf-8"))
    return loaded


def test_the_project_decisions_load(raw: dict[str, object]) -> None:
    decisions = load_decisions(yaml.safe_dump(raw))
    assert len(decisions.categories) == 11
    assert len(decisions.cross_listed) == 2


@pytest.mark.parametrize(
    ("pair", "message"),
    [
        ({"ids": ["HL-021", "KD-024"], "primary": "TG-001", "reason": "x"}, "primary"),
        ({"ids": ["HL-021"], "primary": "HL-021", "reason": "x"}, "two or more"),
        ({"ids": ["HL-021", "HL-021"], "primary": "HL-021", "reason": "x"}, "two or more"),
    ],
)
def test_malformed_cross_listing_is_rejected(
    raw: dict[str, object], pair: dict[str, object], message: str
) -> None:
    raw["cross_listed"] = [pair]
    with pytest.raises(ValueError, match=message):
        load_decisions(yaml.safe_dump(raw))


def test_two_categories_with_one_prefix_are_rejected(raw: dict[str, object]) -> None:
    raw["categories"] = [
        {"name": "Home & Living", "slug": "home-living", "id_prefix": "HL"},
        {"name": "Homeware", "slug": "homeware", "id_prefix": "HL"},
    ]
    with pytest.raises(ValueError, match="share an ID prefix"):
        load_decisions(yaml.safe_dump(raw))


def test_unknown_keys_are_rejected(raw: dict[str, object]) -> None:
    raw["discounts"] = {"black_friday": 0.2}
    with pytest.raises(ValidationError):
        load_decisions(yaml.safe_dump(raw))


@pytest.mark.parametrize(
    ("search", "message"),
    [
        ({"synonyms": [["headphone"]]}, "two or more words"),
        ({"synonyms": [["headphone", "Ear Buds"]]}, "one lower-case word"),
        ({"synonyms": [["headphone", "earbud"], ["earbud", "airpod"]]}, "in two groups"),
        ({"phrases": {"noise": "anc"}}, "two or more lower-case words"),
        ({"phrases": {"noise cancelling": "a n c"}}, "one lower-case word"),
        ({"generic": ["gift set"]}, "search.generic"),
        ({"generic": ["set", "set"]}, "twice"),
        ({"generic": ["set"], "synonyms": [["set", "kit"]]}, "generic and in a synonym group"),
    ],
)
def test_malformed_search_vocabulary_is_rejected(
    raw: dict[str, object], search: dict[str, object], message: str
) -> None:
    raw["search"] = search
    with pytest.raises(ValueError, match=message):
        load_decisions(yaml.safe_dump(raw))
