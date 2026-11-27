"""Dokumenten-Metadatenmodell (PDF-Ablage im gemounteten NAS-Volume)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import DokumentKategorie
from app.models.stammdaten import _pg_enum

if TYPE_CHECKING:
    from app.models.finanzen import Buchung
    from app.models.stammdaten import Mietvertrag, Objekt, Wohneinheit


class Dokument(Base):
    """Metadaten für auf dem NAS-Dateisystem abgelegte PDF-Dokumente.

    Binärdaten werden niemals in der Datenbank gespeichert; lediglich der relative
    Pfad unterhalb von `DOKUMENTE_ROOT` sowie der SHA-256-Hash zur Integritätsprüfung.
    """

    __tablename__ = "dokument"
    __table_args__ = (
        CheckConstraint("jahr BETWEEN 1990 AND 2100", name="jahr_plausibel"),
        CheckConstraint("dateigroesse_bytes > 0", name="dateigroesse_positiv"),
        CheckConstraint("char_length(sha256_hash) = 64", name="sha256_laenge_64"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    objekt_id: Mapped[int] = mapped_column(
        ForeignKey("objekt.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    wohneinheit_id: Mapped[int | None] = mapped_column(
        ForeignKey("wohneinheit.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    mietvertrag_id: Mapped[int | None] = mapped_column(
        ForeignKey("mietvertrag.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    buchung_id: Mapped[int | None] = mapped_column(
        ForeignKey("buchung.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    kategorie: Mapped[DokumentKategorie] = mapped_column(
        _pg_enum(DokumentKategorie, "dokument_kategorie"),
        nullable=False,
    )
    jahr: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)
    original_dateiname: Mapped[str] = mapped_column(String(255), nullable=False)
    relativer_pfad: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="application/pdf",
    )
    dateigroesse_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    hochgeladen_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    beschreibung: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Beziehungen
    objekt: Mapped["Objekt"] = relationship(back_populates="dokumente")
    wohneinheit: Mapped["Wohneinheit | None"] = relationship(back_populates="dokumente")
    mietvertrag: Mapped["Mietvertrag | None"] = relationship(back_populates="dokumente")
    buchung: Mapped["Buchung | None"] = relationship(back_populates="dokumente")
