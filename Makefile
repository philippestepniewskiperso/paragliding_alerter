.DEFAULT_GOAL := run
DB_PATH ?= ./data/paralert.db

.PHONY: help run install dev test test-unit test-integration test-e2e test-front check docker-build docker-up docker-down

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  install        Install dependencies (uv sync)"
	@echo "  dev            Start dev server on :8080"
	@echo "  test           Run all tests"
	@echo "  test-unit      Unit tests only"
	@echo "  test-int       Integration tests only"
	@echo "  test-e2e       API e2e tests only"
	@echo "  test-front     Playwright frontend tests only"
	@echo "  check          Quick smoke test (add summit + trigger check)"
	@echo "  docker-build   Build Docker image"
	@echo "  docker-up      Start with docker compose"
	@echo "  docker-down    Stop docker compose"

run: install dev

install:
	uv sync --dev
	uv run playwright install chromium

dev:
	@mkdir -p data
	DB_PATH=$(DB_PATH) uv run python -m paralert.main

test:
	uv run pytest tests/ --ignore=tests/e2e/test_frontend.py -q
	uv run pytest tests/e2e/test_frontend.py -q

test-unit:
	uv run pytest tests/unit/ -v

test-int:
	uv run pytest tests/integration/ -v

test-e2e:
	uv run pytest tests/e2e/test_api.py -v

test-front:
	uv run pytest tests/e2e/test_frontend.py -v

check:
	@curl -sf http://localhost:8080/api/summits/ > /dev/null || (echo "Server not running. Run: make dev" && exit 1)
	@curl -s -X POST http://localhost:8080/api/summits/ \
		-H "Content-Type: application/json" \
		-d '{"name":"Chamechaude","lat":45.2833,"lon":5.7667,"altitudes_m":[2000,3000],"enabled":true}' | python3 -m json.tool
	@curl -s -X POST http://localhost:8080/api/checks/now | python3 -m json.tool
	@sleep 4 && curl -s http://localhost:8080/api/checks/last | python3 -m json.tool

docker-build:
	docker compose build

docker-up:
	docker compose up

docker-down:
	docker compose down
