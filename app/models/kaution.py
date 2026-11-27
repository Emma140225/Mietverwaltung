"""Getrennte Kautionsverwaltung: Kautionskonto und einzelne Bewegungen."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import KautionAnlageform, KautionBewegungTyp, KautionStatus
from app.models.stammdaten import _pg_enum

if TYPE_CHECKING:
    from app.models.stammdaten import Mietvertrag


class Kaution(TimestampMixin, Base):
    """Kautionsvereinbarung je Mietvertrag, getrennt vom laufenden Mietkonto."""

    __tablename__ = "kaution"
    __table_args__ = (
        CheckConstraint("vereinbarte_summe >= 0", name="vereinbarte_summe_nicht_negativ"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mietvertrag_id: Mapped[int] = mapped_column(
        ForeignKey("mietvertrag.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    vereinbarte_summe: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    anlageform: Mapped[KautionAnlageform] = mapped_column(
        _pg_enum(KautionAnlageform, "kaution_anlageform"),
        nullable=False,
    )
    kontoreferenz: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[KautionStatus] = mapped_column(
        _pg_enum(KautionStatus, "kaution_status"),
        nullable=False,
        default=KautionStatus.OFFEN,
    )
    notizen: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __mapper_args__ = {"version_id_col": version}

    # Beziehungen
    mietvertrag: Mapped["Mietvertrag"] = relationship(back_populates="kaution")
    bewegungen: Mapped[list["KautionBewegung"]] = relationship(
        back_populates="kaution",
        cascade="all, delete-orphan",
        order_by="KautionBewegung.datum.asc(), KautionBewegung.id.asc()",
    )


class KautionBewegung(Base):
    """Einzelbewegung auf dem Kautionskonto (Raten, Zinsen, Einbehalte, Rückzahlungen)."""

    __tablename__ = "kaution_bewegung"
    __table_args__ = (
        CheckConstraint("betrag > 0", name="bewegung_betrag_positiv"),
        CheckConstraint(
            "rate_nummer IS NULL OR (rate_nummer BETWEEN 1 AND 3)",
            name="rate_nummer_1_bis_3",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kaution_id: Mapped[int] = mapped_column(
        ForeignKey("kaution.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    datum: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    typ: Mapped[KautionBewegungTyp] = mapped_column(
        _pg_enum(KautionBewegungTyp, "kaution_bewegung_typ"),
        nullable=False,
    )
    betrag: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    rate_nummer: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    bemerkung: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Beziehungen
    kaution: Mapped["Kaution"] = relationship(back_populates="bewegungen")
