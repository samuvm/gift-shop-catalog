# Catalog Service. The served catalogue (data/build/catalog.json) is committed, so the image
# needs no ingest step: a new export is a commit and a redeploy.
FROM python:3.13.11-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.9.27 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY data/build ./data/build
RUN uv sync --frozen --no-dev && useradd --system --uid 10001 app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
CMD ["/app/.venv/bin/uvicorn", "catalog.api.app:app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
