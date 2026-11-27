"""Web-Router für Buchungsmaske, Buchungsjournal und Kostenarten-Katalog."""

from datetime import date
import json

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.templating import templates
from app.models.enums import Buchungsrichtung, DokumentKategorie, Verteilerschluessel
from app.routers.web.helpers import (
    flash_context,
    opt_date,
    opt_int,
    opt_str,
    parse_decimal,
    redirect_with_flash,
)
from app.schemas.finanzen import BuchungCreate, BuchungUpdate, KostenartCreate
from app.services import buchung as buchung_service
from app.services import dokument as dokument_service
from app.services import stammdaten as stammdaten_service
from app.services.exceptions import DomainError

router = APIRouter(tags=["Web-Buchungen & Kostenarten"])


@router.get("/buchungen", response_class=HTMLResponse)
async def view_buchungen(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    objekte = await stammdaten_service.list_objekte(session)
    einheiten = await stammdaten_service.list_wohneinheiten(session)
    vertraege = await stammdaten_service.list_mietvertraege(session)
    kostenarten = await buchung_service.list_kostenarten(session, nur_aktive=True)
    buchungen = await buchung_service.list_buchungen(session, limit=200)

    einheiten_json = json.dumps(
        [
            {
                "id": e.id,
                "objekt_id": e.objekt_id,
                "label": f"{e.objekt.bezeichnung} · {e.bezeichnung}",
            }
            for e in einheiten
        ]
    )
    vertraege_json = json.dumps(
        [
            {
                "id": v.id,
                "objekt_id": v.wohneinheit.objekt_id,
                "wohneinheit_id": v.wohneinheit_id,
                "label": (
                    f"#{v.id} · {v.wohneinheit.bezeichnung} ("
                    + ", ".join(vm.mieter.nachname for vm in v.mieter_zuordnungen)
                    + ")"
                ),
            }
            for v in vertraege
        ]
    )

    return templates.TemplateResponse(
        request=request,
        name="buchungen/index.html",
        context={
            "active_nav": "buchungen",
            "objekte": objekte,
            "einheiten_json": einheiten_json,
            "vertraege_json": vertraege_json,
            "kostenarten": kostenarten,
            "buchungen": buchungen,
            "heute": date.today(),
            **flash_context(request),
        },
    )


@router.get("/buchungen/tabelle", response_class=HTMLResponse)
async def view_buchungen_tabelle_partial(
    request: Request,
    objekt_id: str | None = Query(default=None),
    umlagefaehig: str | None = Query(default=None),
    von_datum: str | None = Query(default=None),
    bis_datum: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    umlage_filter: bool | None = None
    if umlagefaehig == "true":
        umlage_filter = True
    elif umlagefaehig == "false":
        umlage_filter = False

    buchungen = await buchung_service.list_buchungen(
        session,
        objekt_id=opt_int(objekt_id),
        umlagefaehig=umlage_filter,
        von_datum=opt_date(von_datum),
        bis_datum=opt_date(bis_datum),
        limit=300,
    )
    return templates.TemplateResponse(
        request=request,
        name="buchungen/partials/tabelle.html",
        context={"buchungen": buchungen},
    )


@router.post("/buchungen")
async def web_create_buchung(
    objekt_id: int = Form(...),
    wohneinheit_id: str | None = Form(default=None),
    mietvertrag_id: str | None = Form(default=None),
    kostenart_id: int = Form(...),
    buchungsdatum: str = Form(...),
    leistungszeitraum_von: str | None = Form(default=None),
    leistungszeitraum_bis: str | None = Form(default=None),
    betrag: str = Form(...),
    empfaenger_sender: str = Form(...),
    verwendungszweck: str = Form(...),
    ist_sonderzahlung: bool = Form(default=False),
    belegnummer: str | None = Form(default=None),
    notizen: str | None = Form(default=None),
    beleg_pdf: UploadFile | None = File(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        datum = opt_date(buchungsdatum)
        if datum is None:
            raise ValueError("Buchungsdatum ist erforderlich.")

        payload = BuchungCreate(
            objekt_id=objekt_id,
            wohneinheit_id=opt_int(wohneinheit_id),
            mietvertrag_id=opt_int(mietvertrag_id),
            kostenart_id=kostenart_id,
            buchungsdatum=datum,
            leistungszeitraum_von=opt_date(leistungszeitraum_von),
            leistungszeitraum_bis=opt_date(leistungszeitraum_bis),
            betrag=parse_decimal(betrag, field_name="Betrag"),
            empfaenger_sender=empfaenger_sender,
            verwendungszweck=verwendungszweck,
            ist_sonderzahlung=ist_sonderzahlung,
            belegnummer=opt_str(belegnummer),
            notizen=opt_str(notizen),
        )
        buchung = await buchung_service.create_buchung(session, payload)

        # Optional direkt hochgeladene PDF-Rechnung verknüpfen
        if beleg_pdf is not None and beleg_pdf.filename:
            await dokument_service.upload_pdf_dokument(
                session,
                file=beleg_pdf,
                objekt_id=buchung.objekt_id,
                jahr=buchung.buchungsdatum.year,
                kategorie=DokumentKategorie.BELEG_RECHNUNG,
                wohneinheit_id=buchung.wohneinheit_id,
                mietvertrag_id=buchung.mietvertrag_id,
                buchung_id=buchung.id,
                beschreibung=f"Beleg zu Buchung #{buchung.id}: {buchung.verwendungszweck}",
            )

        return redirect_with_flash("/buchungen", ok=f"Buchung #{buchung.id} gespeichert.")
    except (DomainError, ValueError) as exc:
        return redirect_with_flash("/buchungen", err=getattr(exc, "message", str(exc)))


@router.post("/buchungen/{buchung_id}/update")
async def web_update_buchung(
    buchung_id: int,
    version: int = Form(...),
    objekt_id: int = Form(...),
    wohneinheit_id: str | None = Form(default=None),
    mietvertrag_id: str | None = Form(default=None),
    kostenart_id: int = Form(...),
    buchungsdatum: str = Form(...),
    leistungszeitraum_von: str | None = Form(default=None),
    leistungszeitraum_bis: str | None = Form(default=None),
    betrag: str = Form(...),
    empfaenger_sender: str = Form(...),
    verwendungszweck: str = Form(...),
    ist_sonderzahlung: bool = Form(default=False),
    belegnummer: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        datum = opt_date(buchungsdatum)
        if datum is None:
            raise ValueError("Buchungsdatum ist erforderlich.")
        payload = BuchungUpdate(
            version=version,
            objekt_id=objekt_id,
            wohneinheit_id=opt_int(wohneinheit_id),
            mietvertrag_id=opt_int(mietvertrag_id),
            kostenart_id=kostenart_id,
            buchungsdatum=datum,
            leistungszeitraum_von=opt_date(leistungszeitraum_von),
            leistungszeitraum_bis=opt_date(leistungszeitraum_bis),
            betrag=parse_decimal(betrag, field_name="Betrag"),
            empfaenger_sender=empfaenger_sender,
            verwendungszweck=verwendungszweck,
            ist_sonderzahlung=ist_sonderzahlung,
            belegnummer=opt_str(belegnummer),
        )
        await buchung_service.update_buchung(session, buchung_id, payload)
        return redirect_with_flash("/buchungen", ok=f"Buchung #{buchung_id} aktualisiert.")
    except (DomainError, ValueError) as exc:
        return redirect_with_flash("/buchungen", err=getattr(exc, "message", str(exc)))


@router.post("/buchungen/{buchung_id}/delete")
async def web_delete_buchung(
    buchung_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        await buchung_service.delete_buchung(session, buchung_id)
        return redirect_with_flash("/buchungen", ok=f"Buchung #{buchung_id} gelöscht.")
    except DomainError as exc:
        return redirect_with_flash("/buchungen", err=exc.message)


# --- Kostenarten ---

@router.get("/kostenarten", response_class=HTMLResponse)
async def view_kostenarten(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    kostenarten = await buchung_service.list_kostenarten(session)
    return templates.TemplateResponse(
        request=request,
        name="kostenarten/index.html",
        context={
            "active_nav": "kostenarten",
            "kostenarten": kostenarten,
            "verteilerschluessel_liste": list(Verteilerschluessel),
            **flash_context(request),
        },
    )


@router.post("/kostenarten")
async def web_create_kostenart(
    name: str = Form(...),
    richtung: Buchungsrichtung = Form(...),
    umlagefaehig: bool = Form(default=False),
    standard_verteilerschluessel: Verteilerschluessel = Form(default=Verteilerschluessel.KEINER),
    betrkv_ziffer: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        payload = KostenartCreate(
            name=name,
            richtung=richtung,
            umlagefaehig=umlagefaehig,
            standard_verteilerschluessel=standard_verteilerschluessel,
            betrkv_ziffer=opt_str(betrkv_ziffer),
        )
        await buchung_service.create_kostenart(session, payload)
        return redirect_with_flash("/kostenarten", ok="Kostenart angelegt.")
    except (DomainError, ValueError) as exc:
        return redirect_with_flash("/kostenarten", err=getattr(exc, "message", str(exc)))
