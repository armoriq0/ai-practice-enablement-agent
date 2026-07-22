.PHONY: up down build migrate seed test lint eval smoke tf-fmt tf-validate
up:
	docker compose up --build
down:
	docker compose down
build:
	docker compose build
migrate:
	docker compose run --rm backend alembic -c /app/alembic.ini upgrade head
seed:
	@echo "Mission fixtures are supplied through the API; no production data is seeded."
test:
	pytest -q tests/backend --cov=backend/app --cov-fail-under=80
	cd frontend && npm run lint && npm run typecheck && npm run build
lint:
	ruff check backend tests && mypy backend/app
	cd frontend && npm run lint
eval:
	python evals/run.py
smoke:
	./scripts/smoke_test.sh
tf-fmt:
	terraform -chdir=infra/terraform fmt -recursive
tf-validate:
	terraform -chdir=infra/terraform/environments/dev init -backend=false
	terraform -chdir=infra/terraform/environments/dev validate
