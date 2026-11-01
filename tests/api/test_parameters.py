"""REST contract for parameters: how values are read, which are refused and what the refusal says.

A model reads an error body to correct its next call, so every refusal names the parameter and,
for a closed set of values, lists them (ADR-002, ADR-007).
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from catalog.tools import OCCASIONS, RECIPIENTS, SLUGS, SORTS


def _get(client: TestClient, headers: dict[str, str], url: str) -> tuple[int, dict[str, Any]]:
    r = client.get(url, headers=headers)
    return r.status_code, r.json()


class TestCaseAndSpacing:
    @pytest.mark.parametrize(
        ("loose", "canonical"),
        [
            ("recipient=HER", "recipient=her"),
            ("recipient=Her,Couple", "recipient=her,couple"),
            ("recipient=her,%20couple", "recipient=her,couple"),
            ("recipient=her,", "recipient=her"),
            ("recipient=her,,couple", "recipient=her,couple"),
            ("occasion=Birthday", "occasion=birthday"),
            ("occasion=%20Thank-You%20", "occasion=thank-you"),
            ("sort=PRICE_ASC", "sort=price_asc"),
        ],
    )
    def test_a_loose_value_answers_like_the_canonical_one(
        self, client: TestClient, headers: dict[str, str], loose: str, canonical: str
    ) -> None:
        status, body = _get(client, headers, f"/products/search?query=candle&{loose}")
        assert status == 200
        assert body == _get(client, headers, f"/products/search?query=candle&{canonical}")[1]

    def test_applied_reports_the_canonical_values(self, client: TestClient, headers: dict[str, str]) -> None:
        _, body = _get(
            client, headers, "/categories/home-living/products?recipient=HER,%20Couple,&occasion=Housewarming"
        )
        assert body["meta"]["applied"]["recipient"] == ["her", "couple"]
        assert body["meta"]["applied"]["occasion"] == "housewarming"

    @pytest.mark.parametrize("blank", ["recipient=", "recipient=,", "occasion=", "sort=%20"])
    def test_a_blank_value_means_the_filter_was_left_out(
        self, client: TestClient, headers: dict[str, str], blank: str
    ) -> None:
        status, body = _get(client, headers, f"/products/search?query=candle&{blank}")
        assert status == 200
        assert body == _get(client, headers, "/products/search?query=candle")[1]


class TestErrorBodies:
    def test_unknown_category_lists_the_slugs_and_the_closest(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        status, body = _get(client, headers, "/categories/kichen-dining/products")
        assert status == 404
        assert body["error"]["allowed_values"] == SLUGS
        assert body["error"]["did_you_mean"] == ["kitchen-dining"]

    def test_unknown_product_suggests_close_ids(self, client: TestClient, headers: dict[str, str]) -> None:
        status, body = _get(client, headers, "/products/KD-0011")
        assert status == 404
        assert body["error"]["code"] == "product_not_found"
        assert "KD-001" in body["error"]["did_you_mean"]

    def test_unknown_subcategory_hint_names_the_call(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        status, body = _get(client, headers, "/categories/home-living/products?subcategory=Lamps")
        assert status == 404
        assert "subcategory 'Lighting'" in body["error"]["hint"]
        assert "Lighting" in body["error"]["allowed_values"]

    def test_unauthorized_says_how_to_authenticate(self, client: TestClient) -> None:
        r = client.get("/products/search")
        assert r.status_code == 401
        assert "X-API-Key" in r.json()["error"]["hint"]

    @pytest.mark.parametrize(
        ("param", "value", "allowed", "did_you_mean"),
        [
            ("sort", "cheapest", SORTS, []),
            ("sort", "price-asc", SORTS, ["price_asc", "price_desc"]),
            ("occasion", "thankyou", OCCASIONS, ["thank-you"]),
            ("recipient", "her,wife", RECIPIENTS, []),
            ("include_out_of_stock", "maybe", ["true", "false"], None),
        ],
    )
    def test_a_value_outside_a_closed_set_lists_the_allowed_ones(
        self,
        client: TestClient,
        headers: dict[str, str],
        param: str,
        value: str,
        allowed: list[str],
        did_you_mean: list[str] | None,
    ) -> None:
        status, body = _get(client, headers, f"/products/search?{param}={value}")
        error = body["error"]
        assert (status, error["code"]) == (400, "invalid_parameter")
        assert error["message"].startswith(param) and error["hint"]
        assert error["allowed_values"] == allowed
        assert error.get("did_you_mean", []) == (did_you_mean or [])


class TestBounds:
    @pytest.mark.parametrize(
        ("url", "param"),
        [
            ("/products/search?limit=0", "limit"),
            ("/products/search?offset=-1", "offset"),
            ("/products/search?max_shipping_days=-1", "max_shipping_days"),
            ("/products/search?max_shipping_days=15", "max_shipping_days"),
            ("/products/search?min_price=-1", "min_price"),
            ("/products/search?max_price=-0.5", "max_price"),
            ("/products/search?min_price=nan", "min_price"),
            ("/products/search?max_price=inf", "max_price"),
            ("/products/search?max_price=-inf", "max_price"),
            ("/products/search?limit=two", "limit"),
            ("/products/search?query=" + "x" * 101, "query"),
            ("/products/search?exclude=" + "x" * 201, "exclude"),
            ("/products/search?recipient=" + "her," * 10 + "him", "recipient"),
            ("/categories/home-living/products?subcategory=" + "x" * 51, "subcategory"),
            ("/categories/" + "x" * 51 + "/products", "category"),
            ("/products/" + "X" * 21, "product_id"),
        ],
    )
    def test_out_of_range_is_refused_naming_the_parameter(
        self, client: TestClient, headers: dict[str, str], url: str, param: str
    ) -> None:
        status, body = _get(client, headers, url)
        assert (status, body["error"]["code"]) == (400, "invalid_parameter")
        assert body["error"]["message"].startswith(param)
        assert body["error"]["hint"]

    def test_a_price_range_upside_down_is_refused_with_the_fix(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        status, body = _get(client, headers, "/products/search?min_price=100&max_price=10")
        assert (status, body["error"]["code"]) == (400, "invalid_parameter")
        assert body["error"]["message"] == "min_price (100) is above max_price (10)."
        assert "Swap" in body["error"]["hint"]

    def test_an_equal_price_range_is_a_valid_exact_price(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        status, body = _get(client, headers, "/products/search?min_price=149&max_price=149")
        assert status == 200
        assert {p["price_eur"] for p in body["products"]} == {149.0}


class TestPagination:
    @pytest.mark.parametrize(
        "route", ["/products/search?", "/products/search?query=candle&", "/categories/home-living/products?"]
    )
    @pytest.mark.parametrize("limit", [3, 10])
    def test_pages_concatenate_to_the_whole_list_once(
        self, client: TestClient, headers: dict[str, str], route: str, limit: int
    ) -> None:
        seen: list[str] = []
        offset: int | None = 0
        while offset is not None:
            _, body = _get(client, headers, f"{route}limit={limit}&offset={offset}")
            seen += [p["product_id"] for p in body["products"]]
            offset = body["meta"]["next_offset"]
        assert len(seen) == len(set(seen)) == body["meta"]["total_matches"]
        _, first = _get(client, headers, f"{route}limit=10")
        assert seen[:10] == [p["product_id"] for p in first["products"]]

    def test_an_offset_past_the_end_is_an_empty_last_page(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        status, body = _get(client, headers, "/products/search?offset=100000")
        assert status == 200
        assert body["products"] == []
        assert body["meta"]["returned"] == 0 and body["meta"]["next_offset"] is None
