"""Pydantic-v2-Schemas für Kautionen, Kautionsbewegungen und Dokumente."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    DokumentKategorie,
    KautionAnlageform,
    KautionBewegungTyp,
    KautionStatus,
)


class KautionBewegungCreate(BaseModel):
    datum: date
    typ: KautionBewegungTyp
    betrag: Decimal = Field(gt=Decimal("0"), max_digits=10, decimal_places=2)
    rate_nummer: int | None = Field(default=None, ge=1, le=3)
    bemerkung: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_rate(self) -> "KautionBewegungCreate":
        if self.rate_nummer is not None and self.typ != KautionBewegungTyp.EINZAHLUNG_RATE:
            raise ValueError("Ratennummer ist nur bei Einzahlungsraten zulässig.")
        return self


class KautionBewegungRead(KautionBewegungCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kaution_id: int
    created_at: datetime


class KautionCreate(BaseModel):
    mietvertrag_id: int = Field(gt=0)
    vereinbarte_summe: Decimal = Field(ge=Decimal("0"), max_digits=10, decimal_places=2)
    anlageform: KautionAnlageform
    kontoreferenz: str | None = Field(default=None, max_length=120)
    notizen: str | None = None


class KautionUpdate(BaseModel):
    vereinbarte_summe: Decimal = Field(ge=Decimal("0"), max_digits=10, decimal_places=2)
    anlageform: KautionAnlageform
    kontoreferenz: str | None = Field(default=None, max_length=120)
    status: KautionStatus | None = None
    notizen: str | None = None
    version: int = Field(ge=1)


class KautionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mietvertrag_id: int
    vereinbarte_summe: Decimal
    anlageform: KautionAnlageform
    kontoreferenz: str | None
    status: KautionStatus
    notizen: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class KautionStatusUebersichtRead(BaseModel):
    """Zusammengefasster Kautionsstand inklusive Summen aus Bewegungen."""

    kaution_id: int
    mietvertrag_id: int
    wohneinheit_id: int
    objekt_id: int
    vereinbarte_summe: Decimal
    anlageform: KautionAnlageform
    kontoreferenz: str | None
    status: KautionStatus
    eingezahlt_summe: Decimal
    zinsen_summe: Decimal
    einbehalten_summe: Decimal
    zurueckgezahlt_summe: Decimal
    aktueller_bestand: Decimal
    offene_einzahlung: Decimal


class DokumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    objekt_id: int
    wohneinheit_id: int | None
    mietvertrag_id: int | None
    buchung_id: int | None
    kategorie: DokumentKategorie
    jahr: int
    original_dateiname: str
    relativer_pfad: str
    mime_type: str
    dateigroesse_bytes: int
    sha256_hash: str
    hochgeladen_am: datetime
    beschreibung: str | None
