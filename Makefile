.DEFAULT_GOAL := help
UV := uv run

help: ## List targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{printf "  %-14s %s\n",$$1,$$2}'

lint: ## Ruff lint + format check
	$(UV) ruff check .
	$(UV) ruff format --check .

typecheck: ## mypy strict over src/catalog
	$(UV) mypy

test: ## Full suite; writes coverage, auth and architecture reports (G-COVERAGE, G-AUTH, G-ARCH-LAYERS)
	$(UV) pytest --cov --cov-report=term --cov-report=json:evals/reports/coverage-raw.json
	$(UV) python scripts/coverage_report.py

spec-lint: ## Lint the served OpenAPI against the platform's rules (G-SPEC-LINT)
	$(UV) python scripts/spec_lint.py

eval-l1: ## Level-1 cases over HTTP, exact match and response tokens (G-L1-EXACT, G-RESP-TOKENS-*)
	$(UV) python evals/golden/l1/run.py

secrets: ## Secrets in tracked files that are not in the reviewed baseline (G-SECRETS)
	$(UV) python scripts/secrets_check.py

run: ## Serve locally on :8000 (needs CATALOG_API_KEY in the environment or .env)
	set -a; [ -f .env ] && . ./.env; set +a; $(UV) uvicorn catalog.api.app:app_from_env --factory --port 8000

latency: ## p95 of list and search calls against a deployed URL (G-LATENCY-P95); make latency URL=https://...
	set -a; [ -f .env ] && . ./.env; set +a; $(UV) python scripts/remote_checks.py latency $(URL)

check-public: ## Spec, auth and test page from outside (G-PUBLIC-CHECK); make check-public URL=https://...
	set -a; [ -f .env ] && . ./.env; set +a; $(UV) python scripts/remote_checks.py public $(URL)

gate-fast: lint typecheck test ## Everything that must stay green after each change

ingest: ## CSV + data/decisions.yaml -> data/build/catalog.json + ingest-report.json (exit 1 = decision needed)
	$(UV) python -m catalog.ingest

eval-ingest: ## Seeded-anomaly fixtures must stop the ingest with exactly their anomaly (G-INGEST-STOPS)
	$(UV) python evals/ingest/run.py

golden-l1: ## Rebuild level-1 cases from the reference semantics (evals/golden/l1/oracle.py) + review sheet
	cd evals/golden/l1 && $(UV) python build.py

audit-csv: ## Independent audit of the raw export (stdlib only)
	python3 -I scripts/audit_csv.py data/gift-shop-catalog.csv

.PHONY: help lint typecheck test spec-lint eval-l1 secrets run latency check-public gate-fast ingest eval-ingest golden-l1 audit-csv
