"""Service für PDF-Upload, SHA-256-Integritätsprüfung und strukturiertes NAS-Dateimanagement."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import uuid

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.dokument import Dokument
from app.models.enums import DokumentKategorie
from app.services.buchung import get_buchung
from app.services.exceptions import NotFoundError, StorageError, ValidationError
from app.services.stammdaten import get_mietvertrag, get_objekt, get_wohneinheit

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class ResolvedDokumentFile:
    """Ergebnis einer sicheren Dokumenten-Auflösung inkl. Integritätsstatus."""

    dokument: Dokument
    full_path: Path
    sha256_valid: bool


def _sanitize_filename(filename: str) -> str:
    """Bereinigt den Originaldateinamen für sichere Dateisystemablage."""
    base = Path(filename or "dokument.pdf").name
    cleaned = _SAFE_FILENAME_RE.sub("_", base).strip("._")
    if not cleaned:
        cleaned = "dokument"
    if not cleaned.lower().endswith(".pdf"):
        cleaned = f"{cleaned}.pdf"
    return cleaned[:150]


def _resolve_safe_path(relativer_pfad: str) -> Path:
    """Löst einen relativen DB-Pfad sicher unterhalb von `DOKUMENTE_ROOT` auf."""
    root = get_settings().dokumente_root.resolve()
    candidate = (root / relativer_pfad).resolve()
    if not candidate.is_relative_to(root):
        raise StorageError("Ungültiger Dokumentpfad (Path Traversal verhindert).")
    return candidate


def compute_sha256_file(path: Path) -> str:
    """Berechnet den SHA-256-Hash einer bestehenden Datei im Streaming-Verfahren."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


async def list_dokumente(
    session: AsyncSession,
    *,
    objekt_id: int | None = None,
    wohneinheit_id: int | None = None,
    mietvertrag_id: int | None = None,
    buchung_id: int | None = None,
    jahr: int | None = None,
    kategorie: DokumentKategorie | None = None,
) -> list[Dokument]:
    stmt = select(Dokument).order_by(Dokument.hochgeladen_am.desc(), Dokument.id.desc())
    if objekt_id is not None:
        stmt = stmt.where(Dokument.objekt_id == objekt_id)
    if wohneinheit_id is not None:
        stmt = stmt.where(Dokument.wohneinheit_id == wohneinheit_id)
    if mietvertrag_id is not None:
        stmt = stmt.where(Dokument.mietvertrag_id == mietvertrag_id)
    if buchung_id is not None:
        stmt = stmt.where(Dokument.buchung_id == buchung_id)
    if jahr is not None:
        stmt = stmt.where(Dokument.jahr == jahr)
    if kategorie is not None:
        stmt = stmt.where(Dokument.kategorie == kategorie)
    return list((await session.scalars(stmt)).all())


async def get_dokument(session: AsyncSession, dokument_id: int) -> Dokument:
    dokument = await session.get(Dokument, dokument_id)
    if dokument is None:
        raise NotFoundError(f"Dokument #{dokument_id} wurde nicht gefunden.")
    return dokument


async def upload_pdf_dokument(
    session: AsyncSession,
    *,
    file: UploadFile,
    objekt_id: int,
    jahr: int,
    kategorie: DokumentKategorie,
    wohneinheit_id: int | None = None,
    mietvertrag_id: int | None = None,
    buchung_id: int | None = None,
    beschreibung: str | None = None,
) -> Dokument:
    """Validiert ein PDF, berechnet den SHA-256-Hash und speichert es strukturiert auf dem NAS."""
    settings = get_settings()

    if not (1990 <= jahr <= 2100):
        raise ValidationError("Das Jahr muss zwischen 1990 und 2100 liegen.")

    # Verknüpfungen validieren und ggf. fehlende Kontext-IDs ableiten
    await get_objekt(session, objekt_id)
    if buchung_id is not None:
        buchung = await get_buchung(session, buchung_id)
        if buchung.objekt_id != objekt_id:
            raise ValidationError("Die Buchung gehört nicht zum angegebenen Objekt.")
        if wohneinheit_id is None:
            wohneinheit_id = buchung.wohneinheit_id
        if mietvertrag_id is None:
            mietvertrag_id = buchung.mietvertrag_id

    if mietvertrag_id is not None:
        vertrag = await get_mietvertrag(session, mietvertrag_id)
        if vertrag.wohneinheit.objekt_id != objekt_id:
            raise ValidationError("Der Mietvertrag gehört nicht zum angegebenen Objekt.")
        if wohneinheit_id is None:
            wohneinheit_id = vertrag.wohneinheit_id

    if wohneinheit_id is not None:
        einheit = await get_wohneinheit(session, wohneinheit_id)
        if einheit.objekt_id != objekt_id:
            raise ValidationError("Die Wohneinheit gehört nicht zum angegebenen Objekt.")

    original_name = Path(file.filename or "dokument.pdf").name
    if not original_name.lower().endswith(".pdf") and file.content_type != "application/pdf":
        raise ValidationError("Es sind ausschließlich PDF-Dateien zulässig.")

    content = await file.read()
    if not content:
        raise ValidationError("Die hochgeladene Datei ist leer.")
    if len(content) > settings.max_upload_size_bytes:
        raise ValidationError(
            f"Die Datei überschreitet das Upload-Limit von {settings.max_upload_size_mb} MB."
        )
    if not content.startswith(b"%PDF-"):
        raise ValidationError(
            "Ungültiges Dateiformat: Die Datei beginnt nicht mit der PDF-Signatur (%PDF-)."
        )

    sha256_hash = hashlib.sha256(content).hexdigest()
    safe_name = _sanitize_filename(original_name)
    unique_name = f"{uuid.uuid4().hex[:12]}_{safe_name}"
    relative_path = Path(str(objekt_id)) / str(jahr) / kategorie.value / unique_name

    target_path = _resolve_safe_path(relative_path.as_posix())
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(".tmp")

    try:
        temp_path.write_bytes(content)
        os.replace(temp_path, target_path)
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        raise StorageError(f"Fehler beim Schreiben der PDF-Datei auf das Volume: {exc}") from exc

    dokument = Dokument(
        objekt_id=objekt_id,
        wohneinheit_id=wohneinheit_id,
        mietvertrag_id=mietvertrag_id,
        buchung_id=buchung_id,
        kategorie=kategorie,
        jahr=jahr,
        original_dateiname=original_name[:255],
        relativer_pfad=relative_path.as_posix(),
        mime_type="application/pdf",
        dateigroesse_bytes=len(content),
        sha256_hash=sha256_hash,
        beschreibung=beschreibung,
    )
    session.add(dokument)
    try:
        await session.flush()
    except Exception:
        # Dateileiche bei DB-Fehler sofort entfernen
        target_path.unlink(missing_ok=True)
        raise

    await session.refresh(dokument)
    return dokument


async def resolve_dokument_file(
    session: AsyncSession,
    dokument_id: int,
    *,
    verify_integrity: bool = True,
) -> ResolvedDokumentFile:
    """Löst ein Dokument auf und prüft optional seinen SHA-256-Hash gegen die Datei auf Disk."""
    dokument = await get_dokument(session, dokument_id)
    full_path = _resolve_safe_path(dokument.relativer_pfad)
    if not full_path.is_file():
        raise StorageError(
            f"Die PDF-Datei '{dokument.relativer_pfad}' wurde auf dem Speichermedium nicht gefunden."
        )

    sha_ok = True
    if verify_integrity:
        actual_hash = compute_sha256_file(full_path)
        sha_ok = actual_hash == dokument.sha256_hash

    return ResolvedDokumentFile(
        dokument=dokument,
        full_path=full_path,
        sha256_valid=sha_ok,
    )


async def delete_dokument(session: AsyncSession, dokument_id: int) -> None:
    """Löscht den Datenbankeintrag und (falls vorhanden) die zugehörige PDF-Datei."""
    dokument = await get_dokument(session, dokument_id)
    full_path = _resolve_safe_path(dokument.relativer_pfad)
    await session.delete(dokument)
    await session.flush()
    full_path.unlink(missing_ok=True)
