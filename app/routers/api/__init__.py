"""JSON-API-Router unter `/api`."""

from fastapi import APIRouter

from app.routers.api import auswertungen, dokumente, finanzen, kaution, stammdaten

api_router = APIRouter(prefix="/api")
api_router.include_router(stammdaten.router)
api_router.include_router(finanzen.router)
api_router.include_router(kaution.router)
api_router.include_router(dokumente.router)
api_router.include_router(auswertungen.router)
