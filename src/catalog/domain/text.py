"""Turning shopper text and product text into comparable words. Deterministic, no model."""

import re

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
