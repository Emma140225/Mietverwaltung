"""API-Endpunkte für Soll/Ist-Auswertungen, Cashflow und Abrechner-Exporte (CSV/ZIP)."""

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.services import auswertung as auswertung_service
from app.services import export as export_service

router = APIRouter(tags=["Auswertungen & Export"])


def _default_range() -> tuple[date, date]:
    heute = date.today()
    return date(heute.year, 1, 1), date(heute.year, 12, 1)


@router.get("/auswertungen/dashboard")
async def api_dashboard_summary(
    referenz_monat: date | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    summary = await auswertung_service.get_dashboard_summary(
        session,
        referenz_monat=referenz_monat,
    )
    return {
        "anzahl_objekte": summary.anzahl_objekte,
        "anzahl_einheiten": summary.anzahl_einheiten,
        "vermietete_einheiten": summary.vermietete_einheiten,
        "leerstand_einheiten": summary.leerstand_einheiten,
        "monat_start": summary.monat_start,
        "monat_soll_gesamt": summary.monat_soll_gesamt,
        "monat_ist_mieteinnahmen": summary.monat_ist_mieteinnahmen,
        "monat_ausgaben_gesamt": summary.monat_ausgaben_gesamt,
        "monat_netto_cashflow": summary.monat_netto_cashflow,
        "offene_kautionen": summary.offene_kautionen,
        "soll_ist_abweichungen": [asdict(r) for r in summary.soll_ist_abweichungen],
    }


@router.get("/auswertungen/einheiten-soll-ist")
async def api_einheit_soll_ist(
    von_monat: date | None = Query(default=None),
    bis_monat: date | None = Query(default=None),
    objekt_id: int | None = Query(default=None),
    wohneinheit_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    default_von, default_bis = _default_range()
    rows = await auswertung_service.get_einheit_soll_ist_report(
        session,
        von_monat=von_monat or default_von,
        bis_monat=bis_monat or default_bis,
        objekt_id=objekt_id,
        wohneinheit_id=wohneinheit_id,
    )
    return [asdict(r) for r in rows]


@router.get("/auswertungen/objekte-cashflow")
async def api_objekt_cashflow(
    von_monat: date | None = Query(default=None),
    bis_monat: date | None = Query(default=None),
    objekt_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    default_von, default_bis = _default_range()
    rows = await auswertung_service.get_objekt_cashflow_report(
        session,
        von_monat=von_monat or default_von,
        bis_monat=bis_monat or default_bis,
        objekt_id=objekt_id,
    )
    return [asdict(r) for r in rows]


@router.get("/exporte/objekt/{objekt_id}/jahr/{jahr}/csv")
async def api_export_umlagefaehig_csv(
    objekt_id: int,
    jahr: int,
    session: AsyncSession = Depends(get_db_session),
):
    filename, content = await export_service.export_umlagefaehige_kosten_csv(
        session,
        objekt_id=objekt_id,
        jahr=jahr,
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/exporte/objekt/{objekt_id}/jahr/{jahr}/zip")
async def api_export_umlagefaehig_zip(
    objekt_id: int,
    jahr: int,
    session: AsyncSession = Depends(get_db_session),
):
    filename, content = await export_service.export_umlagefaehige_kosten_zip(
        session,
        objekt_id=objekt_id,
        jahr=jahr,
    )
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
