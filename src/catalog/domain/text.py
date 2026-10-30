"""Turning shopper text and product text into comparable words. Deterministic, no model."""

import re
from collections.abc import Iterable, Mapping

_WORD = re.compile(r"[a-z0-9]+")

# Words that carry no product meaning in a gift-shop query.
# fmt: off
STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "for", "with", "of", "to", "in", "on", "at", "by", "from",
    "my", "his", "her", "him", "their", "our", "your", "me", "i", "it", "is", "that", "this",
    "some", "something", "any", "gift", "gifts", "present", "presents", "idea", "ideas",
})
# fmt: on


def stem(word: str) -> str:
    """English plural to singular, crudely: knives -> knife, glasses -> glass, accessories -> accessory."""
    if len(word) <= 3:
        return word
    for suffix, replacement in (("ies", "y"), ("ives", "ife"), ("ves", "f")):
        if word.endswith(suffix):
            return word[: -len(suffix)] + replacement
    if word.endswith(("sses", "xes", "zes", "ches", "shes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def words(text: str) -> set[str]:
    """Every stemmed word in a piece of product text."""
    return {stem(w) for w in _WORD.findall(text.lower())}


def query_terms(query: str | None) -> list[str]:
    """The meaningful, stemmed words of a query, in order, without repeats."""
    terms = (stem(w) for w in _WORD.findall((query or "").lower()) if w not in STOPWORDS)
    return list(dict.fromkeys(terms))


class Vocabulary:
    """Shopper words the catalogue spells differently (ADR-005), decided by a person in decisions.yaml.

    `phrases` rewrites a multi-word phrase into one catalogue word before the query is split
    ("noise cancelling" -> "anc"). `synonyms` groups words that mean the same thing to a shopper;
    a query word matches any word of its group.
    """

    def __init__(
        self, phrases: Mapping[str, str] | None = None, synonyms: Iterable[Iterable[str]] = ()
    ) -> None:
        normalised = ((" ".join(_WORD.findall(k.lower())), v.lower()) for k, v in (phrases or {}).items())
        self._phrases = sorted(normalised, key=lambda kv: (-len(kv[0]), kv[0]))
        self._groups: dict[str, frozenset[str]] = {}
        for group in synonyms:
            stems = frozenset(stem(w.lower()) for w in group)
            for s in stems:
                self._groups[s] = stems

    def terms(self, query: str | None) -> list[str]:
        text = " ".join(_WORD.findall((query or "").lower()))
        for phrase, word in self._phrases:
            text = re.sub(rf"\b{re.escape(phrase)}\b", word, text)
        return query_terms(text)

    def group(self, term: str) -> frozenset[str]:
        return self._groups.get(term, frozenset({term}))
