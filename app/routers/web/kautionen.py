"""Web-Router für die getrennte Kautionsverwaltung."""

from datetime import date

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.templating import templates
from app.models.enums import KautionAnlageform, KautionBewegungTyp
from app.routers.web.helpers import (
    flash_context,
    opt_date,
    opt_int,
    opt_str,
    parse_decimal,
    redirect_with_flash,
)
from app.schemas.kaution_dokument import KautionBewegungCreate, KautionCreate
from app.services import kaution as kaution_service
from app.services import stammdaten as stammdaten_service
from app.services.exceptions import DomainError

router = APIRouter(tags=["Web-Kautionen"])


@router.get("/kautionen", response_class=HTMLResponse)
async def view_kautionen(
    request: Request,
    mietvertrag_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    kautionen = await kaution_service.list_kaution_uebersichten(session)
    vertraege = await stammdaten_service.list_mietvertraege(session)
    vertraege_ohne_kaution = [v for v in vertraege if v.kaution is None]

    return templates.TemplateResponse(
        request=request,
        name="kautionen/index.html",
        context={
            "active_nav": "kautionen",
            "kautionen": kautionen,
            "vertraege_ohne_kaution": vertraege_ohne_kaution,
            "anlageformen": list(KautionAnlageform),
            "preselect_vertrag_id": mietvertrag_id,
            **flash_context(request),
        },
    )


@router.post("/kautionen")
async def web_create_kaution(
    mietvertrag_id: int = Form(...),
    vereinbarte_summe: str = Form(...),
    anlageform: KautionAnlageform = Form(...),
    kontoreferenz: str | None = Form(default=None),
    notizen: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        payload = KautionCreate(
            mietvertrag_id=mietvertrag_id,
            vereinbarte_summe=parse_decimal(vereinbarte_summe, field_name="Vereinbarte Summe"),
            anlageform=anlageform,
            kontoreferenz=opt_str(kontoreferenz),
            notizen=opt_str(notizen),
        )
        kaution = await kaution_service.create_kaution(session, payload)
        return redirect_with_flash(f"/kautionen/{kaution.id}", ok="Kautionskonto angelegt.")
    except (DomainError, ValueError) as exc:
        return redirect_with_flash("/kautionen", err=getattr(exc, "message", str(exc)))


@router.get("/kautionen/{kaution_id}", response_class=HTMLResponse)
async def view_kaution_detail(
    request: Request,
    kaution_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    kaution = await kaution_service.get_kaution(session, kaution_id)
    uebersichten = await kaution_service.list_kaution_uebersichten(session)
    uebersicht = next(u for u in uebersichten if u.kaution_id == kaution_id)

    return templates.TemplateResponse(
        request=request,
        name="kautionen/detail.html",
        context={
            "active_nav": "kautionen",
            "kaution": kaution,
            "uebersicht": uebersicht,
            "heute": date.today(),
            **flash_context(request),
        },
    )


@router.post("/kautionen/{kaution_id}/bewegungen")
async def web_add_kaution_bewegung(
    kaution_id: int,
    datum: str = Form(...),
    typ: KautionBewegungTyp = Form(...),
    betrag: str = Form(...),
    rate_nummer: str | None = Form(default=None),
    bemerkung: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        datum_val = opt_date(datum)
        if datum_val is None:
            raise ValueError("Datum ist erforderlich.")
        payload = KautionBewegungCreate(
            datum=datum_val,
            typ=typ,
            betrag=parse_decimal(betrag, field_name="Betrag"),
            rate_nummer=opt_int(rate_nummer),
            bemerkung=opt_str(bemerkung),
        )
        await kaution_service.add_kaution_bewegung(session, kaution_id, payload)
        return redirect_with_flash(f"/kautionen/{kaution_id}", ok="Kautionsbewegung gebucht.")
    except (DomainError, ValueError) as exc:
        return redirect_with_flash(f"/kautionen/{kaution_id}", err=getattr(exc, "message", str(exc)))


@router.post("/kautionen/{kaution_id}/bewegungen/{bewegung_id}/delete")
async def web_delete_kaution_bewegung(
    kaution_id: int,
    bewegung_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        await kaution_service.delete_kaution_bewegung(session, kaution_id, bewegung_id)
        return redirect_with_flash(f"/kautionen/{kaution_id}", ok="Kautionsbewegung gelöscht.")
    except DomainError as exc:
        return redirect_with_flash(f"/kautionen/{kaution_id}", err=exc.message)
