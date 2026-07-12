from fastapi import APIRouter

from app.api.routes import grafana_handler, health_handler, incident_handler


api_router = APIRouter()
api_router.include_router(health_handler.router)
api_router.include_router(grafana_handler.router)
api_router.include_router(incident_handler.router)
