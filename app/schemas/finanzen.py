"""Pydantic-v2-Schemas für Kostenarten und manuelle Buchungen."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Buchungsrichtung, Verteilerschluessel


class KostenartBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    richtung: Buchungsrichtung
    umlagefaehig: bool = False
    standard_verteilerschluessel: Verteilerschluessel = Verteilerschluessel.KEINER
    betrkv_ziffer: str | None = Field(default=None, max_length=40)
    aktiv: bool = True
    sortierung: int = Field(default=100, ge=0, le=9999)


class KostenartCreate(KostenartBase):
    pass


class KostenartUpdate(KostenartBase):
    pass


class KostenartRead(KostenartBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class BuchungBase(BaseModel):
    objekt_id: int = Field(gt=0)
    wohneinheit_id: int | None = Field(default=None, gt=0)
    mietvertrag_id: int | None = Field(default=None, gt=0)
    kostenart_id: int = Field(gt=0)
    buchungsdatum: date
    leistungszeitraum_von: date | None = None
    leistungszeitraum_bis: date | None = None
    betrag: Decimal = Field(max_digits=10, decimal_places=2)
    empfaenger_sender: str = Field(min_length=1, max_length=200)
    verwendungszweck: str = Field(min_length=1, max_length=300)
    ist_sonderzahlung: bool = False
    belegnummer: str | None = Field(default=None, max_length=80)
    notizen: str | None = None

    @model_validator(mode="after")
    def validate_buchung(self) -> "BuchungBase":
        if self.betrag == Decimal("0"):
            raise ValueError("Der Betrag darf nicht 0,00 EUR sein.")
        if (
            self.leistungszeitraum_von is not None
            and self.leistungszeitraum_bis is not None
            and self.leistungszeitraum_bis < self.leistungszeitraum_von
        ):
            raise ValueError("Leistungszeitraum-Ende darf nicht vor dem Beginn liegen.")
        return self


class BuchungCreate(BuchungBase):
    pass


class BuchungUpdate(BuchungBase):
    # Optimistic Locking: Client muss die zuletzt geladene Version mitsenden
    version: int = Field(ge=1)


class BuchungRead(BuchungBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int
    created_at: datetime
    updated_at: datetime
    kostenart: KostenartRead | None = None
