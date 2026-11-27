"""Zentrale Konfigurationsverwaltung für die Hausverwaltungs-Anwendung."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Anwendungseinstellungen geladen aus Umgebungsvariablen / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://hausverwaltung:hausverwaltung@db:5432/mietverwaltung",
        description="Asynchrone SQLAlchemy-Verbindungs-URL für PostgreSQL.",
    )
    dokumente_root: Path = Field(
        default=Path("/data/dokumente"),
        description="Wurzelverzeichnis für abgelegte PDF-Dokumente auf dem NAS-Volume.",
    )
    app_env: str = Field(default="production")
    log_level: str = Field(default="info")
    max_upload_size_mb: int = Field(default=25, ge=1, le=200)

    @property
    def max_upload_size_bytes(self) -> int:
        """Maximale Dateigröße für Uploads in Bytes."""
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Gibt eine gecachte Settings-Instanz zurück."""
    return Settings()
