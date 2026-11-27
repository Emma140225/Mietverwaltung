"""Historisierte Miet- und Abschlagsänderungen mit PostgreSQL EXCLUDE-Constraint."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.stammdaten import Mietvertrag


class MietkonditionenHistorie(Base):
    """Zeitraumbezogene Soll-Konditionen eines Mietvertrags.

    `gueltig_ab` und `gueltig_bis` sind inklusive Kalendertage (`'[]'`).
    Ein offener aktueller Zeitraum hat `gueltig_bis = NULL`.
    Der PostgreSQL-GiST-Exclusion-Constraint verhindert überlappende Zeiträume
    für denselben Mietvertrag direkt auf Datenbankebene.
    """

    __tablename__ = "mietkonditionen_historie"
    __table_args__ = (
        CheckConstraint(
            "gueltig_bis IS NULL OR gueltig_bis >= gueltig_ab",
            name="gueltig_bis_nach_ab",
        ),
        CheckConstraint("kaltmiete >= 0", name="kaltmiete_nicht_negativ"),
        CheckConstraint(
            "betriebskosten_vorauszahlung >= 0",
            name="bk_vorauszahlung_nicht_negativ",
        ),
        CheckConstraint(
            "heizkosten_vorauszahlung >= 0",
            name="hk_vorauszahlung_nicht_negativ",
        ),
        ExcludeConstraint(
            ("mietvertrag_id", "="),
            (text("daterange(gueltig_ab, gueltig_bis, '[]')"), "&&"),
            name="excl_mietkonditionen_kein_ueberlapp",
            using="gist",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mietvertrag_id: Mapped[int] = mapped_column(
        ForeignKey("mietvertrag.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    gueltig_ab: Mapped[date] = mapped_column(Date, nullable=False)
    gueltig_bis: Mapped[date | None] = mapped_column(Date, nullable=True)
    kaltmiete: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    betriebskosten_vorauszahlung: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    heizkosten_vorauszahlung: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    aenderungsgrund: Mapped[str] = mapped_column(String(250), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Beziehungen
    mietvertrag: Mapped["Mietvertrag"] = relationship(back_populates="konditionen_historie")

    @property
    def gesamtmiete(self) -> Decimal:
        """Monatliche Warmmiete (Kaltmiete + BK-VZ + HK-VZ)."""
        return (
            self.kaltmiete
            + self.betriebskosten_vorauszahlung
            + self.heizkosten_vorauszahlung
        )
