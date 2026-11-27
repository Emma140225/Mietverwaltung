"""Export-Service für externe Nebenkosten-Abrechner (CSV + ZIP mit Beleg-PDFs)."""

import csv
from datetime import date
from decimal import Decimal
import io
from pathlib import Path
import re
import zipfile

from sqlalchemy import extract, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.finanzen import Buchung, Kostenart
from app.services.dokument import compute_sha256_file, _resolve_safe_path
from app.services.exceptions import ValidationError
from app.services.stammdaten import get_objekt

_SLUG_RE = re.compile(r"[^A-Za-z0-9_-]+")


def _slugify(value: str) -> str:
    return _SLUG_RE.sub("_", value).strip("_").lower() or "objekt"


def _fmt_date(value: date | None) -> str:
    return value.strftime("%d.%m.%Y") if value is not None else ""


def _fmt_decimal_de(value: Decimal) -> str:
    return f"{value:.2f}".replace(".", ",")


async def _load_umlagefaehige_buchungen(
    session: AsyncSession,
    objekt_id: int,
    jahr: int,
) -> list[Buchung]:
    stmt = (
        select(Buchung)
        .join(Buchung.kostenart)
        .options(
            selectinload(Buchung.kostenart),
            selectinload(Buchung.wohneinheit),
            selectinload(Buchung.dokumente),
        )
        .where(
            Buchung.objekt_id == objekt_id,
            Kostenart.umlagefaehig.is_(True),
            extract("year", Buchung.buchungsdatum) == jahr,
        )
        .order_by(Buchung.buchungsdatum.asc(), Buchung.id.asc())
    )
    return list((await session.scalars(stmt)).all())


def _build_csv_bytes(buchungen: list[Buchung], dokument_dateinamen: dict[int, list[str]]) -> bytes:
    """Erstellt eine Excel-/Abrechner-kompatible UTF-8-BOM-CSV-Datei mit Semikolon-Trenner."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow(
        [
            "Buchung-ID",
            "Buchungsdatum",
            "Leistungszeitraum von",
            "Leistungszeitraum bis",
            "Kostenart",
            "BetrKV-Ziffer",
            "Verteilerschlüssel",
            "Zuordnung",
            "Empfänger/Sender",
            "Verwendungszweck",
            "Belegnummer",
            "Betrag (EUR)",
            "Beleg-PDFs im Archiv",
        ]
    )

    for b in buchungen:
        zuordnung = b.wohneinheit.bezeichnung if b.wohneinheit is not None else "Gesamtobjekt"
        beleg_liste = ", ".join(dokument_dateinamen.get(b.id, []))
        writer.writerow(
            [
                b.id,
                _fmt_date(b.buchungsdatum),
                _fmt_date(b.leistungszeitraum_von),
                _fmt_date(b.leistungszeitraum_bis),
                b.kostenart.name,
                b.kostenart.betrkv_ziffer or "",
                b.kostenart.standard_verteilerschluessel.value,
                zuordnung,
                b.empfaenger_sender,
                b.verwendungszweck,
                b.belegnummer or "",
                _fmt_decimal_de(b.betrag),
                beleg_liste,
            ]
        )

    return buffer.getvalue().encode("utf-8-sig")


async def export_umlagefaehige_kosten_csv(
    session: AsyncSession,
    objekt_id: int,
    jahr: int,
) -> tuple[str, bytes]:
    """Exportiert alle umlagefähigen Buchungen eines Objekts und Jahres als CSV."""
    if not (1990 <= jahr <= 2100):
        raise ValidationError("Das Exportjahr muss zwischen 1990 und 2100 liegen.")
    objekt = await get_objekt(session, objekt_id)
    buchungen = await _load_umlagefaehige_buchungen(session, objekt_id, jahr)

    dok_names = {
        b.id: [d.original_dateiname for d in b.dokumente]
        for b in buchungen
    }
    csv_bytes = _build_csv_bytes(buchungen, dok_names)
    filename = f"umlagefaehige_kosten_{_slugify(objekt.bezeichnung)}_{jahr}.csv"
    return filename, csv_bytes


async def export_umlagefaehige_kosten_zip(
    session: AsyncSession,
    objekt_id: int,
    jahr: int,
) -> tuple[str, bytes]:
    """Erstellt ein ZIP-Archiv mit CSV aller umlagefähigen Kosten + allen zugehörigen Rechnungs-PDFs."""
    if not (1990 <= jahr <= 2100):
        raise ValidationError("Das Exportjahr muss zwischen 1990 und 2100 liegen.")
    objekt = await get_objekt(session, objekt_id)
    buchungen = await _load_umlagefaehige_buchungen(session, objekt_id, jahr)

    slug = _slugify(objekt.bezeichnung)
    csv_name = f"umlagefaehige_kosten_{slug}_{jahr}.csv"
    zip_name = f"nk_export_{slug}_{jahr}.zip"

    zip_buffer = io.BytesIO()
    hinweise: list[str] = []
    dokument_archive_paths: dict[int, list[str]] = {}

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for b in buchungen:
            beleg_paths_for_booking: list[str] = []
            for dok in b.dokumente:
                safe_orig = Path(dok.original_dateiname).name.replace("/", "_")
                arcname = f"belege/B{b.id}_D{dok.id}_{safe_orig}"
                try:
                    full_path = _resolve_safe_path(dok.relativer_pfad)
                    if not full_path.is_file():
                        hinweise.append(
                            f"FEHLEND: Buchung #{b.id}, Dokument #{dok.id} ({dok.relativer_pfad}) nicht gefunden."
                        )
                        continue
                    actual_hash = compute_sha256_file(full_path)
                    if actual_hash != dok.sha256_hash:
                        hinweise.append(
                            f"INTEGRITAETSWARNUNG: Buchung #{b.id}, Dokument #{dok.id} ({dok.original_dateiname}) "
                            f"SHA-256 stimmt nicht überein (erwartet {dok.sha256_hash}, ist {actual_hash})."
                        )
                    zf.write(full_path, arcname=arcname)
                    beleg_paths_for_booking.append(arcname)
                except Exception as exc:
                    hinweise.append(f"FEHLER bei Buchung #{b.id}, Dokument #{dok.id}: {exc}")

            dokument_archive_paths[b.id] = beleg_paths_for_booking

        csv_bytes = _build_csv_bytes(buchungen, dokument_archive_paths)
        zf.writestr(csv_name, csv_bytes)

        if hinweise:
            zf.writestr("HINWEISE_EXPORT.txt", "\n".join(hinweise).encode("utf-8"))

    return zip_name, zip_buffer.getvalue()
