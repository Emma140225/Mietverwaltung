"""Service für die getrennte Kautionsverwaltung inkl. 3-Raten-Regelung und Statusberechnung."""

from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.models.enums import KautionAnlageform, KautionBewegungTyp, KautionStatus
from app.models.kaution import Kaution, KautionBewegung
from app.models.stammdaten import Mietvertrag, Wohneinheit
from app.schemas.kaution_dokument import (
    KautionBewegungCreate,
    KautionCreate,
    KautionStatusUebersichtRead,
    KautionUpdate,
)
from app.services.exceptions import ConflictError, NotFoundError, OptimisticLockError, ValidationError
from app.services.stammdaten import get_mietvertrag


def _recalculate_kaution_status(kaution: Kaution) -> KautionStatus:
    """Leitet den Kautionsstatus konsistent aus den gebuchten Bewegungen ab."""
    eingezahlt = sum(
        (b.betrag for b in kaution.bewegungen if b.typ == KautionBewegungTyp.EINZAHLUNG_RATE),
        Decimal("0.00"),
    )
    zinsen = sum(
        (b.betrag for b in kaution.bewegungen if b.typ == KautionBewegungTyp.ZINSGUTSCHRIFT),
        Decimal("0.00"),
    )
    abgang = sum(
        (
            b.betrag
            for b in kaution.bewegungen
            if b.typ in (KautionBewegungTyp.EINBEHALT, KautionBewegungTyp.RUECKZAHLUNG)
        ),
        Decimal("0.00"),
    )
    aktueller_bestand = eingezahlt + zinsen - abgang

    if abgang > Decimal("0.00"):
        if aktueller_bestand <= Decimal("0.00"):
            return KautionStatus.ABGERECHNET
        return KautionStatus.TEILWEISE_ZURUECKGEZAHLT

    if eingezahlt <= Decimal("0.00"):
        return KautionStatus.OFFEN
    if eingezahlt < kaution.vereinbarte_summe:
        return KautionStatus.TEILWEISE_EINGEGANGEN
    return KautionStatus.VOLLSTAENDIG


async def list_kautionen(
    session: AsyncSession,
    *,
    objekt_id: int | None = None,
) -> list[Kaution]:
    stmt = (
        select(Kaution)
        .join(Kaution.mietvertrag)
        .join(Mietvertrag.wohneinheit)
        .options(
            selectinload(Kaution.mietvertrag).selectinload(Mietvertrag.wohneinheit).selectinload(Wohneinheit.objekt),
            selectinload(Kaution.bewegungen),
        )
        .order_by(Kaution.id.desc())
    )
    if objekt_id is not None:
        stmt = stmt.where(Wohneinheit.objekt_id == objekt_id)
    return list((await session.scalars(stmt)).all())


async def list_kaution_uebersichten(
    session: AsyncSession,
    *,
    objekt_id: int | None = None,
    nur_offene: bool = False,
) -> list[KautionStatusUebersichtRead]:
    """Liest aggregierte Kautionsstände aus der PostgreSQL-View `v_kaution_status_uebersicht`."""
    sql = """
        SELECT
            kaution_id,
            mietvertrag_id,
            wohneinheit_id,
            objekt_id,
            vereinbarte_summe,
            anlageform::text AS anlageform,
            kontoreferenz,
            status::text AS status,
            eingezahlt_summe,
            zinsen_summe,
            einbehalten_summe,
            zurueckgezahlt_summe,
            aktueller_bestand,
            offene_einzahlung
        FROM v_kaution_status_uebersicht
        WHERE (CAST(:objekt_id AS integer) IS NULL OR objekt_id = CAST(:objekt_id AS integer))
          AND (:nur_offene = false OR offene_einzahlung > 0)
        ORDER BY offene_einzahlung DESC, kaution_id DESC
    """
    result = await session.execute(
        text(sql),
        {"objekt_id": objekt_id, "nur_offene": nur_offene},
    )
    rows: list[KautionStatusUebersichtRead] = []
    for mapping in result.mappings().all():
        data = dict(mapping)
        data["anlageform"] = KautionAnlageform(data["anlageform"])
        data["status"] = KautionStatus(data["status"])
        rows.append(KautionStatusUebersichtRead(**data))
    return rows


async def get_kaution(session: AsyncSession, kaution_id: int) -> Kaution:
    stmt = (
        select(Kaution)
        .options(
            selectinload(Kaution.mietvertrag).selectinload(Mietvertrag.wohneinheit).selectinload(Wohneinheit.objekt),
            selectinload(Kaution.bewegungen),
        )
        .where(Kaution.id == kaution_id)
    )
    kaution = await session.scalar(stmt)
    if kaution is None:
        raise NotFoundError(f"Kaution #{kaution_id} wurde nicht gefunden.")
    return kaution


async def create_kaution(session: AsyncSession, payload: KautionCreate) -> Kaution:
    await get_mietvertrag(session, payload.mietvertrag_id)
    initial_status = (
        KautionStatus.VOLLSTAENDIG if payload.vereinbarte_summe == Decimal("0") else KautionStatus.OFFEN
    )
    kaution = Kaution(
        mietvertrag_id=payload.mietvertrag_id,
        vereinbarte_summe=payload.vereinbarte_summe,
        anlageform=payload.anlageform,
        kontoreferenz=payload.kontoreferenz,
        status=initial_status,
        notizen=payload.notizen,
    )
    session.add(kaution)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            f"Für Mietvertrag #{payload.mietvertrag_id} existiert bereits ein Kautionskonto."
        ) from exc
    return await get_kaution(session, kaution.id)


async def update_kaution(
    session: AsyncSession,
    kaution_id: int,
    payload: KautionUpdate,
) -> Kaution:
    kaution = await get_kaution(session, kaution_id)
    if kaution.version != payload.version:
        raise OptimisticLockError(
            f"Kaution #{kaution_id} wurde zwischenzeitlich von einem anderen Client geändert."
        )

    kaution.vereinbarte_summe = payload.vereinbarte_summe
    kaution.anlageform = payload.anlageform
    kaution.kontoreferenz = payload.kontoreferenz
    kaution.notizen = payload.notizen
    if payload.status is not None:
        kaution.status = payload.status
    else:
        kaution.status = _recalculate_kaution_status(kaution)

    try:
        await session.flush()
    except StaleDataError as exc:
        raise OptimisticLockError(
            f"Kaution #{kaution_id} wurde parallel aktualisiert."
        ) from exc

    return await get_kaution(session, kaution.id)


async def add_kaution_bewegung(
    session: AsyncSession,
    kaution_id: int,
    payload: KautionBewegungCreate,
) -> KautionBewegung:
    kaution = await get_kaution(session, kaution_id)

    if payload.rate_nummer is not None:
        existing_rates = {
            b.rate_nummer
            for b in kaution.bewegungen
            if b.typ == KautionBewegungTyp.EINZAHLUNG_RATE and b.rate_nummer is not None
        }
        if payload.rate_nummer in existing_rates:
            raise ConflictError(
                f"Einzahlungsrate {payload.rate_nummer} wurde für diese Kaution bereits gebucht."
            )

    if payload.typ in (KautionBewegungTyp.EINBEHALT, KautionBewegungTyp.RUECKZAHLUNG):
        aktueller_bestand = sum(
            (
                b.betrag
                for b in kaution.bewegungen
                if b.typ in (KautionBewegungTyp.EINZAHLUNG_RATE, KautionBewegungTyp.ZINSGUTSCHRIFT)
            ),
            Decimal("0.00"),
        ) - sum(
            (
                b.betrag
                for b in kaution.bewegungen
                if b.typ in (KautionBewegungTyp.EINBEHALT, KautionBewegungTyp.RUECKZAHLUNG)
            ),
            Decimal("0.00"),
        )
        if payload.betrag > aktueller_bestand:
            raise ValidationError(
                f"Der Betrag ({payload.betrag:.2f} EUR) übersteigt den aktuellen "
                f"Kautionsbestand ({aktueller_bestand:.2f} EUR)."
            )

    bewegung = KautionBewegung(
        kaution_id=kaution_id,
        datum=payload.datum,
        typ=payload.typ,
        betrag=payload.betrag,
        rate_nummer=payload.rate_nummer,
        bemerkung=payload.bemerkung,
    )
    kaution.bewegungen.append(bewegung)
    kaution.status = _recalculate_kaution_status(kaution)

    await session.flush()
    await session.refresh(bewegung)
    return bewegung


async def delete_kaution_bewegung(
    session: AsyncSession,
    kaution_id: int,
    bewegung_id: int,
) -> None:
    kaution = await get_kaution(session, kaution_id)
    target = next((b for b in kaution.bewegungen if b.id == bewegung_id), None)
    if target is None:
        raise NotFoundError(f"Kautionsbewegung #{bewegung_id} wurde nicht gefunden.")

    kaution.bewegungen.remove(target)
    await session.delete(target)
    kaution.status = _recalculate_kaution_status(kaution)
    await session.flush()
