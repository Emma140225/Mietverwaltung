"""Jinja2-Template-Konfiguration inkl. deutscher Formatierungsfilter."""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def format_eur(value: Decimal | int | float | None) -> str:
    """Formatiert Geldbeträge im deutschen Format (z. B. 1.234,56 €)."""
    if value is None:
        return "–"
    dec = value if isinstance(value, Decimal) else Decimal(str(value))
    formatted = f"{dec:,.2f}"
    # US-Format (1,234.56) -> DE-Format (1.234,56)
    formatted = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{formatted} €"


def format_de_date(value: date | datetime | None) -> str:
    """Formatiert ein Datum als TT.MM.JJJJ."""
    if value is None:
        return "–"
    return value.strftime("%d.%m.%Y")


def format_de_month(value: date | None) -> str:
    """Formatiert einen Monatsbeginn als MM/JJJJ."""
    if value is None:
        return "–"
    return value.strftime("%m/%Y")


def format_qm(value: Decimal | int | float | None) -> str:
    """Formatiert Flächenangaben mit m²."""
    if value is None:
        return "–"
    dec = value if isinstance(value, Decimal) else Decimal(str(value))
    return f"{dec:.2f}".replace(".", ",") + " m²"


def create_templates() -> Jinja2Templates:
    """Erstellt und konfiguriert die zentrale Jinja2Templates-Instanz."""
    tpl = Jinja2Templates(directory=str(TEMPLATES_DIR))
    tpl.env.filters["eur"] = format_eur
    tpl.env.filters["de_date"] = format_de_date
    tpl.env.filters["de_month"] = format_de_month
    tpl.env.filters["qm"] = format_qm
    return tpl


templates = create_templates()
