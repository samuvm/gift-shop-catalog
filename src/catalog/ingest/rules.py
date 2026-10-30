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
