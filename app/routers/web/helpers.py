"""Hilfsfunktionen für Web-/HTMX-Router (Parsing, PRG-Redirects und Flash-Meldungen)."""

from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import RedirectResponse

from app.services.exceptions import ValidationError


def flash_context(request: Request) -> dict[str, str | None]:
    """Extrahiert optionale Flash-Meldungen aus Query-Parametern."""
    return {
        "flash_success": request.query_params.get("ok"),
        "flash_error": request.query_params.get("err"),
    }


def redirect_with_flash(
    url: str,
    *,
    ok: str | None = None,
    err: str | None = None,
    extra_params: dict[str, str] | None = None,
) -> RedirectResponse:
    """Erstellt einen 303-See-Other-Redirect (PRG-Muster) inkl. Meldung."""
    params: dict[str, str] = dict(extra_params or {})
    if ok:
        params["ok"] = ok
    if err:
        params["err"] = err
    target = f"{url}?{urlencode(params)}" if params else url
    return RedirectResponse(url=target, status_code=303)


def opt_str(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def opt_int(value: str | None) -> int | None:
    stripped = opt_str(value)
    if stripped is None:
        return None
    try:
        return int(stripped)
    except ValueError as exc:
        raise ValidationError(f"Ungültige Ganzzahl: '{value}'.") from exc


def opt_date(value: str | None) -> date | None:
    stripped = opt_str(value)
    if stripped is None:
        return None
    try:
        return date.fromisoformat(stripped)
    except ValueError as exc:
        raise ValidationError(f"Ungültiges Datum: '{value}'.") from exc


def parse_month_input(value: str | None, fallback: date) -> date:
    """Parst ein HTML-<input type='month'> ('YYYY-MM') oder 'YYYY-MM-DD' zum Monatsersten."""
    stripped = opt_str(value)
    if stripped is None:
        return fallback.replace(day=1)
    try:
        if len(stripped) == 7:
            return date.fromisoformat(f"{stripped}-01")
        return date.fromisoformat(stripped).replace(day=1)
    except ValueError as exc:
        raise ValidationError(f"Ungültiger Monat: '{value}'.") from exc


def parse_decimal(value: str | None, *, field_name: str = "Betrag") -> Decimal:
    stripped = opt_str(value)
    if stripped is None:
        raise ValidationError(f"Feld '{field_name}' darf nicht leer sein.")
    try:
        return Decimal(stripped.replace(",", "."))
    except InvalidOperation as exc:
        raise ValidationError(f"Ungültiger Dezimalwert für '{field_name}': '{value}'.") from exc
