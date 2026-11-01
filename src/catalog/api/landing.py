"""Landing page of the demo shop, Ribbon & Co., with the indigo.ai web chat embedded.

Public at / (no key): it shows no catalogue data, only the page, and the chat talks to the
platform, not to this service. The workspace token comes from the environment, never the repo;
without a valid one the page is served without the chat.
"""

import re
from pathlib import Path

from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import Route

HERE = Path(__file__).resolve().parent
WIDGET = '<script defer src="https://platform.indigo.ai/widget.js?token={token}&amp;v=3"></script>'
NO_WIDGET = "<!-- web chat not embedded: WIDGET_TOKEN is unset or not a valid token -->"
MARKER = "<!-- widget -->"
# Workspace tokens are UUIDs; anything outside this alphabet could break out of the attribute.
TOKEN = re.compile(r"[A-Za-z0-9-]{1,64}")
HEADERS = {
    "Cache-Control": "no-cache",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Content-Type-Options": "nosniff",
    # Only what cannot touch the widget: its script, iframe and connections come from origins the
    # platform does not document, so script-src and connect-src are left open.
    "Content-Security-Policy": "frame-ancestors 'none'; base-uri 'none'; object-src 'none'",
}


def render(widget_token: str | None) -> str:
    template = (HERE / "landing.html").read_text(encoding="utf-8")
    if template.count(MARKER) != 1:
        raise ValueError(f"landing.html must hold the widget marker exactly once: {MARKER}")
    valid = widget_token is not None and TOKEN.fullmatch(widget_token) is not None
    return template.replace(MARKER, WIDGET.format(token=widget_token) if valid else NO_WIDGET)


def routes(widget_token: str | None) -> list[Route]:
    """The page and its logo, rendered once per app; the logo URL also serves as the chat's avatar."""
    page = render(widget_token)
    logo = (HERE / "ribbon.svg").read_bytes()

    async def home(_: Request) -> Response:
        return HTMLResponse(page, headers=HEADERS)

    async def ribbon(_: Request) -> Response:
        return Response(logo, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})

    return [Route("/", home, methods=["GET"]), Route("/ribbon.svg", ribbon, methods=["GET"])]
