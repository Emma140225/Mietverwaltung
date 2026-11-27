"""Auswertungs-Service für Soll/Ist-Analysen, Cashflow und Dashboard-Warnhinweise."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.queries import (
    EinheitMonatSollIstRow,
    ObjektCashflowMonatRow,
    fetch_einheit_soll_ist,
    fetch_objekt_cashflow,
)
from app.models.enums import WohneinheitStatus
from app.models.stammdaten import Objekt, Wohneinheit
from app.schemas.kaution_dokument import KautionStatusUebersichtRead
from app.services.kaution import list_kaution_uebersichten


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    """Kompakte Kennzahlen und Handlungs-Hinweise für die Startseite."""

    anzahl_objekte: int
    anzahl_einheiten: int
    vermietete_einheiten: int
    leerstand_einheiten: int
    monat_start: date
    monat_soll_gesamt: Decimal
    monat_ist_mieteinnahmen: Decimal
    monat_ausgaben_gesamt: Decimal
    monat_netto_cashflow: Decimal
    offene_kautionen: list[KautionStatusUebersichtRead]
    soll_ist_abweichungen: list[EinheitMonatSollIstRow]


async def get_einheit_soll_ist_report(
    session: AsyncSession,
    von_monat: date,
    bis_monat: date,
    *,
    objekt_id: int | None = None,
    wohneinheit_id: int | None = None,
) -> list[EinheitMonatSollIstRow]:
    """Delegiert an die dynamische `generate_series`-Abfrage pro Wohneinheit."""
    return await fetch_einheit_soll_ist(
        session,
        von_monat=von_monat,
        bis_monat=bis_monat,
        objekt_id=objekt_id,
        wohneinheit_id=wohneinheit_id,
    )


async def get_objekt_cashflow_report(
    session: AsyncSession,
    von_monat: date,
    bis_monat: date,
    *,
    objekt_id: int | None = None,
) -> list[ObjektCashflowMonatRow]:
    """Delegiert an die dynamische `generate_series`-Cashflow-Abfrage je Objekt."""
    return await fetch_objekt_cashflow(
        session,
        von_monat=von_monat,
        bis_monat=bis_monat,
        objekt_id=objekt_id,
    )


async def get_dashboard_summary(
    session: AsyncSession,
    *,
    referenz_monat: date | None = None,
) -> DashboardSummary:
    """Erstellt die Übersicht für das Dashboard inkl. offener Kautionsraten und Soll/Ist-Abweichungen."""
    ziel_monat = (referenz_monat or date.today()).replace(day=1)

    anzahl_objekte = int(await session.scalar(select(func.count(Objekt.id))) or 0)
    anzahl_einheiten = int(await session.scalar(select(func.count(Wohneinheit.id))) or 0)
    vermietete_einheiten = int(
        await session.scalar(
            select(func.count(Wohneinheit.id)).where(
                Wohneinheit.status == WohneinheitStatus.VERMIETET
            )
        )
        or 0
    )
    leerstand_einheiten = int(
        await session.scalar(
            select(func.count(Wohneinheit.id)).where(
                Wohneinheit.status == WohneinheitStatus.LEERSTAND
            )
        )
        or 0
    )

    cashflow_rows = await fetch_objekt_cashflow(
        session,
        von_monat=ziel_monat,
        bis_monat=ziel_monat,
    )
    monat_soll_gesamt = sum((r.gesamt_soll for r in cashflow_rows), Decimal("0.00"))
    monat_ist_mieteinnahmen = sum((r.ist_mieteinnahmen for r in cashflow_rows), Decimal("0.00"))
    monat_ausgaben_gesamt = sum((r.ausgaben_gesamt for r in cashflow_rows), Decimal("0.00"))
    monat_netto_cashflow = sum((r.netto_cashflow for r in cashflow_rows), Decimal("0.00"))

    offene_kautionen = await list_kaution_uebersichten(session, nur_offene=True)

    # Rückstände der letzten 3 Monate bis einschließlich Zielmonat hervorheben
    if ziel_monat.month >= 3:
        check_von = date(ziel_monat.year, ziel_monat.month - 2, 1)
    else:
        check_von = date(ziel_monat.year - 1, ziel_monat.month + 10, 1)

    einheit_rows = await fetch_einheit_soll_ist(
        session,
        von_monat=check_von,
        bis_monat=ziel_monat,
    )
    abweichungen = [
        row
        for row in einheit_rows
        if row.gesamt_soll > Decimal("0.00") and row.differenz_saldo < Decimal("0.00")
    ]

    return DashboardSummary(
        anzahl_objekte=anzahl_objekte,
        anzahl_einheiten=anzahl_einheiten,
        vermietete_einheiten=vermietete_einheiten,
        leerstand_einheiten=leerstand_einheiten,
        monat_start=ziel_monat,
        monat_soll_gesamt=monat_soll_gesamt,
        monat_ist_mieteinnahmen=monat_ist_mieteinnahmen,
        monat_ausgaben_gesamt=monat_ausgaben_gesamt,
        monat_netto_cashflow=monat_netto_cashflow,
        offene_kautionen=offene_kautionen,
        soll_ist_abweichungen=abweichungen,
    )
