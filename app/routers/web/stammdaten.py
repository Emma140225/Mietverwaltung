"""Web-Router für Stammdaten (Objekte, Wohneinheiten, Mieter, Mietverträge & Stichtag)."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.templating import templates
from app.models.enums import WohneinheitStatus
from app.routers.web.helpers import (
    flash_context,
    opt_date,
    opt_int,
    opt_str,
    parse_decimal,
    redirect_with_flash,
)
from app.schemas.konditionen import KonditionenAnpassungRequest
from app.schemas.stammdaten import (
    KonditionenInitialInput,
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
from app.services import dokument as dokument_service
from app.services import konditionen as konditionen_service
from app.services import stammdaten as stammdaten_service
from app.services.exceptions import DomainError

router = APIRouter(tags=["Web-Stammdaten"])


@router.get("/stammdaten", response_class=HTMLResponse)
async def view_stammdaten(
    request: Request,
    tab: str = "mieter",
    session: AsyncSession = Depends(get_db_session),
):
    objekte = await stammdaten_service.list_objekte(session)
    einheiten = await stammdaten_service.list_wohneinheiten(session)
    mieter = await stammdaten_service.list_mieter(session)
    vertraege = await stammdaten_service.list_mietvertraege(session)

    return templates.TemplateResponse(
        request=request,
        name="stammdaten/index.html",
        context={
            "active_nav": "stammdaten",
            "active_tab": tab,
            "objekte": objekte,
            "einheiten": einheiten,
            "mieter": mieter,
            "vertraege": vertraege,
            "wohneinheit_status_liste": list(WohneinheitStatus),
            **flash_context(request),
        },
    )


# --- Objekte ---

@router.post("/objekte")
async def web_create_objekt(
    bezeichnung: str = Form(...),
    strasse: str = Form(...),
    plz: str = Form(...),
    ort: str = Form(...),
    baujahr: str | None = Form(default=None),
    gesamtflaeche_qm: str = Form(...),
    notizen: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        payload = ObjektCreate(
            bezeichnung=bezeichnung,
            strasse=strasse,
            plz=plz,
            ort=ort,
            baujahr=opt_int(baujahr),
            gesamtflaeche_qm=parse_decimal(gesamtflaeche_qm, field_name="Gesamtfläche"),
            notizen=opt_str(notizen),
        )
        await stammdaten_service.create_objekt(session, payload)
        return redirect_with_flash("/stammdaten", ok="Objekt angelegt.", extra_params={"tab": "objekte"})
    except (DomainError, ValueError) as exc:
        return redirect_with_flash("/stammdaten", err=str(exc), extra_params={"tab": "objekte"})


@router.post("/objekte/{objekt_id}/update")
async def web_update_objekt(
    objekt_id: int,
    bezeichnung: str = Form(...),
    strasse: str = Form(...),
    plz: str = Form(...),
    ort: str = Form(...),
    baujahr: str | None = Form(default=None),
    gesamtflaeche_qm: str = Form(...),
    notizen: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        payload = ObjektUpdate(
            bezeichnung=bezeichnung,
            strasse=strasse,
            plz=plz,
            ort=ort,
            baujahr=opt_int(baujahr),
            gesamtflaeche_qm=parse_decimal(gesamtflaeche_qm, field_name="Gesamtfläche"),
            notizen=opt_str(notizen),
        )
        await stammdaten_service.update_objekt(session, objekt_id, payload)
        return redirect_with_flash("/stammdaten", ok="Objekt aktualisiert.", extra_params={"tab": "objekte"})
    except (DomainError, ValueError) as exc:
        return redirect_with_flash("/stammdaten", err=str(exc), extra_params={"tab": "objekte"})


@router.post("/objekte/{objekt_id}/delete")
async def web_delete_objekt(
    objekt_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        await stammdaten_service.delete_objekt(session, objekt_id)
        return redirect_with_flash("/stammdaten", ok="Objekt gelöscht.", extra_params={"tab": "objekte"})
    except DomainError as exc:
        return redirect_with_flash("/stammdaten", err=exc.message, extra_params={"tab": "objekte"})


# --- Wohneinheiten ---

@router.post("/wohneinheiten")
async def web_create_wohneinheit(
    objekt_id: int = Form(...),
    bezeichnung: str = Form(...),
    lage_etage: str = Form(...),
    wohnflaeche_qm: str = Form(...),
    zimmeranzahl: str = Form(...),
    status: WohneinheitStatus = Form(...),
    notizen: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        payload = WohneinheitCreate(
            objekt_id=objekt_id,
            bezeichnung=bezeichnung,
            lage_etage=lage_etage,
            wohnflaeche_qm=parse_decimal(wohnflaeche_qm, field_name="Wohnfläche"),
            zimmeranzahl=parse_decimal(zimmeranzahl, field_name="Zimmeranzahl"),
            status=status,
            notizen=opt_str(notizen),
        )
        await stammdaten_service.create_wohneinheit(session, payload)
        return redirect_with_flash("/stammdaten", ok="Wohneinheit angelegt.", extra_params={"tab": "einheiten"})
    except (DomainError, ValueError) as exc:
        return redirect_with_flash("/stammdaten", err=str(exc), extra_params={"tab": "einheiten"})


@router.post("/wohneinheiten/{wohneinheit_id}/update")
async def web_update_wohneinheit(
    wohneinheit_id: int,
    objekt_id: int = Form(...),
    bezeichnung: str = Form(...),
    lage_etage: str = Form(...),
    wohnflaeche_qm: str = Form(...),
    zimmeranzahl: str = Form(...),
    status: WohneinheitStatus = Form(...),
    notizen: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        payload = WohneinheitUpdate(
            objekt_id=objekt_id,
            bezeichnung=bezeichnung,
            lage_etage=lage_etage,
            wohnflaeche_qm=parse_decimal(wohnflaeche_qm, field_name="Wohnfläche"),
            zimmeranzahl=parse_decimal(zimmeranzahl, field_name="Zimmeranzahl"),
            status=status,
            notizen=opt_str(notizen),
        )
        await stammdaten_service.update_wohneinheit(session, wohneinheit_id, payload)
        return redirect_with_flash("/stammdaten", ok="Wohneinheit aktualisiert.", extra_params={"tab": "einheiten"})
    except (DomainError, ValueError) as exc:
        return redirect_with_flash("/stammdaten", err=str(exc), extra_params={"tab": "einheiten"})


@router.post("/wohneinheiten/{wohneinheit_id}/delete")
async def web_delete_wohneinheit(
    wohneinheit_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        await stammdaten_service.delete_wohneinheit(session, wohneinheit_id)
        return redirect_with_flash("/stammdaten", ok="Wohneinheit gelöscht.", extra_params={"tab": "einheiten"})
    except DomainError as exc:
        return redirect_with_flash("/stammdaten", err=exc.message, extra_params={"tab": "einheiten"})


# --- Mieter ---

@router.post("/mieter")
async def web_create_mieter(
    anrede: str | None = Form(default=None),
    vorname: str = Form(...),
    nachname: str = Form(...),
    email: str | None = Form(default=None),
    telefon: str | None = Form(default=None),
    aktuelle_strasse: str | None = Form(default=None),
    aktuelle_plz: str | None = Form(default=None),
    aktueller_ort: str | None = Form(default=None),
    iban: str | None = Form(default=None),
    notizen: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        payload = MieterCreate(
            anrede=opt_str(anrede),
            vorname=vorname,
            nachname=nachname,
            email=opt_str(email),
            telefon=opt_str(telefon),
            aktuelle_strasse=opt_str(aktuelle_strasse),
            aktuelle_plz=opt_str(aktuelle_plz),
            aktueller_ort=opt_str(aktueller_ort),
            iban=opt_str(iban),
            notizen=opt_str(notizen),
        )
        await stammdaten_service.create_mieter(session, payload)
        return redirect_with_flash("/stammdaten", ok="Mieter angelegt.", extra_params={"tab": "mieter"})
    except (DomainError, ValueError) as exc:
        return redirect_with_flash("/stammdaten", err=str(exc), extra_params={"tab": "mieter"})


@router.post("/mieter/{mieter_id}/update")
async def web_update_mieter(
    mieter_id: int,
    anrede: str | None = Form(default=None),
    vorname: str = Form(...),
    nachname: str = Form(...),
    email: str | None = Form(default=None),
    telefon: str | None = Form(default=None),
    aktuelle_strasse: str | None = Form(default=None),
    aktuelle_plz: str | None = Form(default=None),
    aktueller_ort: str | None = Form(default=None),
    iban: str | None = Form(default=None),
    notizen: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        payload = MieterUpdate(
            anrede=opt_str(anrede),
            vorname=vorname,
            nachname=nachname,
            email=opt_str(email),
            telefon=opt_str(telefon),
            aktuelle_strasse=opt_str(aktuelle_strasse),
            aktuelle_plz=opt_str(aktuelle_plz),
            aktueller_ort=opt_str(aktueller_ort),
            iban=opt_str(iban),
            notizen=opt_str(notizen),
        )
        await stammdaten_service.update_mieter(session, mieter_id, payload)
        return redirect_with_flash("/stammdaten", ok="Mieter aktualisiert.", extra_params={"tab": "mieter"})
    except (DomainError, ValueError) as exc:
        return redirect_with_flash("/stammdaten", err=str(exc), extra_params={"tab": "mieter"})


@router.post("/mieter/{mieter_id}/delete")
async def web_delete_mieter(
    mieter_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        await stammdaten_service.delete_mieter(session, mieter_id)
        return redirect_with_flash("/stammdaten", ok="Mieter gelöscht.", extra_params={"tab": "mieter"})
    except DomainError as exc:
        return redirect_with_flash("/stammdaten", err=exc.message, extra_params={"tab": "mieter"})


# --- Mietverträge & Konditionen ---

@router.post("/mietvertraege")
async def web_create_mietvertrag(
    wohneinheit_id: int = Form(...),
    mieter_ids: list[int] = Form(...),
    vertragsnummer: str | None = Form(default=None),
    vertragsbeginn: str = Form(...),
    vertragsende: str | None = Form(default=None),
    zahlungsziel_werktag: int = Form(default=3),
    kaltmiete: str = Form(...),
    betriebskosten_vorauszahlung: str = Form(default="0.00"),
    heizkosten_vorauszahlung: str = Form(default="0.00"),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        beginn = opt_date(vertragsbeginn)
        if beginn is None:
            raise ValueError("Vertragsbeginn ist erforderlich.")

        links = [
            VertragMieterLink(mieter_id=mid, hauptmieter=(idx == 0))
            for idx, mid in enumerate(mieter_ids)
        ]
        payload = MietvertragCreate(
            wohneinheit_id=wohneinheit_id,
            vertragsnummer=opt_str(vertragsnummer),
            vertragsbeginn=beginn,
            vertragsende=opt_date(vertragsende),
            zahlungsziel_werktag=zahlungsziel_werktag,
            mieter=links,
            initiale_konditionen=KonditionenInitialInput(
                kaltmiete=parse_decimal(kaltmiete, field_name="Kaltmiete"),
                betriebskosten_vorauszahlung=parse_decimal(
                    betriebskosten_vorauszahlung, field_name="BK-VZ"
                ),
                heizkosten_vorauszahlung=parse_decimal(
                    heizkosten_vorauszahlung, field_name="HK-VZ"
                ),
            ),
        )
        vertrag = await stammdaten_service.create_mietvertrag(session, payload)
        return redirect_with_flash(
            f"/mietvertraege/{vertrag.id}",
            ok="Mietvertrag inkl. initialer Konditionen angelegt.",
        )
    except (DomainError, ValueError) as exc:
        return redirect_with_flash("/stammdaten", err=str(exc), extra_params={"tab": "vertraege"})


@router.get("/mietvertraege/{mietvertrag_id}", response_class=HTMLResponse)
async def view_mietvertrag_detail(
    request: Request,
    mietvertrag_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    vertrag = await stammdaten_service.get_mietvertrag(session, mietvertrag_id)
    konditionen = await konditionen_service.list_konditionen_historie(session, mietvertrag_id)
    dokumente = await dokument_service.list_dokumente(session, mietvertrag_id=mietvertrag_id)

    return templates.TemplateResponse(
        request=request,
        name="stammdaten/mietvertrag_detail.html",
        context={
            "active_nav": "stammdaten",
            "vertrag": vertrag,
            "konditionen": konditionen,
            "dokumente": dokumente,
            **flash_context(request),
        },
    )


@router.post("/mietvertraege/{mietvertrag_id}/update")
async def web_update_mietvertrag(
    mietvertrag_id: int,
    wohneinheit_id: int = Form(...),
    vertragsnummer: str | None = Form(default=None),
    vertragsbeginn: str = Form(...),
    vertragsende: str | None = Form(default=None),
    kuendigungsdatum: str | None = Form(default=None),
    zahlungsziel_werktag: int = Form(default=3),
    notizen: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        beginn = opt_date(vertragsbeginn)
        if beginn is None:
            raise ValueError("Vertragsbeginn ist erforderlich.")

        payload = MietvertragUpdate(
            wohneinheit_id=wohneinheit_id,
            vertragsnummer=opt_str(vertragsnummer),
            vertragsbeginn=beginn,
            vertragsende=opt_date(vertragsende),
            kuendigungsdatum=opt_date(kuendigungsdatum),
            zahlungsziel_werktag=zahlungsziel_werktag,
            notizen=opt_str(notizen),
        )
        await stammdaten_service.update_mietvertrag(session, mietvertrag_id, payload)
        return redirect_with_flash(f"/mietvertraege/{mietvertrag_id}", ok="Vertragsdaten gespeichert.")
    except (DomainError, ValueError) as exc:
        return redirect_with_flash(f"/mietvertraege/{mietvertrag_id}", err=str(exc))


@router.post("/mietvertraege/{mietvertrag_id}/konditionen/anpassen", response_class=HTMLResponse)
async def web_adjust_konditionen(
    request: Request,
    mietvertrag_id: int,
    stichtag: str = Form(...),
    kaltmiete: str = Form(...),
    betriebskosten_vorauszahlung: str = Form(default="0.00"),
    heizkosten_vorauszahlung: str = Form(default="0.00"),
    aenderungsgrund: str = Form(...),
    session: AsyncSession = Depends(get_db_session),
):
    vertrag = await stammdaten_service.get_mietvertrag(session, mietvertrag_id)
    success_message: str | None = None
    error_message: str | None = None

    try:
        stichtag_date = opt_date(stichtag)
        if stichtag_date is None:
            raise ValueError("Stichtag ist erforderlich.")
        payload = KonditionenAnpassungRequest(
            stichtag=stichtag_date,
            kaltmiete=parse_decimal(kaltmiete, field_name="Kaltmiete"),
            betriebskosten_vorauszahlung=parse_decimal(
                betriebskosten_vorauszahlung, field_name="BK-VZ"
            ),
            heizkosten_vorauszahlung=parse_decimal(
                heizkosten_vorauszahlung, field_name="HK-VZ"
            ),
            aenderungsgrund=aenderungsgrund,
        )
        await konditionen_service.adjust_konditionen_zum_stichtag(session, mietvertrag_id, payload)
        success_message = f"Mietkonditionen zum {stichtag_date.strftime('%d.%m.%Y')} erfolgreich angepasst."
    except (DomainError, ValueError) as exc:
        error_message = getattr(exc, "message", str(exc))

    konditionen = await konditionen_service.list_konditionen_historie(session, mietvertrag_id)
    return templates.TemplateResponse(
        request=request,
        name="stammdaten/partials/konditionen_section.html",
        context={
            "vertrag": vertrag,
            "konditionen": konditionen,
            "success_message": success_message,
            "error_message": error_message,
        },
    )
