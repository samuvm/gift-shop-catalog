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
        ({"category_words": {"garden": ["garden"]}}, "not a category"),
        ({"category_words": {"kitchen-dining": ["cooking"]}}, "not a word of"),
        ({"category_words": {"kitchen-dining": ["Kitchen"]}}, "one lower-case word"),
        ({"category_words": {"kitchen-dining": []}}, "no words"),
    ],
)
def test_malformed_search_vocabulary_is_rejected(
    raw: dict[str, object], search: dict[str, object], message: str
) -> None:
    raw["search"] = search
    with pytest.raises(ValueError, match=message):
        load_decisions(yaml.safe_dump(raw))


def test_an_empty_list_of_accepted_exports_loads(raw: dict[str, object]) -> None:
    raw["change_guard"] = {"max_changed_ratio": 0.5, "accepted_exports": None}
    assert load_decisions(yaml.safe_dump(raw)).change_guard.accepted_exports == []


@pytest.mark.parametrize(
    ("accepted", "message"),
    [
        ([{"source_sha256": "abc", "reason": "Winter sale"}], "sha256"),
        ([{"source_sha256": "A" * 64, "reason": "Winter sale"}], "sha256"),
        ([{"source_sha256": "a" * 64, "reason": "  "}], "reason"),
        ([{"source_sha256": "a" * 64, "reason": "x"}, {"source_sha256": "a" * 64, "reason": "y"}], "twice"),
    ],
)
def test_malformed_accepted_export_is_rejected(
    raw: dict[str, object], accepted: list[dict[str, str]], message: str
) -> None:
    raw["change_guard"] = {"max_changed_ratio": 0.5, "accepted_exports": accepted}
    with pytest.raises(ValueError, match=message):
        load_decisions(yaml.safe_dump(raw))


def test_a_category_word_may_be_the_singular_of_the_name(raw: dict[str, object]) -> None:
    raw["search"] = {"category_words": {"tech-gadgets": ["gadget"], "pets": ["pet"]}}
    assert load_decisions(yaml.safe_dump(raw)).search.category_words["tech-gadgets"] == ["gadget"]


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"category": "animals", "recipient": "pet", "reason": "x"}, "not a category"),
        ({"category": "pets", "recipient": "dog", "reason": "x"}, "not one of the recipients"),
        ({"category": "pets", "recipient": "anyone", "reason": "x"}, "not one of the recipients"),
        ({"category": "pets", "recipient": "pet", "reason": " "}, "reason"),
    ],
)
def test_malformed_recipient_override_is_rejected(
    raw: dict[str, object], override: dict[str, str], message: str
) -> None:
    raw["recipient_overrides"] = [override]
    with pytest.raises(ValueError, match=message):
        load_decisions(yaml.safe_dump(raw))


def test_a_category_overridden_twice_is_rejected(raw: dict[str, object]) -> None:
    raw["recipient_overrides"] = [{"category": "pets", "recipient": "pet", "reason": "x"}] * 2
    with pytest.raises(ValueError, match="twice"):
        load_decisions(yaml.safe_dump(raw))
