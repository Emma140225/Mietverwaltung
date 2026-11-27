"""Initiales Schema: Stammdaten, Historie, Buchungen, Kaution, Dokumente & Soll/Ist-Views.

Revision ID: 20261125_0001
Revises:
Create Date: 2026-11-25 16:55:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.db.views import (
    SQL_CREATE_VIEW_EINHEIT_MONAT_SOLL_IST,
    SQL_CREATE_VIEW_KAUTION_STATUS,
    SQL_CREATE_VIEW_OBJEKT_CASHFLOW_MONAT,
    SQL_DROP_VIEWS,
)

revision: str = "20261125_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Explizite PostgreSQL-ENUM-Definitionen für deterministisches Upgrade/Downgrade
wohneinheit_status_enum = postgresql.ENUM(
    "vermietet",
    "leerstand",
    "eigennutzung",
    "renovierung",
    name="wohneinheit_status",
    create_type=False,
)
buchungsrichtung_enum = postgresql.ENUM(
    "einnahme",
    "ausgabe",
    name="buchungsrichtung",
    create_type=False,
)
verteilerschluessel_enum = postgresql.ENUM(
    "wohnflaeche",
    "einheiten",
    "personen",
    "verbrauch",
    "direkt",
    "keiner",
    name="verteilerschluessel",
    create_type=False,
)
kaution_anlageform_enum = postgresql.ENUM(
    "mietkautionskonto",
    "sparbuch_verpfaendet",
    "bankbuergschaft",
    "bar",
    name="kaution_anlageform",
    create_type=False,
)
kaution_status_enum = postgresql.ENUM(
    "offen",
    "teilweise_eingegangen",
    "vollstaendig",
    "teilweise_zurueckgezahlt",
    "abgerechnet",
    name="kaution_status",
    create_type=False,
)
kaution_bewegung_typ_enum = postgresql.ENUM(
    "einzahlung_rate",
    "zinsgutschrift",
    "einbehalt",
    "rueckzahlung",
    name="kaution_bewegung_typ",
    create_type=False,
)
dokument_kategorie_enum = postgresql.ENUM(
    "beleg_rechnung",
    "mietvertrag",
    "uebergabeprotokoll",
    "kaution",
    "sonstiges",
    name="dokument_kategorie",
    create_type=False,
)

ALL_ENUMS = (
    wohneinheit_status_enum,
    buchungsrichtung_enum,
    verteilerschluessel_enum,
    kaution_anlageform_enum,
    kaution_status_enum,
    kaution_bewegung_typ_enum,
    dokument_kategorie_enum,
)


def upgrade() -> None:
    bind = op.get_bind()

    # Erforderlich für GiST-Exclusion-Constraints auf (integer, daterange)
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    for enum_type in ALL_ENUMS:
        enum_type.create(bind, checkfirst=True)

    # 1. objekt
    op.create_table(
        "objekt",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bezeichnung", sa.String(length=120), nullable=False),
        sa.Column("strasse", sa.String(length=200), nullable=False),
        sa.Column("plz", sa.String(length=10), nullable=False),
        sa.Column("ort", sa.String(length=100), nullable=False),
        sa.Column("baujahr", sa.SmallInteger(), nullable=True),
        sa.Column("gesamtflaeche_qm", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("notizen", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("gesamtflaeche_qm > 0", name="ck_objekt_gesamtflaeche_positiv"),
        sa.CheckConstraint("baujahr IS NULL OR (baujahr BETWEEN 1500 AND 2100)", name="ck_objekt_baujahr_plausibel"),
        sa.PrimaryKeyConstraint("id", name="pk_objekt"),
    )

    # 2. wohneinheit
    op.create_table(
        "wohneinheit",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("objekt_id", sa.Integer(), nullable=False),
        sa.Column("bezeichnung", sa.String(length=100), nullable=False),
        sa.Column("lage_etage", sa.String(length=80), nullable=False),
        sa.Column("wohnflaeche_qm", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("zimmeranzahl", sa.Numeric(precision=4, scale=1), nullable=False),
        sa.Column("status", wohneinheit_status_enum, nullable=False, server_default="leerstand"),
        sa.Column("notizen", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("wohnflaeche_qm > 0", name="ck_wohneinheit_wohnflaeche_positiv"),
        sa.CheckConstraint("zimmeranzahl > 0", name="ck_wohneinheit_zimmeranzahl_positiv"),
        sa.ForeignKeyConstraint(["objekt_id"], ["objekt.id"], name="fk_wohneinheit_objekt_id_objekt", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_wohneinheit"),
    )
    op.create_index("ix_wohneinheit_objekt_id", "wohneinheit", ["objekt_id"])

    # 3. mieter
    op.create_table(
        "mieter",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("anrede", sa.String(length=20), nullable=True),
        sa.Column("vorname", sa.String(length=100), nullable=False),
        sa.Column("nachname", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("telefon", sa.String(length=50), nullable=True),
        sa.Column("aktuelle_strasse", sa.String(length=200), nullable=True),
        sa.Column("aktuelle_plz", sa.String(length=10), nullable=True),
        sa.Column("aktueller_ort", sa.String(length=100), nullable=True),
        sa.Column("iban", sa.String(length=34), nullable=True),
        sa.Column("notizen", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_mieter"),
    )

    # 4. mietvertrag
    op.create_table(
        "mietvertrag",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wohneinheit_id", sa.Integer(), nullable=False),
        sa.Column("vertragsnummer", sa.String(length=60), nullable=True),
        sa.Column("vertragsbeginn", sa.Date(), nullable=False),
        sa.Column("vertragsende", sa.Date(), nullable=True),
        sa.Column("kuendigungsdatum", sa.Date(), nullable=True),
        sa.Column("zahlungsziel_werktag", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.Column("notizen", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "vertragsende IS NULL OR vertragsende >= vertragsbeginn",
            name="ck_mietvertrag_vertragsende_nach_beginn",
        ),
        sa.CheckConstraint(
            "zahlungsziel_werktag BETWEEN 1 AND 28",
            name="ck_mietvertrag_zahlungsziel_werktag_gueltig",
        ),
        sa.ForeignKeyConstraint(["wohneinheit_id"], ["wohneinheit.id"], name="fk_mietvertrag_wohneinheit_id_wohneinheit", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_mietvertrag"),
        sa.UniqueConstraint("vertragsnummer", name="uq_mietvertrag_vertragsnummer"),
    )
    op.create_index("ix_mietvertrag_wohneinheit_id", "mietvertrag", ["wohneinheit_id"])

    # 5. vertrag_mieter
    op.create_table(
        "vertrag_mieter",
        sa.Column("mietvertrag_id", sa.Integer(), nullable=False),
        sa.Column("mieter_id", sa.Integer(), nullable=False),
        sa.Column("hauptmieter", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("einzugsdatum_mieter", sa.Date(), nullable=True),
        sa.Column("auszugsdatum_mieter", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "auszugsdatum_mieter IS NULL OR einzugsdatum_mieter IS NULL "
            "OR auszugsdatum_mieter >= einzugsdatum_mieter",
            name="ck_vertrag_mieter_mieter_zeitraum_plausibel",
        ),
        sa.ForeignKeyConstraint(["mieter_id"], ["mieter.id"], name="fk_vertrag_mieter_mieter_id_mieter", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["mietvertrag_id"], ["mietvertrag.id"], name="fk_vertrag_mieter_mietvertrag_id_mietvertrag", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("mietvertrag_id", "mieter_id", name="pk_vertrag_mieter"),
    )

    # 6. mietkonditionen_historie (mit GiST EXCLUDE-Constraint)
    op.create_table(
        "mietkonditionen_historie",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mietvertrag_id", sa.Integer(), nullable=False),
        sa.Column("gueltig_ab", sa.Date(), nullable=False),
        sa.Column("gueltig_bis", sa.Date(), nullable=True),
        sa.Column("kaltmiete", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("betriebskosten_vorauszahlung", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0.00"),
        sa.Column("heizkosten_vorauszahlung", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0.00"),
        sa.Column("aenderungsgrund", sa.String(length=250), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("gueltig_bis IS NULL OR gueltig_bis >= gueltig_ab", name="ck_mietkonditionen_historie_gueltig_bis_nach_ab"),
        sa.CheckConstraint("kaltmiete >= 0", name="ck_mietkonditionen_historie_kaltmiete_nicht_negativ"),
        sa.CheckConstraint("betriebskosten_vorauszahlung >= 0", name="ck_mietkonditionen_historie_bk_vorauszahlung_nicht_negativ"),
        sa.CheckConstraint("heizkosten_vorauszahlung >= 0", name="ck_mietkonditionen_historie_hk_vorauszahlung_nicht_negativ"),
        postgresql.ExcludeConstraint(
            ("mietvertrag_id", "="),
            (sa.text("daterange(gueltig_ab, gueltig_bis, '[]')"), "&&"),
            name="excl_mietkonditionen_kein_ueberlapp",
            using="gist",
        ),
        sa.ForeignKeyConstraint(["mietvertrag_id"], ["mietvertrag.id"], name="fk_mietkonditionen_historie_mietvertrag_id_mietvertrag", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_mietkonditionen_historie"),
    )
    op.create_index("ix_mietkonditionen_historie_mietvertrag_id", "mietkonditionen_historie", ["mietvertrag_id"])

    # 7. kostenart
    kostenart_table = op.create_table(
        "kostenart",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("richtung", buchungsrichtung_enum, nullable=False),
        sa.Column("umlagefaehig", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("standard_verteilerschluessel", verteilerschluessel_enum, nullable=False, server_default="keiner"),
        sa.Column("betrkv_ziffer", sa.String(length=40), nullable=True),
        sa.Column("aktiv", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sortierung", sa.SmallInteger(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_kostenart"),
        sa.UniqueConstraint("name", name="uq_kostenart_name"),
    )

    # Standard-Kostenarten nach deutscher Vermietungspraxis / BetrKV vorbelegen
    op.bulk_insert(
        kostenart_table,
        [
            {"name": "Mietzahlung (Kalt + Abschläge)", "richtung": "einnahme", "umlagefaehig": False, "standard_verteilerschluessel": "direkt", "betrkv_ziffer": None, "aktiv": True, "sortierung": 10},
            {"name": "Kaltmiete", "richtung": "einnahme", "umlagefaehig": False, "standard_verteilerschluessel": "direkt", "betrkv_ziffer": None, "aktiv": True, "sortierung": 11},
            {"name": "Betriebskosten-Vorauszahlung", "richtung": "einnahme", "umlagefaehig": False, "standard_verteilerschluessel": "direkt", "betrkv_ziffer": None, "aktiv": True, "sortierung": 12},
            {"name": "Heizkosten-Vorauszahlung", "richtung": "einnahme", "umlagefaehig": False, "standard_verteilerschluessel": "direkt", "betrkv_ziffer": None, "aktiv": True, "sortierung": 13},
            {"name": "NK-Nachzahlung (Sonderzahlung)", "richtung": "einnahme", "umlagefaehig": False, "standard_verteilerschluessel": "direkt", "betrkv_ziffer": None, "aktiv": True, "sortierung": 15},
            {"name": "Grundsteuer", "richtung": "ausgabe", "umlagefaehig": True, "standard_verteilerschluessel": "wohnflaeche", "betrkv_ziffer": "§ 2 Nr. 1 BetrKV", "aktiv": True, "sortierung": 20},
            {"name": "Wasserversorgung & Entwässerung", "richtung": "ausgabe", "umlagefaehig": True, "standard_verteilerschluessel": "verbrauch", "betrkv_ziffer": "§ 2 Nr. 2/3 BetrKV", "aktiv": True, "sortierung": 21},
            {"name": "Heizung & Warmwasser (Brennstoff/Wartung)", "richtung": "ausgabe", "umlagefaehig": True, "standard_verteilerschluessel": "verbrauch", "betrkv_ziffer": "§ 2 Nr. 4/5 BetrKV", "aktiv": True, "sortierung": 22},
            {"name": "Straßenreinigung & Müllbeseitigung", "richtung": "ausgabe", "umlagefaehig": True, "standard_verteilerschluessel": "einheiten", "betrkv_ziffer": "§ 2 Nr. 8 BetrKV", "aktiv": True, "sortierung": 23},
            {"name": "Gebäudereinigung & Winterdienst", "richtung": "ausgabe", "umlagefaehig": True, "standard_verteilerschluessel": "wohnflaeche", "betrkv_ziffer": "§ 2 Nr. 9 BetrKV", "aktiv": True, "sortierung": 24},
            {"name": "Gartenpflege", "richtung": "ausgabe", "umlagefaehig": True, "standard_verteilerschluessel": "wohnflaeche", "betrkv_ziffer": "§ 2 Nr. 10 BetrKV", "aktiv": True, "sortierung": 25},
            {"name": "Allgemeinstrom / Beleuchtung", "richtung": "ausgabe", "umlagefaehig": True, "standard_verteilerschluessel": "wohnflaeche", "betrkv_ziffer": "§ 2 Nr. 11 BetrKV", "aktiv": True, "sortierung": 26},
            {"name": "Schornsteinfeger", "richtung": "ausgabe", "umlagefaehig": True, "standard_verteilerschluessel": "einheiten", "betrkv_ziffer": "§ 2 Nr. 12 BetrKV", "aktiv": True, "sortierung": 27},
            {"name": "Sach- und Haftpflichtversicherung", "richtung": "ausgabe", "umlagefaehig": True, "standard_verteilerschluessel": "wohnflaeche", "betrkv_ziffer": "§ 2 Nr. 13 BetrKV", "aktiv": True, "sortierung": 28},
            {"name": "Sonstige Betriebskosten", "richtung": "ausgabe", "umlagefaehig": True, "standard_verteilerschluessel": "wohnflaeche", "betrkv_ziffer": "§ 2 Nr. 17 BetrKV", "aktiv": True, "sortierung": 29},
            {"name": "Instandhaltung & Reparatur", "richtung": "ausgabe", "umlagefaehig": False, "standard_verteilerschluessel": "keiner", "betrkv_ziffer": None, "aktiv": True, "sortierung": 40},
            {"name": "Verwaltungskosten / Steuerberater", "richtung": "ausgabe", "umlagefaehig": False, "standard_verteilerschluessel": "keiner", "betrkv_ziffer": None, "aktiv": True, "sortierung": 41},
            {"name": "Darlehenszinsen", "richtung": "ausgabe", "umlagefaehig": False, "standard_verteilerschluessel": "keiner", "betrkv_ziffer": None, "aktiv": True, "sortierung": 42},
            {"name": "Darlehenstilgung", "richtung": "ausgabe", "umlagefaehig": False, "standard_verteilerschluessel": "keiner", "betrkv_ziffer": None, "aktiv": True, "sortierung": 43},
            {"name": "NK-Erstattung an Mieter", "richtung": "ausgabe", "umlagefaehig": False, "standard_verteilerschluessel": "direkt", "betrkv_ziffer": None, "aktiv": True, "sortierung": 44},
        ],
    )

    # 8. buchung
    op.create_table(
        "buchung",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("objekt_id", sa.Integer(), nullable=False),
        sa.Column("wohneinheit_id", sa.Integer(), nullable=True),
        sa.Column("mietvertrag_id", sa.Integer(), nullable=True),
        sa.Column("kostenart_id", sa.Integer(), nullable=False),
        sa.Column("buchungsdatum", sa.Date(), nullable=False),
        sa.Column("leistungszeitraum_von", sa.Date(), nullable=True),
        sa.Column("leistungszeitraum_bis", sa.Date(), nullable=True),
        sa.Column("betrag", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("empfaenger_sender", sa.String(length=200), nullable=False),
        sa.Column("verwendungszweck", sa.String(length=300), nullable=False),
        sa.Column("ist_sonderzahlung", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("belegnummer", sa.String(length=80), nullable=True),
        sa.Column("notizen", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("betrag <> 0", name="ck_buchung_betrag_ungleich_null"),
        sa.CheckConstraint(
            "leistungszeitraum_von IS NULL OR leistungszeitraum_bis IS NULL "
            "OR leistungszeitraum_bis >= leistungszeitraum_von",
            name="ck_buchung_leistungszeitraum_plausibel",
        ),
        sa.ForeignKeyConstraint(["kostenart_id"], ["kostenart.id"], name="fk_buchung_kostenart_id_kostenart", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["mietvertrag_id"], ["mietvertrag.id"], name="fk_buchung_mietvertrag_id_mietvertrag", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["objekt_id"], ["objekt.id"], name="fk_buchung_objekt_id_objekt", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["wohneinheit_id"], ["wohneinheit.id"], name="fk_buchung_wohneinheit_id_wohneinheit", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_buchung"),
    )
    op.create_index("ix_buchung_buchungsdatum", "buchung", ["buchungsdatum"])
    op.create_index("ix_buchung_kostenart_id", "buchung", ["kostenart_id"])
    op.create_index("ix_buchung_objekt_datum", "buchung", ["objekt_id", "buchungsdatum"])
    op.create_index("ix_buchung_einheit_datum", "buchung", ["wohneinheit_id", "buchungsdatum"])
    op.create_index("ix_buchung_vertrag_datum", "buchung", ["mietvertrag_id", "buchungsdatum"])

    # 9. kaution
    op.create_table(
        "kaution",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mietvertrag_id", sa.Integer(), nullable=False),
        sa.Column("vereinbarte_summe", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("anlageform", kaution_anlageform_enum, nullable=False),
        sa.Column("kontoreferenz", sa.String(length=120), nullable=True),
        sa.Column("status", kaution_status_enum, nullable=False, server_default="offen"),
        sa.Column("notizen", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("vereinbarte_summe >= 0", name="ck_kaution_vereinbarte_summe_nicht_negativ"),
        sa.ForeignKeyConstraint(["mietvertrag_id"], ["mietvertrag.id"], name="fk_kaution_mietvertrag_id_mietvertrag", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_kaution"),
        sa.UniqueConstraint("mietvertrag_id", name="uq_kaution_mietvertrag_id"),
    )

    # 10. kaution_bewegung
    op.create_table(
        "kaution_bewegung",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kaution_id", sa.Integer(), nullable=False),
        sa.Column("datum", sa.Date(), nullable=False),
        sa.Column("typ", kaution_bewegung_typ_enum, nullable=False),
        sa.Column("betrag", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("rate_nummer", sa.SmallInteger(), nullable=True),
        sa.Column("bemerkung", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("betrag > 0", name="ck_kaution_bewegung_bewegung_betrag_positiv"),
        sa.CheckConstraint("rate_nummer IS NULL OR (rate_nummer BETWEEN 1 AND 3)", name="ck_kaution_bewegung_rate_nummer_1_bis_3"),
        sa.ForeignKeyConstraint(["kaution_id"], ["kaution.id"], name="fk_kaution_bewegung_kaution_id_kaution", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_kaution_bewegung"),
    )
    op.create_index("ix_kaution_bewegung_kaution_id", "kaution_bewegung", ["kaution_id"])
    op.create_index("ix_kaution_bewegung_datum", "kaution_bewegung", ["datum"])

    # 11. dokument
    op.create_table(
        "dokument",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("objekt_id", sa.Integer(), nullable=False),
        sa.Column("wohneinheit_id", sa.Integer(), nullable=True),
        sa.Column("mietvertrag_id", sa.Integer(), nullable=True),
        sa.Column("buchung_id", sa.Integer(), nullable=True),
        sa.Column("kategorie", dokument_kategorie_enum, nullable=False),
        sa.Column("jahr", sa.SmallInteger(), nullable=False),
        sa.Column("original_dateiname", sa.String(length=255), nullable=False),
        sa.Column("relativer_pfad", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False, server_default="application/pdf"),
        sa.Column("dateigroesse_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("hochgeladen_am", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("beschreibung", sa.Text(), nullable=True),
        sa.CheckConstraint("jahr BETWEEN 1990 AND 2100", name="ck_dokument_jahr_plausibel"),
        sa.CheckConstraint("dateigroesse_bytes > 0", name="ck_dokument_dateigroesse_positiv"),
        sa.CheckConstraint("char_length(sha256_hash) = 64", name="ck_dokument_sha256_laenge_64"),
        sa.ForeignKeyConstraint(["buchung_id"], ["buchung.id"], name="fk_dokument_buchung_id_buchung", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["mietvertrag_id"], ["mietvertrag.id"], name="fk_dokument_mietvertrag_id_mietvertrag", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["objekt_id"], ["objekt.id"], name="fk_dokument_objekt_id_objekt", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["wohneinheit_id"], ["wohneinheit.id"], name="fk_dokument_wohneinheit_id_wohneinheit", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_dokument"),
        sa.UniqueConstraint("relativer_pfad", name="uq_dokument_relativer_pfad"),
    )
    op.create_index("ix_dokument_objekt_id", "dokument", ["objekt_id"])
    op.create_index("ix_dokument_wohneinheit_id", "dokument", ["wohneinheit_id"])
    op.create_index("ix_dokument_mietvertrag_id", "dokument", ["mietvertrag_id"])
    op.create_index("ix_dokument_buchung_id", "dokument", ["buchung_id"])
    op.create_index("ix_dokument_jahr", "dokument", ["jahr"])
    op.create_index("ix_dokument_sha256_hash", "dokument", ["sha256_hash"])

    # 12. PostgreSQL Views für dynamische Soll/Ist- und Kautionsauswertungen
    op.execute(SQL_CREATE_VIEW_KAUTION_STATUS)
    op.execute(SQL_CREATE_VIEW_EINHEIT_MONAT_SOLL_IST)
    op.execute(SQL_CREATE_VIEW_OBJEKT_CASHFLOW_MONAT)


def downgrade() -> None:
    bind = op.get_bind()

    op.execute(SQL_DROP_VIEWS)

    op.drop_table("dokument")
    op.drop_table("kaution_bewegung")
    op.drop_table("kaution")
    op.drop_table("buchung")
    op.drop_table("kostenart")
    op.drop_table("mietkonditionen_historie")
    op.drop_table("vertrag_mieter")
    op.drop_table("mietvertrag")
    op.drop_table("mieter")
    op.drop_table("wohneinheit")
    op.drop_table("objekt")

    for enum_type in reversed(ALL_ENUMS):
        enum_type.drop(bind, checkfirst=True)
