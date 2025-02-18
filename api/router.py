from fastapi import APIRouter
from api.routes import integration
from api.routes import health

api_router = APIRouter()
api_router.include_router(integration.router, tags=["telex_integration_json"])
api_router.include_router(health.router, tags=["server_health_check"])