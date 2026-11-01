"""The shared entry point reads arguments the same way for every transport (REST and MCP)."""

import math
from typing import Any

import pytest

from catalog.service import InvalidParameter, normalise
from catalog.tools import OCCASIONS, RECIPIENTS, SORTS


@pytest.mark.parametrize(
    ("given", "read"),
    [
        ({"occasion": "Birthday", "sort": " PRICE_ASC "}, {"occasion": "birthday", "sort": "price_asc"}),
        ({"recipient": "Her, COUPLE,"}, {"recipient": ["her", "couple"]}),
        ({"recipient": ["him", "Him", ""]}, {"recipient": ["him"]}),
        (
            {"recipient": " , ", "occasion": "", "sort": " "},
            {"recipient": [], "occasion": None, "sort": None},
        ),
        ({"min_price": 20, "max_price": 20}, {"min_price": 20, "max_price": 20}),
        ({"query": "Chef Knife"}, {"query": "Chef Knife"}),
    ],
)
def test_loose_values_are_read_as_the_canonical_ones(given: dict[str, Any], read: dict[str, Any]) -> None:
    assert normalise(given) == read


@pytest.mark.parametrize(
    ("args", "allowed"),
    [
        ({"sort": "cheapest"}, SORTS),
        ({"occasion": "wedding"}, OCCASIONS),
        ({"recipient": "her,wife"}, RECIPIENTS),
    ],
)
def test_a_value_outside_a_closed_set_carries_the_allowed_values(
    args: dict[str, Any], allowed: list[str]
) -> None:
    with pytest.raises(InvalidParameter) as caught:
        normalise(args)
    assert caught.value.code == "invalid_parameter"
    assert caught.value.allowed_values == allowed


@pytest.mark.parametrize(
    "args",
    [
        {"min_price": math.nan},
        {"max_price": math.inf},
        {"max_price": -math.inf},
        {"min_price": 9, "max_price": 1},
    ],
)
def test_prices_no_product_can_match_are_refused(args: dict[str, Any]) -> None:
    with pytest.raises(InvalidParameter):
        normalise(args)
