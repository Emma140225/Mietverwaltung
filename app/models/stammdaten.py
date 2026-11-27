"""Stammdaten-Modelle: Objekt, Wohneinheit, Mieter, Mietvertrag und VertragMieter."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import WohneinheitStatus

if TYPE_CHECKING:
    from app.models.dokument import Dokument
    from app.models.finanzen import Buchung
    from app.models.kaution import Kaution
    from app.models.konditionen import MietkonditionenHistorie


def _pg_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """Hilfsfunktion für PostgreSQL-ENUM-Typen mit kleingeschriebenen Enum-Values."""
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda obj: [e.value for e in obj],
        validate_strings=True,
    )


class Objekt(TimestampMixin, Base):
    """Immobilienobjekt (Gebäude / Liegenschaft)."""

    __tablename__ = "objekt"
    __table_args__ = (
        CheckConstraint("gesamtflaeche_qm > 0", name="gesamtflaeche_positiv"),
        CheckConstraint("baujahr IS NULL OR (baujahr BETWEEN 1500 AND 2100)", name="baujahr_plausibel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bezeichnung: Mapped[str] = mapped_column(String(120), nullable=False)
    strasse: Mapped[str] = mapped_column(String(200), nullable=False)
    plz: Mapped[str] = mapped_column(String(10), nullable=False)
    ort: Mapped[str] = mapped_column(String(100), nullable=False)
    baujahr: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    gesamtflaeche_qm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    notizen: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Beziehungen
    wohneinheiten: Mapped[list["Wohneinheit"]] = relationship(
        back_populates="objekt",
        cascade="save-update, merge",
        order_by="Wohneinheit.bezeichnung",
    )
    buchungen: Mapped[list["Buchung"]] = relationship(
        back_populates="objekt",
        cascade="save-update, merge",
    )
    dokumente: Mapped[list["Dokument"]] = relationship(
        back_populates="objekt",
        cascade="save-update, merge",
    )

    @property
    def adresse(self) -> str:
        """Formatierte Gesamtadresse des Objekts."""
        return f"{self.strasse}, {self.plz} {self.ort}"


class Wohneinheit(TimestampMixin, Base):
    """Einzelne vermietbare oder selbstgenutzte Wohneinheit innerhalb eines Objekts."""

    __tablename__ = "wohneinheit"
    __table_args__ = (
        CheckConstraint("wohnflaeche_qm > 0", name="wohnflaeche_positiv"),
        CheckConstraint("zimmeranzahl > 0", name="zimmeranzahl_positiv"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    objekt_id: Mapped[int] = mapped_column(
        ForeignKey("objekt.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bezeichnung: Mapped[str] = mapped_column(String(100), nullable=False)
    lage_etage: Mapped[str] = mapped_column(String(80), nullable=False)
    wohnflaeche_qm: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    # NUMERIC(4, 1) erlaubt halbe Zimmer (z. B. 2.5 Zimmer)
    zimmeranzahl: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    status: Mapped[WohneinheitStatus] = mapped_column(
        _pg_enum(WohneinheitStatus, "wohneinheit_status"),
        nullable=False,
        default=WohneinheitStatus.LEERSTAND,
    )
    notizen: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Beziehungen
    objekt: Mapped["Objekt"] = relationship(back_populates="wohneinheiten")
    mietvertraege: Mapped[list["Mietvertrag"]] = relationship(
        back_populates="wohneinheit",
        order_by="Mietvertrag.vertragsbeginn.desc()",
    )
    buchungen: Mapped[list["Buchung"]] = relationship(back_populates="wohneinheit")
    dokumente: Mapped[list["Dokument"]] = relationship(back_populates="wohneinheit")


class Mieter(TimestampMixin, Base):
    """Personendaten eines Mieters inkl. aktueller Nachsende-/Kontaktanschrift und IBAN."""

    __tablename__ = "mieter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anrede: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vorname: Mapped[str] = mapped_column(String(100), nullable=False)
    nachname: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    telefon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Aktuelle Anschrift (insbesondere nach Auszug für Kautionsabrechnung / Korrespondenz)
    aktuelle_strasse: Mapped[str | None] = mapped_column(String(200), nullable=True)
    aktuelle_plz: Mapped[str | None] = mapped_column(String(10), nullable=True)
    aktueller_ort: Mapped[str | None] = mapped_column(String(100), nullable=True)
    iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    notizen: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Beziehungen
    vertragszuordnungen: Mapped[list["VertragMieter"]] = relationship(
        back_populates="mieter",
        cascade="save-update, merge",
    )

    @property
    def voller_name(self) -> str:
        """Vollständiger Name des Mieters."""
        return f"{self.vorname} {self.nachname}".strip()


class Mietvertrag(TimestampMixin, Base):
    """Mietvertrag einer Wohneinheit; Mietkonditionen liegen historisiert in eigener Tabelle."""

    __tablename__ = "mietvertrag"
    __table_args__ = (
        CheckConstraint(
            "vertragsende IS NULL OR vertragsende >= vertragsbeginn",
            name="vertragsende_nach_beginn",
        ),
        CheckConstraint(
            "zahlungsziel_werktag BETWEEN 1 AND 28",
            name="zahlungsziel_werktag_gueltig",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wohneinheit_id: Mapped[int] = mapped_column(
        ForeignKey("wohneinheit.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    vertragsnummer: Mapped[str | None] = mapped_column(String(60), nullable=True, unique=True)
    vertragsbeginn: Mapped[date] = mapped_column(Date, nullable=False)
    vertragsende: Mapped[date | None] = mapped_column(Date, nullable=True)
    kuendigungsdatum: Mapped[date | None] = mapped_column(Date, nullable=True)
    zahlungsziel_werktag: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    notizen: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Beziehungen
    wohneinheit: Mapped["Wohneinheit"] = relationship(back_populates="mietvertraege")
    mieter_zuordnungen: Mapped[list["VertragMieter"]] = relationship(
        back_populates="mietvertrag",
        cascade="all, delete-orphan",
        order_by="VertragMieter.hauptmieter.desc()",
    )
    konditionen_historie: Mapped[list["MietkonditionenHistorie"]] = relationship(
        back_populates="mietvertrag",
        cascade="all, delete-orphan",
        order_by="MietkonditionenHistorie.gueltig_ab.asc()",
    )
    kaution: Mapped["Kaution | None"] = relationship(
        back_populates="mietvertrag",
        uselist=False,
    )
    buchungen: Mapped[list["Buchung"]] = relationship(back_populates="mietvertrag")
    dokumente: Mapped[list["Dokument"]] = relationship(back_populates="mietvertrag")


class VertragMieter(Base):
    """Assoziationstabelle für 1..n Mieter je Mietvertrag inkl. Hauptmieter-Kennzeichnung."""

    __tablename__ = "vertrag_mieter"
    __table_args__ = (
        CheckConstraint(
            "auszugsdatum_mieter IS NULL OR einzugsdatum_mieter IS NULL "
            "OR auszugsdatum_mieter >= einzugsdatum_mieter",
            name="mieter_zeitraum_plausibel",
        ),
    )

    mietvertrag_id: Mapped[int] = mapped_column(
        ForeignKey("mietvertrag.id", ondelete="CASCADE"),
        primary_key=True,
    )
    mieter_id: Mapped[int] = mapped_column(
        ForeignKey("mieter.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    hauptmieter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    einzugsdatum_mieter: Mapped[date | None] = mapped_column(Date, nullable=True)
    auszugsdatum_mieter: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Beziehungen
    mietvertrag: Mapped["Mietvertrag"] = relationship(back_populates="mieter_zuordnungen")
    mieter: Mapped["Mieter"] = relationship(back_populates="vertragszuordnungen")
