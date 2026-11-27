"""API-Endpunkte für Kostenarten-Katalog und manuelle Buchungen."""

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.enums import Buchungsrichtung
from app.schemas.finanzen import (
    BuchungCreate,
    BuchungRead,
    BuchungUpdate,
    KostenartCreate,
    KostenartRead,
    KostenartUpdate,
)
from app.services import buchung as buchung_service

router = APIRouter(tags=["Finanzen & Buchungen"])


# --- Kostenarten ---

@router.get("/kostenarten", response_model=list[KostenartRead])
async def api_list_kostenarten(
    nur_aktive: bool = Query(default=False),
    richtung: Buchungsrichtung | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    return await buchung_service.list_kostenarten(
        session,
        nur_aktive=nur_aktive,
        richtung=richtung,
    )


@router.post("/kostenarten", response_model=KostenartRead, status_code=status.HTTP_201_CREATED)
async def api_create_kostenart(
    payload: KostenartCreate,
    session: AsyncSession = Depends(get_db_session),
):
    return await buchung_service.create_kostenart(session, payload)


@router.put("/kostenarten/{kostenart_id}", response_model=KostenartRead)
async def api_update_kostenart(
    kostenart_id: int,
    payload: KostenartUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    return await buchung_service.update_kostenart(session, kostenart_id, payload)


# --- Buchungen ---

@router.get("/buchungen", response_model=list[BuchungRead])
async def api_list_buchungen(
    objekt_id: int | None = Query(default=None),
    wohneinheit_id: int | None = Query(default=None),
    kostenart_id: int | None = Query(default=None),
    von_datum: date | None = Query(default=None),
    bis_datum: date | None = Query(default=None),
    umlagefaehig: bool | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    session: AsyncSession = Depends(get_db_session),
):
    return await buchung_service.list_buchungen(
        session,
        objekt_id=objekt_id,
        wohneinheit_id=wohneinheit_id,
        kostenart_id=kostenart_id,
        von_datum=von_datum,
        bis_datum=bis_datum,
        umlagefaehig=umlagefaehig,
        limit=limit,
    )


@router.post("/buchungen", response_model=BuchungRead, status_code=status.HTTP_201_CREATED)
async def api_create_buchung(
    payload: BuchungCreate,
    session: AsyncSession = Depends(get_db_session),
):
    return await buchung_service.create_buchung(session, payload)


@router.get("/buchungen/{buchung_id}", response_model=BuchungRead)
async def api_get_buchung(buchung_id: int, session: AsyncSession = Depends(get_db_session)):
    return await buchung_service.get_buchung(session, buchung_id)


@router.put("/buchungen/{buchung_id}", response_model=BuchungRead)
async def api_update_buchung(
    buchung_id: int,
    payload: BuchungUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    return await buchung_service.update_buchung(session, buchung_id, payload)


@router.delete("/buchungen/{buchung_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_buchung(buchung_id: int, session: AsyncSession = Depends(get_db_session)):
    await buchung_service.delete_buchung(session, buchung_id)
