"""API-Endpunkte für Stammdaten und historisierte Mietkonditionen."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.konditionen import KonditionenAnpassungRequest, MietkonditionenRead
from app.schemas.stammdaten import (
    MieterCreate,
    MieterRead,
    MieterUpdate,
    MietvertragCreate,
    MietvertragRead,
    MietvertragUpdate,
    ObjektCreate,
    ObjektRead,
    ObjektUpdate,
    WohneinheitCreate,
    WohneinheitRead,
    WohneinheitUpdate,
)
from app.services import konditionen as konditionen_service
from app.services import stammdaten as stammdaten_service

router = APIRouter(tags=["Stammdaten & Mietkonditionen"])


# --- Objekte ---

@router.get("/objekte", response_model=list[ObjektRead])
async def api_list_objekte(session: AsyncSession = Depends(get_db_session)):
    return await stammdaten_service.list_objekte(session)


@router.post("/objekte", response_model=ObjektRead, status_code=status.HTTP_201_CREATED)
async def api_create_objekt(payload: ObjektCreate, session: AsyncSession = Depends(get_db_session)):
    return await stammdaten_service.create_objekt(session, payload)


@router.get("/objekte/{objekt_id}", response_model=ObjektRead)
async def api_get_objekt(objekt_id: int, session: AsyncSession = Depends(get_db_session)):
    return await stammdaten_service.get_objekt(session, objekt_id)


@router.put("/objekte/{objekt_id}", response_model=ObjektRead)
async def api_update_objekt(
    objekt_id: int,
    payload: ObjektUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    return await stammdaten_service.update_objekt(session, objekt_id, payload)


@router.delete("/objekte/{objekt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_objekt(objekt_id: int, session: AsyncSession = Depends(get_db_session)):
    await stammdaten_service.delete_objekt(session, objekt_id)


# --- Wohneinheiten ---

@router.get("/wohneinheiten", response_model=list[WohneinheitRead])
async def api_list_wohneinheiten(
    objekt_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    return await stammdaten_service.list_wohneinheiten(session, objekt_id=objekt_id)


@router.post("/wohneinheiten", response_model=WohneinheitRead, status_code=status.HTTP_201_CREATED)
async def api_create_wohneinheit(
    payload: WohneinheitCreate,
    session: AsyncSession = Depends(get_db_session),
):
    return await stammdaten_service.create_wohneinheit(session, payload)


@router.get("/wohneinheiten/{wohneinheit_id}", response_model=WohneinheitRead)
async def api_get_wohneinheit(wohneinheit_id: int, session: AsyncSession = Depends(get_db_session)):
    return await stammdaten_service.get_wohneinheit(session, wohneinheit_id)


@router.put("/wohneinheiten/{wohneinheit_id}", response_model=WohneinheitRead)
async def api_update_wohneinheit(
    wohneinheit_id: int,
    payload: WohneinheitUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    return await stammdaten_service.update_wohneinheit(session, wohneinheit_id, payload)


@router.delete("/wohneinheiten/{wohneinheit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_wohneinheit(wohneinheit_id: int, session: AsyncSession = Depends(get_db_session)):
    await stammdaten_service.delete_wohneinheit(session, wohneinheit_id)


# --- Mieter ---

@router.get("/mieter", response_model=list[MieterRead])
async def api_list_mieter(
    q: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    return await stammdaten_service.list_mieter(session, query=q)


@router.post("/mieter", response_model=MieterRead, status_code=status.HTTP_201_CREATED)
async def api_create_mieter(payload: MieterCreate, session: AsyncSession = Depends(get_db_session)):
    return await stammdaten_service.create_mieter(session, payload)


@router.get("/mieter/{mieter_id}", response_model=MieterRead)
async def api_get_mieter(mieter_id: int, session: AsyncSession = Depends(get_db_session)):
    return await stammdaten_service.get_mieter(session, mieter_id)


@router.put("/mieter/{mieter_id}", response_model=MieterRead)
async def api_update_mieter(
    mieter_id: int,
    payload: MieterUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    return await stammdaten_service.update_mieter(session, mieter_id, payload)


@router.delete("/mieter/{mieter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_mieter(mieter_id: int, session: AsyncSession = Depends(get_db_session)):
    await stammdaten_service.delete_mieter(session, mieter_id)


# --- Mietverträge & Historisierte Mietkonditionen ---

@router.get("/mietvertraege", response_model=list[MietvertragRead])
async def api_list_mietvertraege(
    objekt_id: int | None = Query(default=None),
    wohneinheit_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    return await stammdaten_service.list_mietvertraege(
        session,
        objekt_id=objekt_id,
        wohneinheit_id=wohneinheit_id,
    )


@router.post("/mietvertraege", response_model=MietvertragRead, status_code=status.HTTP_201_CREATED)
async def api_create_mietvertrag(
    payload: MietvertragCreate,
    session: AsyncSession = Depends(get_db_session),
):
    return await stammdaten_service.create_mietvertrag(session, payload)


@router.get("/mietvertraege/{mietvertrag_id}", response_model=MietvertragRead)
async def api_get_mietvertrag(mietvertrag_id: int, session: AsyncSession = Depends(get_db_session)):
    return await stammdaten_service.get_mietvertrag(session, mietvertrag_id)


@router.put("/mietvertraege/{mietvertrag_id}", response_model=MietvertragRead)
async def api_update_mietvertrag(
    mietvertrag_id: int,
    payload: MietvertragUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    return await stammdaten_service.update_mietvertrag(session, mietvertrag_id, payload)


@router.delete("/mietvertraege/{mietvertrag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_mietvertrag(
    mietvertrag_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    await stammdaten_service.delete_mietvertrag(session, mietvertrag_id)


@router.get("/mietvertraege/{mietvertrag_id}/konditionen", response_model=list[MietkonditionenRead])
async def api_list_konditionen(
    mietvertrag_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    return await konditionen_service.list_konditionen_historie(session, mietvertrag_id)


@router.post(
    "/mietvertraege/{mietvertrag_id}/konditionen/anpassen",
    response_model=MietkonditionenRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_adjust_konditionen_stichtag(
    mietvertrag_id: int,
    payload: KonditionenAnpassungRequest,
    session: AsyncSession = Depends(get_db_session),
):
    return await konditionen_service.adjust_konditionen_zum_stichtag(
        session,
        mietvertrag_id,
        payload,
    )
