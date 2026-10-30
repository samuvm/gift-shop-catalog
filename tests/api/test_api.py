"""REST contract: authentication, the response envelope and recoverable errors (ADR-002)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from catalog.api.app import create_app

ROOT = Path(__file__).resolve().parents[2]
DATA_ROUTES = [
    "/categories",
    "/categories/kitchen-dining/products",
    "/products/search?query=candle",
    "/products/KD-001",
]
PUBLIC_ROUTES = ["/health", "/openapi.json"]


class TestAuth:
    def test_every_data_route_rejects_a_missing_or_wrong_key(self, client: TestClient) -> None:
        results = {}
        for route in DATA_ROUTES:
            for label, hdrs in (
                ("missing", {}),
                ("wrong", {"X-API-Key": "nope"}),
                ("empty", {"X-API-Key": ""}),
            ):
                r = client.get(route, headers=hdrs)
                results[f"{route} [{label}]"] = (
                    r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"
                )
        report = ROOT / "evals" / "reports" / "auth-latest.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            json.dumps(
                {"rejected_rate": sum(results.values()) / len(results), "n": len(results), "checks": results},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        assert all(results.values()), [k for k, ok in results.items() if not ok]

    @pytest.mark.parametrize("route", DATA_ROUTES)
    def test_the_right_key_is_accepted(self, client: TestClient, headers: dict[str, str], route: str) -> None:
        assert client.get(route, headers=headers).status_code == 200

    @pytest.mark.parametrize("route", PUBLIC_ROUTES)
    def test_health_and_spec_are_public(self, client: TestClient, route: str) -> None:
        assert client.get(route).status_code == 200

    def test_the_service_refuses_to_start_without_a_key(self) -> None:
        with pytest.raises(ValueError, match="API key"):
            create_app("")


class TestEnvelope:
    def test_list_meta_carries_counts_paging_filters_date_and_version(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        body = client.get("/categories/kitchen-dining/products?max_price=100&limit=2", headers=headers).json()
        meta = body["meta"]
        assert meta["returned"] == 2 and meta["next_offset"] == 2
        assert meta["applied"] == {"category": "kitchen-dining", "max_price": 100.0}
        assert meta["today"] == "2026-10-30"
        assert len(meta["catalog_version"]) == 8

    def test_list_item_has_exactly_the_compact_fields(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        item = client.get("/products/search?query=knife", headers=headers).json()["products"][0]
        assert list(item) == [
            "product_id",
            "name",
            "category",
            "subcategory",
            "price_eur",
            "availability",
            "rating",
            "reviews_count",
            "recipient",
            "occasions",
            "shipping_days",
            "gift_wrap",
            "description",
        ]

    def test_optional_blocks_are_absent_when_empty(self, client: TestClient, headers: dict[str, str]) -> None:
        body = client.get("/categories/kitchen-dining/products", headers=headers).json()
        assert set(body) == {"products", "meta"}

    def test_chef_knife_under_100_is_answered_honestly(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        body = client.get("/products/search?query=chef%20knife&max_price=100", headers=headers).json()
        assert body["over_budget_matches"][0] == {
            "product_id": "KD-001",
            "name": "Chef's Knife 20cm",
            "price_eur": 149.0,
            "over_by_eur": 49.0,
        }
        assert body["suggestions"][0] == {"change": "max_price", "to": 149.0, "would_match": 4}

    def test_details_include_stock_units_and_alternatives_when_out(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        body = client.get("/products/kd-7", headers=headers).json()
        assert body["product"]["product_id"] == "KD-007" and body["product"]["stock_units"] == 0
        assert [p["product_id"] for p in body["in_stock_alternatives"]] == ["KD-004", "KD-005", "KD-006"]
        assert "KD-007" in body["note"]

    def test_an_oversized_limit_is_reduced_with_a_note(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        body = client.get("/products/search?limit=50", headers=headers).json()
        assert body["meta"]["returned"] == 10
        assert "limit" in body["note"]


class TestErrors:
    @pytest.mark.parametrize(
        ("route", "status", "code"),
        [
            ("/categories/garden/products", 404, "unknown_category"),
            ("/categories/home-living/products?subcategory=Lamps", 404, "unknown_subcategory"),
            ("/products/XX-999", 404, "product_not_found"),
            ("/products/search?max_price=abc", 400, "invalid_parameter"),
            ("/products/search?recipient=grandma", 400, "invalid_parameter"),
            ("/products/search?query=" + "x" * 101, 400, "invalid_parameter"),
        ],
    )
    def test_every_error_has_one_shape_with_a_hint(
        self, client: TestClient, headers: dict[str, str], route: str, status: int, code: str
    ) -> None:
        r = client.get(route, headers=headers)
        assert r.status_code == status
        error = r.json()["error"]
        assert error["code"] == code
        assert error["message"] and error["hint"]

    def test_a_subcategory_used_as_category_points_to_the_right_call(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        error = client.get("/categories/garden/products", headers=headers).json()["error"]
        assert error["did_you_mean"] == ["home-living"]
        assert "subcategory 'Garden'" in error["hint"]

    def test_an_empty_result_is_not_an_error(self, client: TestClient, headers: dict[str, str]) -> None:
        r = client.get("/products/search?query=iphone", headers=headers)
        assert r.status_code == 200
        assert r.json()["unmatched_terms"] == ["iphone"]
