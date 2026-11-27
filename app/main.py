"""FastAPI-Hauptanwendung inkl. Lifecycle, Healthcheck, StaticFiles, Web- & API-Router."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import engine, get_db_session
from app.routers.api import api_router
from app.routers.web import web_router
from app.services.exceptions import (
    ConflictError,
    NotFoundError,
    OptimisticLockError,
    StorageError,
    ValidationError,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialisiert beim Start das Dokumentenverzeichnis und gibt den DB-Pool beim Stopp frei."""
    settings = get_settings()
    settings.dokumente_root.mkdir(parents=True, exist_ok=True)
    yield
    await engine.dispose()


app = FastAPI(
    title="Private Hausverwaltung",
    description="Lokale Web-Anwendung zur privaten Hausverwaltung von Wohneinheiten.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(NotFoundError)
async def handle_not_found(_: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": exc.message})


@app.exception_handler(ValidationError)
async def handle_validation(_: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.message},
    )


@app.exception_handler(OptimisticLockError)
async def handle_optimistic_lock(_: Request, exc: OptimisticLockError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": exc.message})


@app.exception_handler(ConflictError)
async def handle_conflict(_: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": exc.message})


@app.exception_handler(StorageError)
async def handle_storage(_: Request, exc: StorageError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": exc.message},
    )


@app.get("/health", tags=["System"])
async def healthcheck(session: AsyncSession = Depends(get_db_session)) -> dict[str, str]:
    """Prüft Anwendungs- und Datenbankverfügbarkeit für den Docker-Healthcheck."""
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(web_router)
app.include_router(api_router)
