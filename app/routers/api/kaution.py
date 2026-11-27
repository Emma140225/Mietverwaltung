"""API-Endpunkte für getrennte Kautionsverwaltung."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.kaution_dokument import (
    KautionBewegungCreate,
    KautionBewegungRead,
    KautionCreate,
    KautionRead,
    KautionStatusUebersichtRead,
    KautionUpdate,
)
from app.services import kaution as kaution_service

router = APIRouter(tags=["Kautionsverwaltung"])


@router.get("/kautionen", response_model=list[KautionRead])
async def api_list_kautionen(
    objekt_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    return await kaution_service.list_kautionen(session, objekt_id=objekt_id)


@router.get("/kautionen/uebersicht", response_model=list[KautionStatusUebersichtRead])
async def api_list_kaution_uebersicht(
    objekt_id: int | None = Query(default=None),
    nur_offene: bool = Query(default=False),
    session: AsyncSession = Depends(get_db_session),
):
    return await kaution_service.list_kaution_uebersichten(
        session,
        objekt_id=objekt_id,
        nur_offene=nur_offene,
    )


@router.post("/kautionen", response_model=KautionRead, status_code=status.HTTP_201_CREATED)
async def api_create_kaution(
    payload: KautionCreate,
    session: AsyncSession = Depends(get_db_session),
):
    return await kaution_service.create_kaution(session, payload)


@router.get("/kautionen/{kaution_id}", response_model=KautionRead)
async def api_get_kaution(kaution_id: int, session: AsyncSession = Depends(get_db_session)):
    return await kaution_service.get_kaution(session, kaution_id)


@router.put("/kautionen/{kaution_id}", response_model=KautionRead)
async def api_update_kaution(
    kaution_id: int,
    payload: KautionUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    return await kaution_service.update_kaution(session, kaution_id, payload)


@router.post(
    "/kautionen/{kaution_id}/bewegungen",
    response_model=KautionBewegungRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_add_kaution_bewegung(
    kaution_id: int,
    payload: KautionBewegungCreate,
    session: AsyncSession = Depends(get_db_session),
):
    return await kaution_service.add_kaution_bewegung(session, kaution_id, payload)


@router.delete(
    "/kautionen/{kaution_id}/bewegungen/{bewegung_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def api_delete_kaution_bewegung(
    kaution_id: int,
    bewegung_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    await kaution_service.delete_kaution_bewegung(session, kaution_id, bewegung_id)
