"""Turning shopper text and product text into comparable words. Deterministic, no model."""

import re
from collections.abc import Iterable, Mapping

_WORD = re.compile(r"[a-z0-9]+")
# An apostrophe never splits a word: "chef's" is "chef", "kids'" is "kids", "don't" is "dont".
# Straight and curly (phone keyboards type the curly one).
_POSSESSIVE = re.compile(r"(?<=[a-z0-9])['\u2019]s(?![a-z0-9])")
_APOSTROPHE = re.compile(r"['\u2019]")

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


def tokens(text: str | None) -> list[str]:
    """The lowercase words of a text, unstemmed. Single letters and digits stay: in this catalogue
    they carry meaning ("Vitamin C", "E-Reader", "3-cup")."""
    lowered = _APOSTROPHE.sub("", _POSSESSIVE.sub("", (text or "").lower()))
    return _WORD.findall(lowered)


def words(text: str) -> set[str]:
    """Every stemmed word in a piece of product text."""
    return {stem(w) for w in tokens(text)}


def query_terms(query: str | None) -> list[str]:
    """The meaningful, stemmed words of a query, in order, without repeats."""
    terms = (stem(w) for w in tokens(query) if w not in STOPWORDS)
    return list(dict.fromkeys(terms))


class Vocabulary:
    """Shopper words the catalogue spells differently (ADR-005, ADR-006), decided by a person in
    decisions.yaml.

    `phrases` rewrites a multi-word phrase into one catalogue word before the query is split
    ("noise cancelling" -> "anc"). `synonyms` groups words that mean the same thing to a shopper;
    a query word matches any word of its group. `generic` words ("set", "kit") say how a product is
    packaged, not what it is: they are dropped when the query has another word.
    """

    def __init__(
        self,
        phrases: Mapping[str, str] | None = None,
        synonyms: Iterable[Iterable[str]] = (),
        generic: Iterable[str] = (),
    ) -> None:
        normalised = ((" ".join(tokens(k)), v.lower()) for k, v in (phrases or {}).items())
        self._phrases = sorted(normalised, key=lambda kv: (-len(kv[0]), kv[0]))
        self._groups: dict[str, frozenset[str]] = {}
        for group in synonyms:
            stems = frozenset(stem(w.lower()) for w in group)
            for s in stems:
                self._groups[s] = stems
        self._generic = frozenset(stem(w.lower()) for w in generic)

    def _words(self, query: str | None) -> list[str]:
        text = " ".join(tokens(query))
        for phrase, word in self._phrases:
            text = re.sub(rf"\b{re.escape(phrase)}\b", word, text)
        return query_terms(text)

    def terms(self, query: str | None) -> list[str]:
        found = self._words(query)
        specific = [t for t in found if t not in self._generic]
        return specific or found

    def main_word(self, query: str | None) -> str | None:
        """The word that names the product: the last specific one, when the query has two or more."""
        found = self._words(query)
        specific = [t for t in found if t not in self._generic]
        return specific[-1] if len(found) > 1 and specific else None

    def group(self, term: str) -> frozenset[str]:
        return self._groups.get(term, frozenset({term}))
