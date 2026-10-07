COMPOSE := docker compose -f docker/docker-compose.yaml -f docker/docker-compose.dev.yaml
APP_SERVICES := api worker outbox-publisher

.PHONY: help dev-start dev-restart dev-rebuild dev-stop dev-status dev-logs dev-migrate test smoke seed-knowledge

help:
	@echo "Targets disponibles:"
	@echo "  make dev-start      Construye y levanta el entorno local"
	@echo "  make dev-restart    Reinicia API, worker y publicador"
	@echo "  make dev-rebuild    Reconstruye y recrea los procesos de aplicacion"
	@echo "  make dev-stop       Para contenedores y conserva los datos"
	@echo "  make dev-status     Muestra el estado de los servicios"
	@echo "  make dev-logs       Sigue los logs"
	@echo "  make dev-migrate    Aplica las migraciones pendientes"
	@echo "  make test           Ejecuta los tests locales con uv"
	@echo "  make smoke          Comprueba el flujo real con el simulador y RAG apagado"
	@echo "  make seed-knowledge Indexa runbooks (requiere RAG; consume embeddings)"

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
