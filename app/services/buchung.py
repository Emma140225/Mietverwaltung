"""Service für Kostenarten-Katalog und manuelle Buchungen inkl. Optimistic Locking."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.models.enums import Buchungsrichtung
from app.models.finanzen import Buchung, Kostenart
from app.schemas.finanzen import BuchungCreate, BuchungUpdate, KostenartCreate, KostenartUpdate
from app.services.exceptions import ConflictError, NotFoundError, OptimisticLockError, ValidationError
from app.services.stammdaten import get_mietvertrag, get_objekt, get_wohneinheit


# --- Kostenarten-Katalog ---

async def list_kostenarten(
    session: AsyncSession,
    *,
    nur_aktive: bool = False,
    richtung: Buchungsrichtung | None = None,
) -> list[Kostenart]:
    stmt = select(Kostenart).order_by(Kostenart.sortierung.asc(), Kostenart.name.asc())
    if nur_aktive:
        stmt = stmt.where(Kostenart.aktiv.is_(True))
    if richtung is not None:
        stmt = stmt.where(Kostenart.richtung == richtung)
    return list((await session.scalars(stmt)).all())


async def get_kostenart(session: AsyncSession, kostenart_id: int) -> Kostenart:
    kostenart = await session.get(Kostenart, kostenart_id)
    if kostenart is None:
        raise NotFoundError(f"Kostenart #{kostenart_id} wurde nicht gefunden.")
    return kostenart


async def create_kostenart(session: AsyncSession, payload: KostenartCreate) -> Kostenart:
    kostenart = Kostenart(**payload.model_dump())
    session.add(kostenart)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(f"Eine Kostenart mit dem Namen '{payload.name}' existiert bereits.") from exc
    await session.refresh(kostenart)
    return kostenart


async def update_kostenart(
    session: AsyncSession,
    kostenart_id: int,
    payload: KostenartUpdate,
) -> Kostenart:
    kostenart = await get_kostenart(session, kostenart_id)
    for field, value in payload.model_dump().items():
        setattr(kostenart, field, value)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(f"Eine Kostenart mit dem Namen '{payload.name}' existiert bereits.") from exc
    await session.refresh(kostenart)
    return kostenart


# --- Buchungen ---

async def _validate_buchung_relations(
    session: AsyncSession,
    *,
    objekt_id: int,
    wohneinheit_id: int | None,
    mietvertrag_id: int | None,
    kostenart_id: int,
) -> int | None:
    """Prüft relationale Konsistenz und ergänzt bei Bedarf `wohneinheit_id` aus `mietvertrag`."""
    await get_objekt(session, objekt_id)
    await get_kostenart(session, kostenart_id)

    resolved_einheit_id = wohneinheit_id
    if mietvertrag_id is not None:
        vertrag = await get_mietvertrag(session, mietvertrag_id)
        if vertrag.wohneinheit.objekt_id != objekt_id:
            raise ValidationError(
                "Der gewählte Mietvertrag gehört nicht zum ausgewählten Objekt."
            )
        if resolved_einheit_id is None:
            resolved_einheit_id = vertrag.wohneinheit_id
        elif resolved_einheit_id != vertrag.wohneinheit_id:
            raise ValidationError(
                "Der gewählte Mietvertrag gehört nicht zur ausgewählten Wohneinheit."
            )

    if resolved_einheit_id is not None:
        einheit = await get_wohneinheit(session, resolved_einheit_id)
        if einheit.objekt_id != objekt_id:
            raise ValidationError(
                "Die gewählte Wohneinheit gehört nicht zum ausgewählten Objekt."
            )

    return resolved_einheit_id


async def list_buchungen(
    session: AsyncSession,
    *,
    objekt_id: int | None = None,
    wohneinheit_id: int | None = None,
    kostenart_id: int | None = None,
    von_datum: date | None = None,
    bis_datum: date | None = None,
    umlagefaehig: bool | None = None,
    limit: int = 200,
) -> list[Buchung]:
    stmt = (
        select(Buchung)
        .join(Buchung.kostenart)
        .options(
            selectinload(Buchung.objekt),
            selectinload(Buchung.wohneinheit),
            selectinload(Buchung.mietvertrag),
            selectinload(Buchung.kostenart),
            selectinload(Buchung.dokumente),
        )
        .order_by(Buchung.buchungsdatum.desc(), Buchung.id.desc())
        .limit(limit)
    )
    if objekt_id is not None:
        stmt = stmt.where(Buchung.objekt_id == objekt_id)
    if wohneinheit_id is not None:
        stmt = stmt.where(Buchung.wohneinheit_id == wohneinheit_id)
    if kostenart_id is not None:
        stmt = stmt.where(Buchung.kostenart_id == kostenart_id)
    if von_datum is not None:
        stmt = stmt.where(Buchung.buchungsdatum >= von_datum)
    if bis_datum is not None:
        stmt = stmt.where(Buchung.buchungsdatum <= bis_datum)
    if umlagefaehig is not None:
        stmt = stmt.where(Kostenart.umlagefaehig.is_(umlagefaehig))

    return list((await session.scalars(stmt)).all())


async def get_buchung(session: AsyncSession, buchung_id: int) -> Buchung:
    stmt = (
        select(Buchung)
        .options(
            selectinload(Buchung.objekt),
            selectinload(Buchung.wohneinheit),
            selectinload(Buchung.mietvertrag),
            selectinload(Buchung.kostenart),
            selectinload(Buchung.dokumente),
        )
        .where(Buchung.id == buchung_id)
    )
    buchung = await session.scalar(stmt)
    if buchung is None:
        raise NotFoundError(f"Buchung #{buchung_id} wurde nicht gefunden.")
    return buchung


async def create_buchung(session: AsyncSession, payload: BuchungCreate) -> Buchung:
    resolved_einheit_id = await _validate_buchung_relations(
        session,
        objekt_id=payload.objekt_id,
        wohneinheit_id=payload.wohneinheit_id,
        mietvertrag_id=payload.mietvertrag_id,
        kostenart_id=payload.kostenart_id,
    )
    data = payload.model_dump()
    data["wohneinheit_id"] = resolved_einheit_id

    buchung = Buchung(**data)
    session.add(buchung)
    await session.flush()
    return await get_buchung(session, buchung.id)


async def update_buchung(
    session: AsyncSession,
    buchung_id: int,
    payload: BuchungUpdate,
) -> Buchung:
    buchung = await get_buchung(session, buchung_id)

    # Explizite Optimistic-Locking-Prüfung vor Änderung
    if buchung.version != payload.version:
        raise OptimisticLockError(
            f"Buchung #{buchung_id} wurde zwischenzeitlich von einem anderen Client geändert "
            f"(erwartete Version {payload.version}, aktuell {buchung.version}). "
            "Bitte laden Sie den Datensatz neu."
        )

    resolved_einheit_id = await _validate_buchung_relations(
        session,
        objekt_id=payload.objekt_id,
        wohneinheit_id=payload.wohneinheit_id,
        mietvertrag_id=payload.mietvertrag_id,
        kostenart_id=payload.kostenart_id,
    )

    update_data = payload.model_dump(exclude={"version"})
    update_data["wohneinheit_id"] = resolved_einheit_id
    for field, value in update_data.items():
        setattr(buchung, field, value)

    try:
        await session.flush()
    except StaleDataError as exc:
        raise OptimisticLockError(
            f"Buchung #{buchung_id} wurde parallel von einem anderen Client aktualisiert."
        ) from exc

    return await get_buchung(session, buchung.id)


async def delete_buchung(session: AsyncSession, buchung_id: int) -> None:
    buchung = await get_buchung(session, buchung_id)
    await session.delete(buchung)
    await session.flush()
