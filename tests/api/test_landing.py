"""Landing page at /: public, embeds the web chat only with a valid token, and leaks no secret."""

import pytest
from fastapi.testclient import TestClient

from catalog.api.app import create_app

from .conftest import KEY

WORKSPACE = "00000000-0000-4000-8000-000000000000"  # shaped like a workspace token, not a real one
WIDGET_SRC = "https://platform.indigo.ai/widget.js?token="


def page(widget_token: str | None) -> str:
    response = TestClient(create_app(KEY, widget_token=widget_token)).get("/")
    assert response.status_code == 200
    return response.text


def test_the_page_is_public_html(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Ribbon &amp; Co." in response.text


def test_the_widget_is_embedded_with_the_token() -> None:
    html = page(WORKSPACE)
    assert f'<script defer src="{WIDGET_SRC}{WORKSPACE}&amp;v=3"></script>' in html
    assert html.count(WIDGET_SRC) == 1


def test_without_a_token_there_is_no_widget_script() -> None:
    for token in (None, ""):
        html = page(token)
        assert WIDGET_SRC not in html
        assert "WIDGET_TOKEN" in html  # the note, inside an HTML comment


@pytest.mark.parametrize(
    "token",
    [
        '"><script>alert(1)</script>',
        "abc&autostart=on",
        "abc def",
        "abc\n",
        "a" * 65,
    ],
)
def test_a_token_outside_the_alphabet_is_not_rendered(token: str) -> None:
    html = page(token)
    assert WIDGET_SRC not in html
    assert token not in html


def test_the_api_key_never_appears_in_the_page() -> None:
    assert KEY not in page(WORKSPACE)
    assert KEY not in page(None)


def test_the_logo_is_served_as_svg(client: TestClient) -> None:
    response = client.get("/ribbon.svg")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"


def test_the_page_is_not_in_either_spec(client: TestClient) -> None:
    assert "/" not in client.get("/openapi.json").json()["paths"]
    assert "/" not in create_app("k").openapi()["paths"]
