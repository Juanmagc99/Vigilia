COMPOSE := docker compose -f docker/docker-compose.dev.yaml
APP_SERVICES := api worker outbox-publisher

.PHONY: help dev-start dev-restart dev-rebuild dev-stop dev-status dev-logs

help:
	@echo "Targets disponibles:"
	@echo "  make dev-start    Construye y levanta todo el entorno local en segundo plano"
	@echo "  make dev-restart  Reinicia API, worker y publicador; conserva la base de datos"
	@echo "  make dev-rebuild  Reconstruye y recrea solo API, worker y publicador"
	@echo "  make dev-stop     Para los contenedores sin borrar datos ni volúmenes"
	@echo "  make dev-status   Muestra el estado de los servicios"
	@echo "  make dev-logs     Sigue los logs de todos los servicios"

dev-start:
	$(COMPOSE) up --build -d

dev-restart:
	$(COMPOSE) restart $(APP_SERVICES)

dev-rebuild:
	$(COMPOSE) up --build --force-recreate -d $(APP_SERVICES)

dev-stop:
	$(COMPOSE) stop

dev-status:
	$(COMPOSE) ps

dev-logs:
	$(COMPOSE) logs -f --tail=100
