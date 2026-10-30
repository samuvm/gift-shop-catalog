"""General cleaning rules. They hold for any export of this catalogue, so they live in code."""

import re

_WHITESPACE = re.compile(r"\s+")
_AND_WORD = re.compile(r"\band\b")


def clean(value: str | None) -> str | None:
    """Trim and collapse whitespace. Empty means missing, never an empty string."""
    if value is None:
        return None
    collapsed = _WHITESPACE.sub(" ", value).strip()
    return collapsed or None


def category_key(value: str) -> str:
    """Comparison key for category spellings: case, padding and `and` vs `&` do not matter."""
    lowered = (clean(value) or "").lower()
    return _WHITESPACE.sub(" ", _AND_WORD.sub("&", lowered))


def split_multi(value: str | None) -> list[str]:
    """`a|B| c` -> ['a', 'b', 'c']: lower-case, trimmed, no empties, first occurrence wins."""
    parts = ((clean(p) or "").lower() for p in (value or "").split("|"))
    return list(dict.fromkeys(p for p in parts if p))


def parse_yes_no(value: str | None) -> bool | None:
    """`yes`/`no` in any case; anything else is not a boolean."""
    return {"yes": True, "no": False}.get((clean(value) or "").lower())


def parse_number[T: (int, float)](value: str | None, kind: type[T]) -> T | None:
    """Parse a plain number. Missing stays missing; anything else that does not parse raises."""
    text = clean(value)
    if text is None:
        return None
    try:
        return kind(text)
    except ValueError:
        raise ValueError(f"{text!r} is not a valid {kind.__name__}") from None


# Phrases written to steer a language model, not to describe a product. Product copy reaches
# the agent verbatim, so an export that carries them is a prompt injection through the data.
_INSTRUCTION_PATTERNS = re.compile(
    r"\b(ignore|disregard|forget)\b.{0,20}\b(previous|prior|above|earlier|all)\b.{0,20}"
    r"\b(instructions?|prompts?|rules)\b"
    r"|\bsystem\s+prompt\b"
    r"|\byou\s+are\s+now\b"
    r"|\bas\s+an\s+ai\b"
    r"|</?\s*(system|assistant|user|instructions?)\s*>",
    re.IGNORECASE,
)


def looks_like_instruction(text: str) -> bool:
    """True when the text contains phrasing aimed at a language model rather than a shopper."""
    return bool(_INSTRUCTION_PATTERNS.search(text))
