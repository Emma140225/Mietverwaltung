"""Stammdaten-Service für Objekte, Wohneinheiten, Mieter und Mietverträge."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import WohneinheitStatus
from app.models.konditionen import MietkonditionenHistorie
from app.models.stammdaten import Mieter, Mietvertrag, Objekt, VertragMieter, Wohneinheit
from app.schemas.stammdaten import (
    MieterCreate,
    MieterUpdate,
    MietvertragCreate,
    MietvertragUpdate,
    ObjektCreate,
    ObjektUpdate,
    VertragMieterLink,
    WohneinheitCreate,
    WohneinheitUpdate,
)
from app.services.exceptions import ConflictError, NotFoundError, ValidationError


# --- Objekte ---

async def list_objekte(session: AsyncSession) -> list[Objekt]:
    stmt = select(Objekt).order_by(Objekt.bezeichnung.asc(), Objekt.id.asc())
    return list((await session.scalars(stmt)).all())


async def get_objekt(session: AsyncSession, objekt_id: int) -> Objekt:
    objekt = await session.get(Objekt, objekt_id)
    if objekt is None:
        raise NotFoundError(f"Objekt #{objekt_id} wurde nicht gefunden.")
    return objekt


async def create_objekt(session: AsyncSession, payload: ObjektCreate) -> Objekt:
    objekt = Objekt(**payload.model_dump())
    session.add(objekt)
    await session.flush()
    await session.refresh(objekt)
    return objekt


async def update_objekt(session: AsyncSession, objekt_id: int, payload: ObjektUpdate) -> Objekt:
    objekt = await get_objekt(session, objekt_id)
    for field, value in payload.model_dump().items():
        setattr(objekt, field, value)
    await session.flush()
    await session.refresh(objekt)
    return objekt


async def delete_objekt(session: AsyncSession, objekt_id: int) -> None:
    objekt = await get_objekt(session, objekt_id)
    try:
        await session.delete(objekt)
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "Das Objekt kann nicht gelöscht werden, da noch Wohneinheiten, "
            "Buchungen oder Dokumente zugeordnet sind."
        ) from exc


# --- Wohneinheiten ---

async def list_wohneinheiten(
    session: AsyncSession,
    *,
    objekt_id: int | None = None,
) -> list[Wohneinheit]:
    stmt = (
        select(Wohneinheit)
        .options(selectinload(Wohneinheit.objekt))
        .order_by(Wohneinheit.objekt_id.asc(), Wohneinheit.bezeichnung.asc())
    )
    if objekt_id is not None:
        stmt = stmt.where(Wohneinheit.objekt_id == objekt_id)
    return list((await session.scalars(stmt)).all())


async def get_wohneinheit(session: AsyncSession, wohneinheit_id: int) -> Wohneinheit:
    stmt = (
        select(Wohneinheit)
        .options(selectinload(Wohneinheit.objekt))
        .where(Wohneinheit.id == wohneinheit_id)
    )
    einheit = await session.scalar(stmt)
    if einheit is None:
        raise NotFoundError(f"Wohneinheit #{wohneinheit_id} wurde nicht gefunden.")
    return einheit


async def create_wohneinheit(session: AsyncSession, payload: WohneinheitCreate) -> Wohneinheit:
    await get_objekt(session, payload.objekt_id)
    einheit = Wohneinheit(**payload.model_dump())
    session.add(einheit)
    await session.flush()
    await session.refresh(einheit)
    return einheit


async def update_wohneinheit(
    session: AsyncSession,
    wohneinheit_id: int,
    payload: WohneinheitUpdate,
) -> Wohneinheit:
    einheit = await get_wohneinheit(session, wohneinheit_id)
    await get_objekt(session, payload.objekt_id)
    for field, value in payload.model_dump().items():
        setattr(einheit, field, value)
    await session.flush()
    await session.refresh(einheit)
    return einheit


async def delete_wohneinheit(session: AsyncSession, wohneinheit_id: int) -> None:
    einheit = await get_wohneinheit(session, wohneinheit_id)
    try:
        await session.delete(einheit)
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "Die Wohneinheit kann nicht gelöscht werden, da noch Mietverträge "
            "oder Buchungen zugeordnet sind."
        ) from exc


# --- Mieter ---

async def list_mieter(session: AsyncSession, *, query: str | None = None) -> list[Mieter]:
    stmt = select(Mieter).order_by(Mieter.nachname.asc(), Mieter.vorname.asc())
    if query:
        pattern = f"%{query.strip()}%"
        stmt = stmt.where(
            Mieter.nachname.ilike(pattern)
            | Mieter.vorname.ilike(pattern)
            | Mieter.email.ilike(pattern)
        )
    return list((await session.scalars(stmt)).all())


async def get_mieter(session: AsyncSession, mieter_id: int) -> Mieter:
    mieter = await session.get(Mieter, mieter_id)
    if mieter is None:
        raise NotFoundError(f"Mieter #{mieter_id} wurde nicht gefunden.")
    return mieter


async def create_mieter(session: AsyncSession, payload: MieterCreate) -> Mieter:
    mieter = Mieter(**payload.model_dump())
    session.add(mieter)
    await session.flush()
    await session.refresh(mieter)
    return mieter


async def update_mieter(session: AsyncSession, mieter_id: int, payload: MieterUpdate) -> Mieter:
    mieter = await get_mieter(session, mieter_id)
    for field, value in payload.model_dump().items():
        setattr(mieter, field, value)
    await session.flush()
    await session.refresh(mieter)
    return mieter


async def delete_mieter(session: AsyncSession, mieter_id: int) -> None:
    mieter = await get_mieter(session, mieter_id)
    try:
        await session.delete(mieter)
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "Der Mieter kann nicht gelöscht werden, da er noch einem Mietvertrag zugeordnet ist."
        ) from exc


# --- Mietverträge ---

async def _validate_and_build_vertrag_mieter(
    session: AsyncSession,
    links: list[VertragMieterLink],
) -> list[VertragMieter]:
    if not links:
        raise ValidationError("Mindestens ein Mieter muss dem Mietvertrag zugeordnet werden.")

    seen_ids: set[int] = set()
    has_hauptmieter = False
    result: list[VertragMieter] = []

    for link in links:
        if link.mieter_id in seen_ids:
            raise ValidationError(f"Mieter #{link.mieter_id} wurde mehrfach angegeben.")
        seen_ids.add(link.mieter_id)
        await get_mieter(session, link.mieter_id)
        if link.hauptmieter:
            has_hauptmieter = True
        result.append(
            VertragMieter(
                mieter_id=link.mieter_id,
                hauptmieter=link.hauptmieter,
                einzugsdatum_mieter=link.einzugsdatum_mieter,
                auszugsdatum_mieter=link.auszugsdatum_mieter,
            )
        )

    if not has_hauptmieter:
        result[0].hauptmieter = True
    return result


async def list_mietvertraege(
    session: AsyncSession,
    *,
    wohneinheit_id: int | None = None,
    objekt_id: int | None = None,
) -> list[Mietvertrag]:
    stmt = (
        select(Mietvertrag)
        .join(Mietvertrag.wohneinheit)
        .options(
            selectinload(Mietvertrag.wohneinheit).selectinload(Wohneinheit.objekt),
            selectinload(Mietvertrag.mieter_zuordnungen).selectinload(VertragMieter.mieter),
            selectinload(Mietvertrag.konditionen_historie),
            selectinload(Mietvertrag.kaution),
        )
        .order_by(Mietvertrag.vertragsbeginn.desc(), Mietvertrag.id.desc())
    )
    if wohneinheit_id is not None:
        stmt = stmt.where(Mietvertrag.wohneinheit_id == wohneinheit_id)
    if objekt_id is not None:
        stmt = stmt.where(Wohneinheit.objekt_id == objekt_id)
    return list((await session.scalars(stmt)).all())


async def get_mietvertrag(session: AsyncSession, mietvertrag_id: int) -> Mietvertrag:
    stmt = (
        select(Mietvertrag)
        .options(
            selectinload(Mietvertrag.wohneinheit).selectinload(Wohneinheit.objekt),
            selectinload(Mietvertrag.mieter_zuordnungen).selectinload(VertragMieter.mieter),
            selectinload(Mietvertrag.konditionen_historie),
            selectinload(Mietvertrag.kaution),
        )
        .where(Mietvertrag.id == mietvertrag_id)
    )
    vertrag = await session.scalar(stmt)
    if vertrag is None:
        raise NotFoundError(f"Mietvertrag #{mietvertrag_id} wurde nicht gefunden.")
    return vertrag


async def create_mietvertrag(session: AsyncSession, payload: MietvertragCreate) -> Mietvertrag:
    einheit = await get_wohneinheit(session, payload.wohneinheit_id)
    mieter_links = await _validate_and_build_vertrag_mieter(session, payload.mieter)

    vertrag = Mietvertrag(
        wohneinheit_id=payload.wohneinheit_id,
        vertragsnummer=payload.vertragsnummer or None,
        vertragsbeginn=payload.vertragsbeginn,
        vertragsende=payload.vertragsende,
        kuendigungsdatum=payload.kuendigungsdatum,
        zahlungsziel_werktag=payload.zahlungsziel_werktag,
        notizen=payload.notizen,
        mieter_zuordnungen=mieter_links,
    )
    session.add(vertrag)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Vertragsnummer existiert bereits.") from exc

    # Initiale Mietkonditionen ab Vertragsbeginn anlegen
    kondition = MietkonditionenHistorie(
        mietvertrag_id=vertrag.id,
        gueltig_ab=payload.vertragsbeginn,
        gueltig_bis=payload.vertragsende,
        kaltmiete=payload.initiale_konditionen.kaltmiete,
        betriebskosten_vorauszahlung=payload.initiale_konditionen.betriebskosten_vorauszahlung,
        heizkosten_vorauszahlung=payload.initiale_konditionen.heizkosten_vorauszahlung,
        aenderungsgrund=payload.initiale_konditionen.aenderungsgrund,
    )
    session.add(kondition)

    # Bei offenem/laufendem Vertrag Status der Wohneinheit automatisch auf "vermietet" setzen
    if payload.vertragsende is None and einheit.status == WohneinheitStatus.LEERSTAND:
        einheit.status = WohneinheitStatus.VERMIETET

    await session.flush()
    return await get_mietvertrag(session, vertrag.id)


async def update_mietvertrag(
    session: AsyncSession,
    mietvertrag_id: int,
    payload: MietvertragUpdate,
) -> Mietvertrag:
    vertrag = await get_mietvertrag(session, mietvertrag_id)
    await get_wohneinheit(session, payload.wohneinheit_id)

    vertrag.wohneinheit_id = payload.wohneinheit_id
    vertrag.vertragsnummer = payload.vertragsnummer or None
    vertrag.vertragsbeginn = payload.vertragsbeginn
    vertrag.vertragsende = payload.vertragsende
    vertrag.kuendigungsdatum = payload.kuendigungsdatum
    vertrag.zahlungsziel_werktag = payload.zahlungsziel_werktag
    vertrag.notizen = payload.notizen

    if payload.mieter is not None:
        new_links = await _validate_and_build_vertrag_mieter(session, payload.mieter)
        vertrag.mieter_zuordnungen.clear()
        await session.flush()
        vertrag.mieter_zuordnungen.extend(new_links)

    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Vertragsnummer existiert bereits.") from exc

    return await get_mietvertrag(session, vertrag.id)


async def delete_mietvertrag(session: AsyncSession, mietvertrag_id: int) -> None:
    vertrag = await get_mietvertrag(session, mietvertrag_id)
    try:
        await session.delete(vertrag)
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "Der Mietvertrag kann nicht gelöscht werden, da noch Buchungen oder "
            "eine Kaution zugeordnet sind."
        ) from exc
