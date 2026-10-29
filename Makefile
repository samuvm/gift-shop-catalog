.DEFAULT_GOAL := help
UV := uv run

help: ## List targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{printf "  %-14s %s\n",$$1,$$2}'

lint: ## Ruff lint + format check
	$(UV) ruff check .
	$(UV) ruff format --check .

typecheck: ## mypy strict over src/catalog
	$(UV) mypy

test: ## Full test suite with coverage
	$(UV) pytest --cov --cov-report=term

gate-fast: lint typecheck test ## Everything that must stay green after each change

audit-csv: ## Independent audit of the raw export (stdlib only)
	python3 -I scripts/audit_csv.py data/gift-shop-catalog.csv

.PHONY: help lint typecheck test gate-fast audit-csv
