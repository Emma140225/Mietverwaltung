"""Web-Router für Soll/Ist-Auswertungen, Portfolio-Cashflow und PDF-Dokumentenarchiv."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.templating import templates
from app.models.enums import DokumentKategorie
from app.routers.web.helpers import (
    flash_context,
    opt_int,
    opt_str,
    parse_month_input,
    redirect_with_flash,
)
from app.services import auswertung as auswertung_service
from app.services import dokument as dokument_service
from app.services import stammdaten as stammdaten_service
from app.services.exceptions import DomainError

router = APIRouter(tags=["Web-Auswertungen & Dokumente"])


def _compute_auswertung_summen(einheit_rows, objekt_rows) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    einheit_summen = {
        "kaltmiete_soll": sum((r.kaltmiete_soll for r in einheit_rows), Decimal("0.00")),
        "nk_abschlag_soll": sum((r.nk_abschlag_soll for r in einheit_rows), Decimal("0.00")),
        "gesamt_soll": sum((r.gesamt_soll for r in einheit_rows), Decimal("0.00")),
        "ist_zahlungseingang": sum((r.ist_zahlungseingang for r in einheit_rows), Decimal("0.00")),
        "differenz_saldo": sum((r.differenz_saldo for r in einheit_rows), Decimal("0.00")),
        "sonderzahlungen": sum((r.sonderzahlungen for r in einheit_rows), Decimal("0.00")),
    }
    objekt_summen = {
        "gesamt_soll": sum((r.gesamt_soll for r in objekt_rows), Decimal("0.00")),
        "ist_mieteinnahmen": sum((r.ist_mieteinnahmen for r in objekt_rows), Decimal("0.00")),
        "ist_sonderzahlungen": sum((r.ist_sonderzahlungen for r in objekt_rows), Decimal("0.00")),
        "ausgaben_umlagefaehig": sum((r.ausgaben_umlagefaehig for r in objekt_rows), Decimal("0.00")),
        "ausgaben_nicht_umlagefaehig": sum((r.ausgaben_nicht_umlagefaehig for r in objekt_rows), Decimal("0.00")),
        "ausgaben_gesamt": sum((r.ausgaben_gesamt for r in objekt_rows), Decimal("0.00")),
        "netto_cashflow": sum((r.netto_cashflow for r in objekt_rows), Decimal("0.00")),
    }
    return einheit_summen, objekt_summen


@router.get("/auswertungen", response_class=HTMLResponse)
async def view_auswertungen(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    heute = date.today()
    von = date(heute.year, 1, 1)
    bis = date(heute.year, 12, 1)

    objekte = await stammdaten_service.list_objekte(session)
    einheiten = await stammdaten_service.list_wohneinheiten(session)
    einheit_rows = await auswertung_service.get_einheit_soll_ist_report(session, von, bis)
    objekt_rows = await auswertung_service.get_objekt_cashflow_report(session, von, bis)
    einheit_summen, objekt_summen = _compute_auswertung_summen(einheit_rows, objekt_rows)

    return templates.TemplateResponse(
        request=request,
        name="auswertungen/index.html",
        context={
            "active_nav": "auswertungen",
            "objekte": objekte,
            "einheiten": einheiten,
            "von_monat_str": von.strftime("%Y-%m"),
            "bis_monat_str": bis.strftime("%Y-%m"),
            "standard_jahr": heute.year,
            "einheit_rows": einheit_rows,
            "objekt_rows": objekt_rows,
            "einheit_summen": einheit_summen,
            "objekt_summen": objekt_summen,
            **flash_context(request),
        },
    )


@router.get("/auswertungen/tabellen", response_class=HTMLResponse)
async def view_auswertungen_partial(
    request: Request,
    von_monat: str | None = Query(default=None),
    bis_monat: str | None = Query(default=None),
    objekt_id: str | None = Query(default=None),
    wohneinheit_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    heute = date.today()
    von = parse_month_input(von_monat, date(heute.year, 1, 1))
    bis = parse_month_input(bis_monat, date(heute.year, 12, 1))
    if bis < von:
        bis = von

    obj_id = opt_int(objekt_id)
    we_id = opt_int(wohneinheit_id)

    einheit_rows = await auswertung_service.get_einheit_soll_ist_report(
        session, von, bis, objekt_id=obj_id, wohneinheit_id=we_id
    )
    objekt_rows = await auswertung_service.get_objekt_cashflow_report(
        session, von, bis, objekt_id=obj_id
    )
    einheit_summen, objekt_summen = _compute_auswertung_summen(einheit_rows, objekt_rows)

    return templates.TemplateResponse(
        request=request,
        name="auswertungen/partials/tabellen.html",
        context={
            "einheit_rows": einheit_rows,
            "objekt_rows": objekt_rows,
            "einheit_summen": einheit_summen,
            "objekt_summen": objekt_summen,
        },
    )


# --- PDF-Dokumentenarchiv ---

@router.get("/dokumente", response_class=HTMLResponse)
async def view_dokumente(
    request: Request,
    objekt_id: str | None = Query(default=None),
    kategorie: str | None = Query(default=None),
    jahr: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    f_objekt = opt_int(objekt_id)
    f_kat = opt_str(kategorie)
    f_jahr = opt_int(jahr)

    kat_enum = DokumentKategorie(f_kat) if f_kat else None
    dokumente = await dokument_service.list_dokumente(
        session,
        objekt_id=f_objekt,
        kategorie=kat_enum,
        jahr=f_jahr,
    )
    objekte = await stammdaten_service.list_objekte(session)
    einheiten = await stammdaten_service.list_wohneinheiten(session)

    return templates.TemplateResponse(
        request=request,
        name="dokumente/index.html",
        context={
            "active_nav": "dokumente",
            "dokumente": dokumente,
            "objekte": objekte,
            "einheiten": einheiten,
            "kategorien": list(DokumentKategorie),
            "filter_objekt_id": f_objekt,
            "filter_kategorie": f_kat,
            "filter_jahr": f_jahr,
            "standard_jahr": date.today().year,
            **flash_context(request),
        },
    )


@router.post("/dokumente/upload")
async def web_upload_dokument(
    file: UploadFile = File(...),
    objekt_id: int = Form(...),
    jahr: int = Form(...),
    kategorie: DokumentKategorie = Form(...),
    wohneinheit_id: str | None = Form(default=None),
    mietvertrag_id: str | None = Form(default=None),
    buchung_id: str | None = Form(default=None),
    beschreibung: str | None = Form(default=None),
    redirect_to: str = Form(default="/dokumente"),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    target = redirect_to if redirect_to.startswith("/") else "/dokumente"
    try:
        dok = await dokument_service.upload_pdf_dokument(
            session,
            file=file,
            objekt_id=objekt_id,
            jahr=jahr,
            kategorie=kategorie,
            wohneinheit_id=opt_int(wohneinheit_id),
            mietvertrag_id=opt_int(mietvertrag_id),
            buchung_id=opt_int(buchung_id),
            beschreibung=opt_str(beschreibung),
        )
        return redirect_with_flash(
            target,
            ok=f"PDF '{dok.original_dateiname}' hochgeladen (SHA-256: {dok.sha256_hash[:12]}…).",
        )
    except (DomainError, ValueError) as exc:
        return redirect_with_flash(target, err=getattr(exc, "message", str(exc)))


@router.post("/dokumente/{dokument_id}/delete")
async def web_delete_dokument(
    dokument_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        await dokument_service.delete_dokument(session, dokument_id)
        return redirect_with_flash("/dokumente", ok="Dokument gelöscht.")
    except DomainError as exc:
        return redirect_with_flash("/dokumente", err=exc.message)
