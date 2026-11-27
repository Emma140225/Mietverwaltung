"""HTML/HTMX-Web-Router der Anwendung."""

from fastapi import APIRouter

from app.routers.web import auswertungen, buchungen, dashboard, kautionen, stammdaten

web_router = APIRouter()
web_router.include_router(dashboard.router)
web_router.include_router(stammdaten.router)
web_router.include_router(buchungen.router)
web_router.include_router(kautionen.router)
web_router.include_router(auswertungen.router)
