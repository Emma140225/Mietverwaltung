"""Pydantic-v2-Schemas für Stammdaten (Objekt, Wohneinheit, Mieter, Mietvertrag)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import WohneinheitStatus


class ObjektBase(BaseModel):
    bezeichnung: str = Field(min_length=1, max_length=120)
    strasse: str = Field(min_length=1, max_length=200)
    plz: str = Field(min_length=4, max_length=10)
    ort: str = Field(min_length=1, max_length=100)
    baujahr: int | None = Field(default=None, ge=1500, le=2100)
    gesamtflaeche_qm: Decimal = Field(gt=Decimal("0"), max_digits=10, decimal_places=2)
    notizen: str | None = None


class ObjektCreate(ObjektBase):
    pass


class ObjektUpdate(ObjektBase):
    pass


class ObjektRead(ObjektBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    adresse: str
    created_at: datetime
    updated_at: datetime


class WohneinheitBase(BaseModel):
    objekt_id: int = Field(gt=0)
    bezeichnung: str = Field(min_length=1, max_length=100)
    lage_etage: str = Field(min_length=1, max_length=80)
    wohnflaeche_qm: Decimal = Field(gt=Decimal("0"), max_digits=8, decimal_places=2)
    zimmeranzahl: Decimal = Field(gt=Decimal("0"), max_digits=4, decimal_places=1)
    status: WohneinheitStatus = WohneinheitStatus.LEERSTAND
    notizen: str | None = None


class WohneinheitCreate(WohneinheitBase):
    pass


class WohneinheitUpdate(WohneinheitBase):
    pass


class WohneinheitRead(WohneinheitBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class MieterBase(BaseModel):
    anrede: str | None = Field(default=None, max_length=20)
    vorname: str = Field(min_length=1, max_length=100)
    nachname: str = Field(min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=200)
    telefon: str | None = Field(default=None, max_length=50)
    aktuelle_strasse: str | None = Field(default=None, max_length=200)
    aktuelle_plz: str | None = Field(default=None, max_length=10)
    aktueller_ort: str | None = Field(default=None, max_length=100)
    iban: str | None = Field(default=None, max_length=34)
    notizen: str | None = None


class MieterCreate(MieterBase):
    pass


class MieterUpdate(MieterBase):
    pass


class MieterRead(MieterBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    voller_name: str
    created_at: datetime
    updated_at: datetime


class VertragMieterLink(BaseModel):
    mieter_id: int = Field(gt=0)
    hauptmieter: bool = True
    einzugsdatum_mieter: date | None = None
    auszugsdatum_mieter: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "VertragMieterLink":
        if (
            self.einzugsdatum_mieter is not None
            and self.auszugsdatum_mieter is not None
            and self.auszugsdatum_mieter < self.einzugsdatum_mieter
        ):
            raise ValueError("Auszugsdatum des Mieters darf nicht vor dem Einzugsdatum liegen.")
        return self


class VertragMieterRead(VertragMieterLink):
    model_config = ConfigDict(from_attributes=True)

    mietvertrag_id: int
    mieter: MieterRead | None = None


class KonditionenInitialInput(BaseModel):
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
    aenderungsgrund: str = Field(default="Vertragsbeginn", min_length=1, max_length=250)


class MietvertragBase(BaseModel):
    wohneinheit_id: int = Field(gt=0)
    vertragsnummer: str | None = Field(default=None, max_length=60)
    vertragsbeginn: date
    vertragsende: date | None = None
    kuendigungsdatum: date | None = None
    zahlungsziel_werktag: int = Field(default=3, ge=1, le=28)
    notizen: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "MietvertragBase":
        if self.vertragsende is not None and self.vertragsende < self.vertragsbeginn:
            raise ValueError("Vertragsende darf nicht vor dem Vertragsbeginn liegen.")
        return self


class MietvertragCreate(MietvertragBase):
    mieter: list[VertragMieterLink] = Field(min_length=1)
    initiale_konditionen: KonditionenInitialInput


class MietvertragUpdate(MietvertragBase):
    mieter: list[VertragMieterLink] | None = Field(default=None, min_length=1)


class MietvertragRead(MietvertragBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    mieter_zuordnungen: list[VertragMieterRead] = []
