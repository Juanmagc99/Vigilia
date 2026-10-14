COMPOSE := docker compose -f docker/docker-compose.yaml -f docker/docker-compose.dev.yaml
APP_SERVICES := api worker outbox-publisher

.PHONY: help dev-start dev-restart dev-rebuild dev-stop dev-status dev-logs dev-migrate test smoke seed-knowledge

help:
	@echo "Available targets:"
	@echo "  make dev-start      Build and start the local environment"
	@echo "  make dev-restart    Restart the API, worker, and publisher"
	@echo "  make dev-rebuild    Rebuild and recreate application processes"
	@echo "  make dev-stop       Stop containers and retain data"
	@echo "  make dev-status     Show service status"
	@echo "  make dev-logs       Follow service logs"
	@echo "  make dev-migrate    Apply pending migrations"
	@echo "  make test           Run local tests with uv"
	@echo "  make smoke          Check the real flow with simulation and RAG disabled"
	@echo "  make seed-knowledge Index runbooks (requires RAG; uses embeddings)"

dev-start:
	$(COMPOSE) up --build -d --wait --wait-timeout 60

dev-restart:
	$(COMPOSE) restart $(APP_SERVICES)

dev-rebuild:
	$(COMPOSE) build $(APP_SERVICES) migrate
	$(COMPOSE) run --rm migrate
	$(COMPOSE) up --force-recreate -d --wait --wait-timeout 60 $(APP_SERVICES)

dev-stop:
	$(COMPOSE) stop

dev-status:
	$(COMPOSE) ps -a

dev-logs:
	$(COMPOSE) logs -f --tail=100

dev-migrate:
	$(COMPOSE) run --rm migrate

test:
	uv run --locked pytest -q

smoke:
	uv run --locked python scripts/smoke.py

seed-knowledge:
	uv run --locked python scripts/seed_knowledge.py
