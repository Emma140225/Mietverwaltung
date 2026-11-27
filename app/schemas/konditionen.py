"""Pydantic-v2-Schemas für historisierte Miet- und Abschlagsänderungen."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MietkonditionenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mietvertrag_id: int
    gueltig_ab: date
    gueltig_bis: date | None
    kaltmiete: Decimal
    betriebskosten_vorauszahlung: Decimal
    heizkosten_vorauszahlung: Decimal
    gesamtmiete: Decimal
    aenderungsgrund: str
    created_at: datetime


class KonditionenAnpassungRequest(BaseModel):
    """Request für die UI-Funktion 'Miete / Abschlag zum Stichtag anpassen'."""

    stichtag: date
    kaltmiete: Decimal = Field(ge=Decimal("0"), max_digits=10, decimal_places=2)
    betriebskosten_vorauszahlung: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        max_digits=10,
        decimal_places=2,
    )
    heizkosten_vorauszahlung: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        max_digits=10,
        decimal_places=2,
    )
    aenderungsgrund: str = Field(min_length=1, max_length=250)
