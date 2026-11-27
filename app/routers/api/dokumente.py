"""API-Endpunkte für PDF-Dokumentenmanagement (Upload, Vorschau, Download & Löschung)."""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.enums import DokumentKategorie
from app.schemas.kaution_dokument import DokumentRead
from app.services import dokument as dokument_service

router = APIRouter(tags=["Dokumente (PDF)"])


@router.get("/dokumente", response_model=list[DokumentRead])
async def api_list_dokumente(
    objekt_id: int | None = Query(default=None),
    wohneinheit_id: int | None = Query(default=None),
    mietvertrag_id: int | None = Query(default=None),
    buchung_id: int | None = Query(default=None),
    jahr: int | None = Query(default=None),
    kategorie: DokumentKategorie | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    return await dokument_service.list_dokumente(
        session,
        objekt_id=objekt_id,
        wohneinheit_id=wohneinheit_id,
        mietvertrag_id=mietvertrag_id,
        buchung_id=buchung_id,
        jahr=jahr,
        kategorie=kategorie,
    )


@router.post("/dokumente", response_model=DokumentRead, status_code=status.HTTP_201_CREATED)
async def api_upload_dokument(
    file: UploadFile = File(...),
    objekt_id: int = Form(...),
    jahr: int = Form(...),
    kategorie: DokumentKategorie = Form(...),
    wohneinheit_id: int | None = Form(default=None),
    mietvertrag_id: int | None = Form(default=None),
    buchung_id: int | None = Form(default=None),
    beschreibung: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    return await dokument_service.upload_pdf_dokument(
        session,
        file=file,
        objekt_id=objekt_id,
        jahr=jahr,
        kategorie=kategorie,
        wohneinheit_id=wohneinheit_id,
        mietvertrag_id=mietvertrag_id,
        buchung_id=buchung_id,
        beschreibung=beschreibung,
    )


@router.get("/dokumente/{dokument_id}/vorschau")
async def api_preview_dokument(
    dokument_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """Liefert die PDF-Datei direkt für Browser-Inline-Vorschau aus."""
    resolved = await dokument_service.resolve_dokument_file(session, dokument_id)
    return FileResponse(
        path=resolved.full_path,
        media_type=resolved.dokument.mime_type,
        content_disposition_type="inline",
        filename=resolved.dokument.original_dateiname,
        headers={
            "X-SHA256-Hash": resolved.dokument.sha256_hash,
            "X-SHA256-Valid": "true" if resolved.sha256_valid else "false",
        },
    )


@router.get("/dokumente/{dokument_id}/download")
async def api_download_dokument(
    dokument_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """Liefert die PDF-Datei als Download inkl. SHA-256-Integritätsheader aus."""
    resolved = await dokument_service.resolve_dokument_file(session, dokument_id)
    return FileResponse(
        path=resolved.full_path,
        media_type=resolved.dokument.mime_type,
        content_disposition_type="attachment",
        filename=resolved.dokument.original_dateiname,
        headers={
            "X-SHA256-Hash": resolved.dokument.sha256_hash,
            "X-SHA256-Valid": "true" if resolved.sha256_valid else "false",
        },
    )


@router.delete("/dokumente/{dokument_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_dokument(
    dokument_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    await dokument_service.delete_dokument(session, dokument_id)
