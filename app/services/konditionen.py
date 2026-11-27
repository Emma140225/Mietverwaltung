"""Service für historisierte Miet- und Abschlagsänderungen zum Stichtag."""

from datetime import date, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.konditionen import MietkonditionenHistorie
from app.schemas.konditionen import KonditionenAnpassungRequest
from app.services.exceptions import ConflictError, ValidationError
from app.services.stammdaten import get_mietvertrag


async def list_konditionen_historie(
    session: AsyncSession,
    mietvertrag_id: int,
) -> list[MietkonditionenHistorie]:
    """Listet alle Konditionenzeiträume eines Mietvertrags chronologisch auf."""
    await get_mietvertrag(session, mietvertrag_id)
    stmt = (
        select(MietkonditionenHistorie)
        .where(MietkonditionenHistorie.mietvertrag_id == mietvertrag_id)
        .order_by(MietkonditionenHistorie.gueltig_ab.asc())
    )
    return list((await session.scalars(stmt)).all())


async def get_aktuelle_kondition(
    session: AsyncSession,
    mietvertrag_id: int,
    *,
    stichtag: date | None = None,
) -> MietkonditionenHistorie | None:
    """Ermittelt die am angegebenen Stichtag (Standard: heute) gültigen Konditionen."""
    ref_date = stichtag or date.today()
    stmt = (
        select(MietkonditionenHistorie)
        .where(
            MietkonditionenHistorie.mietvertrag_id == mietvertrag_id,
            MietkonditionenHistorie.gueltig_ab <= ref_date,
            or_(
                MietkonditionenHistorie.gueltig_bis.is_(None),
                MietkonditionenHistorie.gueltig_bis >= ref_date,
            ),
        )
        .limit(1)
    )
    return await session.scalar(stmt)


async def adjust_konditionen_zum_stichtag(
    session: AsyncSession,
    mietvertrag_id: int,
    payload: KonditionenAnpassungRequest,
) -> MietkonditionenHistorie:
    """Passt Miete und Vorauszahlungen sauber zum Stichtag an.

    Ablauf innerhalb derselben Transaktion:
    1. Prüft Vertragsgrenzen (`vertragsbeginn` / `vertragsende`).
    2. Prüft, dass keine bereits geplante künftige Konditionsänderung nach dem Stichtag kollidiert.
    3. Schließt den bisher am Stichtag aktiven Eintrag automatisch zum Vortag (`stichtag - 1 Tag`)
       und führt `flush()` aus, damit der PostgreSQL GiST-EXCLUDE-Constraint beim anschließenden
       INSERT erfüllt bleibt.
    4. Legt den neuen Historieneintrag ab `stichtag` an (mit dem bisherigen `gueltig_bis`).
    """
    vertrag = await get_mietvertrag(session, mietvertrag_id)
    stichtag = payload.stichtag

    if stichtag < vertrag.vertragsbeginn:
        raise ValidationError(
            f"Der Stichtag ({stichtag.isoformat()}) liegt vor dem Vertragsbeginn "
            f"({vertrag.vertragsbeginn.isoformat()})."
        )
    if vertrag.vertragsende is not None and stichtag > vertrag.vertragsende:
        raise ValidationError(
            f"Der Stichtag ({stichtag.isoformat()}) liegt nach dem Vertragsende "
            f"({vertrag.vertragsende.isoformat()})."
        )

    # Künftige Änderungen ab/nach dem Stichtag prüfen
    future_stmt = (
        select(MietkonditionenHistorie)
        .where(
            MietkonditionenHistorie.mietvertrag_id == mietvertrag_id,
            MietkonditionenHistorie.gueltig_ab >= stichtag,
        )
        .order_by(MietkonditionenHistorie.gueltig_ab.asc())
        .limit(1)
    )
    future_entry = await session.scalar(future_stmt)
    if future_entry is not None:
        if future_entry.gueltig_ab == stichtag:
            raise ConflictError(
                f"Zum Stichtag {stichtag.isoformat()} existiert bereits ein Historieneintrag."
            )
        raise ConflictError(
            f"Es existiert bereits eine spätere Konditionsänderung ab "
            f"{future_entry.gueltig_ab.isoformat()}. Bitte wählen Sie ein Datum danach."
        )

    # Aktiven Eintrag am Stichtag finden und zum Vortag schließen
    active_stmt = select(MietkonditionenHistorie).where(
        and_(
            MietkonditionenHistorie.mietvertrag_id == mietvertrag_id,
            MietkonditionenHistorie.gueltig_ab < stichtag,
            or_(
                MietkonditionenHistorie.gueltig_bis.is_(None),
                MietkonditionenHistorie.gueltig_bis >= stichtag,
            ),
        )
    )
    previous_entry = await session.scalar(active_stmt)

    neues_gueltig_bis = vertrag.vertragsende
    if previous_entry is not None:
        neues_gueltig_bis = previous_entry.gueltig_bis
        previous_entry.gueltig_bis = stichtag - timedelta(days=1)
        # Wichtig: UPDATE zuerst flushen, bevor der neue Zeitraum eingefügt wird (GiST-Constraint)
        await session.flush()

    neuer_eintrag = MietkonditionenHistorie(
        mietvertrag_id=mietvertrag_id,
        gueltig_ab=stichtag,
        gueltig_bis=neues_gueltig_bis,
        kaltmiete=payload.kaltmiete,
        betriebskosten_vorauszahlung=payload.betriebskosten_vorauszahlung,
        heizkosten_vorauszahlung=payload.heizkosten_vorauszahlung,
        aenderungsgrund=payload.aenderungsgrund,
    )
    session.add(neuer_eintrag)

    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "Der Zeitraum überschneidet sich mit bestehenden Mietkonditionen."
        ) from exc

    await session.refresh(neuer_eintrag)
    return neuer_eintrag
