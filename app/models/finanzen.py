"""Finanzmodelle: Konfigurierbarer Kostenarten-Katalog und manuelle Buchungen."""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import Buchungsrichtung, Verteilerschluessel
from app.models.stammdaten import _pg_enum

if TYPE_CHECKING:
    from app.models.dokument import Dokument
    from app.models.stammdaten import Mietvertrag, Objekt, Wohneinheit


class Kostenart(TimestampMixin, Base):
    """Konfigurierbarer Katalog für Einnahmen und Ausgaben inkl. BetrKV-Umlagefähigkeit."""

    __tablename__ = "kostenart"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    richtung: Mapped[Buchungsrichtung] = mapped_column(
        _pg_enum(Buchungsrichtung, "buchungsrichtung"),
        nullable=False,
    )
    umlagefaehig: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    standard_verteilerschluessel: Mapped[Verteilerschluessel] = mapped_column(
        _pg_enum(Verteilerschluessel, "verteilerschluessel"),
        nullable=False,
        default=Verteilerschluessel.KEINER,
    )
    betrkv_ziffer: Mapped[str | None] = mapped_column(String(40), nullable=True)
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sortierung: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=100)

    # Beziehungen
    buchungen: Mapped[list["Buchung"]] = relationship(back_populates="kostenart")


class Buchung(TimestampMixin, Base):
    """Lückenlose Buchung von Zahlungseingängen und -ausgängen.

    Alle Geldbeträge werden strikt als `NUMERIC(10, 2)` / `Decimal` gespeichert.
    Optimistic Locking über `version` verhindert Datenverlust bei paralleler
    Bearbeitung über mehrere Client-PCs im Heimnetzwerk.
    """

    __tablename__ = "buchung"
    __table_args__ = (
        CheckConstraint("betrag <> 0", name="betrag_ungleich_null"),
        CheckConstraint(
            "leistungszeitraum_von IS NULL OR leistungszeitraum_bis IS NULL "
            "OR leistungszeitraum_bis >= leistungszeitraum_von",
            name="leistungszeitraum_plausibel",
        ),
        Index("ix_buchung_objekt_datum", "objekt_id", "buchungsdatum"),
        Index("ix_buchung_einheit_datum", "wohneinheit_id", "buchungsdatum"),
        Index("ix_buchung_vertrag_datum", "mietvertrag_id", "buchungsdatum"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    objekt_id: Mapped[int] = mapped_column(
        ForeignKey("objekt.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # NULL = Gesamtobjektkosten (z. B. Grundsteuer, Gebäudeversicherung)
    wohneinheit_id: Mapped[int | None] = mapped_column(
        ForeignKey("wohneinheit.id", ondelete="RESTRICT"),
        nullable=True,
    )
    mietvertrag_id: Mapped[int | None] = mapped_column(
        ForeignKey("mietvertrag.id", ondelete="RESTRICT"),
        nullable=True,
    )
    kostenart_id: Mapped[int] = mapped_column(
        ForeignKey("kostenart.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    buchungsdatum: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    leistungszeitraum_von: Mapped[date | None] = mapped_column(Date, nullable=True)
    leistungszeitraum_bis: Mapped[date | None] = mapped_column(Date, nullable=True)
    betrag: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    empfaenger_sender: Mapped[str] = mapped_column(String(200), nullable=False)
    verwendungszweck: Mapped[str] = mapped_column(String(300), nullable=False)
    ist_sonderzahlung: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    belegnummer: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notizen: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optimistic Locking Spalte
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __mapper_args__ = {"version_id_col": version}

    # Beziehungen
    objekt: Mapped["Objekt"] = relationship(back_populates="buchungen")
    wohneinheit: Mapped["Wohneinheit | None"] = relationship(back_populates="buchungen")
    mietvertrag: Mapped["Mietvertrag | None"] = relationship(back_populates="buchungen")
    kostenart: Mapped["Kostenart"] = relationship(back_populates="buchungen")
    dokumente: Mapped[list["Dokument"]] = relationship(back_populates="buchung")
