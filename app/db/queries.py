"""Parametrisierte SQL-Abfragen mit `generate_series` für beliebige Auswertungszeiträume."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class EinheitMonatSollIstRow:
    """Ergebniszeile der monatlichen Soll/Ist-Auswertung pro Wohneinheit."""

    objekt_id: int
    objekt_bezeichnung: str
    wohneinheit_id: int
    wohneinheit_bezeichnung: str
    lage_etage: str
    wohneinheit_status: str
    monat: date
    tage_im_monat: int
    vermietete_tage: int
    ist_leerstand: bool
    ist_teilleerstand: bool
    aktiver_mietvertrag_id: int | None
    kaltmiete_soll: Decimal
    bk_vorauszahlung_soll: Decimal
    hk_vorauszahlung_soll: Decimal
    nk_abschlag_soll: Decimal
    gesamt_soll: Decimal
    ist_zahlungseingang: Decimal
    differenz_saldo: Decimal
    sonderzahlungen: Decimal
    kaution_status: str | None
    kaution_bestand: Decimal | None
    kaution_offen: Decimal | None


@dataclass(frozen=True, slots=True)
class ObjektCashflowMonatRow:
    """Ergebniszeile der monatlichen Cashflow- und Kostenauswertung je Objekt."""

    objekt_id: int
    objekt_bezeichnung: str
    monat: date
    kaltmiete_soll: Decimal
    nk_abschlag_soll: Decimal
    gesamt_soll: Decimal
    ist_mieteinnahmen: Decimal
    ist_sonderzahlungen: Decimal
    ist_einnahmen_gesamt: Decimal
    miet_soll_ist_differenz: Decimal
    ausgaben_umlagefaehig: Decimal
    ausgaben_nicht_umlagefaehig: Decimal
    ausgaben_gesamt: Decimal
    netto_cashflow: Decimal


_SQL_EINHEIT_SOLL_IST_ZEITRAUM = text("""
WITH kalendermonate AS (
    SELECT
        gs::date AS monat_start,
        (gs + interval '1 month' - interval '1 day')::date AS monat_ende,
        ((gs + interval '1 month')::date - gs::date) AS tage_im_monat
    FROM generate_series(
        date_trunc('month', CAST(:von_monat AS date)),
        date_trunc('month', CAST(:bis_monat AS date)),
        interval '1 month'
    ) AS gs
),
gefilterte_einheiten AS (
    SELECT we.*
    FROM wohneinheit we
    WHERE (CAST(:objekt_id AS integer) IS NULL OR we.objekt_id = CAST(:objekt_id AS integer))
      AND (CAST(:wohneinheit_id AS integer) IS NULL OR we.id = CAST(:wohneinheit_id AS integer))
),
aktive_vertraege AS (
    SELECT
        we.id AS wohneinheit_id,
        km.monat_start,
        km.tage_im_monat,
        mv.id AS mietvertrag_id,
        GREATEST(km.monat_start, mv.vertragsbeginn) AS vertrag_eff_von,
        LEAST(km.monat_ende, COALESCE(mv.vertragsende, '9999-12-31'::date)) AS vertrag_eff_bis
    FROM gefilterte_einheiten we
    CROSS JOIN kalendermonate km
    JOIN mietvertrag mv
      ON mv.wohneinheit_id = we.id
     AND mv.vertragsbeginn <= km.monat_ende
     AND COALESCE(mv.vertragsende, '9999-12-31'::date) >= km.monat_start
),
belegung_je_einheit_monat AS (
    SELECT
        av.wohneinheit_id,
        av.monat_start,
        LEAST(SUM(av.vertrag_eff_bis - av.vertrag_eff_von + 1), MAX(av.tage_im_monat))::integer AS vermietete_tage
    FROM aktive_vertraege av
    GROUP BY av.wohneinheit_id, av.monat_start
),
letzter_vertrag_je_einheit_monat AS (
    SELECT DISTINCT ON (av.wohneinheit_id, av.monat_start)
        av.wohneinheit_id,
        av.monat_start,
        av.mietvertrag_id
    FROM aktive_vertraege av
    ORDER BY av.wohneinheit_id, av.monat_start, av.vertrag_eff_bis DESC, av.mietvertrag_id DESC
),
soll_anteilig AS (
    SELECT
        av.wohneinheit_id,
        av.monat_start,
        ROUND(
            SUM(
                mk.kaltmiete
                * ((LEAST(av.vertrag_eff_bis, COALESCE(mk.gueltig_bis, '9999-12-31'::date))
                    - GREATEST(av.vertrag_eff_von, mk.gueltig_ab) + 1)::numeric)
                / av.tage_im_monat::numeric
            ),
            2
        )::numeric(10, 2) AS kaltmiete_soll,
        ROUND(
            SUM(
                mk.betriebskosten_vorauszahlung
                * ((LEAST(av.vertrag_eff_bis, COALESCE(mk.gueltig_bis, '9999-12-31'::date))
                    - GREATEST(av.vertrag_eff_von, mk.gueltig_ab) + 1)::numeric)
                / av.tage_im_monat::numeric
            ),
            2
        )::numeric(10, 2) AS bk_vorauszahlung_soll,
        ROUND(
            SUM(
                mk.heizkosten_vorauszahlung
                * ((LEAST(av.vertrag_eff_bis, COALESCE(mk.gueltig_bis, '9999-12-31'::date))
                    - GREATEST(av.vertrag_eff_von, mk.gueltig_ab) + 1)::numeric)
                / av.tage_im_monat::numeric
            ),
            2
        )::numeric(10, 2) AS hk_vorauszahlung_soll,
        ROUND(
            SUM(
                (mk.betriebskosten_vorauszahlung + mk.heizkosten_vorauszahlung)
                * ((LEAST(av.vertrag_eff_bis, COALESCE(mk.gueltig_bis, '9999-12-31'::date))
                    - GREATEST(av.vertrag_eff_von, mk.gueltig_ab) + 1)::numeric)
                / av.tage_im_monat::numeric
            ),
            2
        )::numeric(10, 2) AS nk_abschlag_soll
    FROM aktive_vertraege av
    JOIN mietkonditionen_historie mk
      ON mk.mietvertrag_id = av.mietvertrag_id
     AND mk.gueltig_ab <= av.vertrag_eff_bis
     AND COALESCE(mk.gueltig_bis, '9999-12-31'::date) >= av.vertrag_eff_von
    GROUP BY av.wohneinheit_id, av.monat_start
),
ist_einheit_monat AS (
    SELECT
        COALESCE(b.wohneinheit_id, mv.wohneinheit_id) AS wohneinheit_id,
        date_trunc('month', b.buchungsdatum)::date AS monat_start,
        COALESCE(SUM(b.betrag) FILTER (WHERE ka.richtung = 'einnahme' AND NOT b.ist_sonderzahlung), 0.00)::numeric(10, 2) AS ist_zahlungseingang,
        COALESCE(SUM(b.betrag) FILTER (WHERE ka.richtung = 'einnahme' AND b.ist_sonderzahlung), 0.00)::numeric(10, 2) AS sonderzahlungen
    FROM buchung b
    JOIN kostenart ka ON ka.id = b.kostenart_id
    LEFT JOIN mietvertrag mv ON mv.id = b.mietvertrag_id
    WHERE COALESCE(b.wohneinheit_id, mv.wohneinheit_id) IS NOT NULL
      AND ka.richtung = 'einnahme'
      AND b.buchungsdatum >= date_trunc('month', CAST(:von_monat AS date))::date
      AND b.buchungsdatum < (date_trunc('month', CAST(:bis_monat AS date)) + interval '1 month')::date
    GROUP BY COALESCE(b.wohneinheit_id, mv.wohneinheit_id), date_trunc('month', b.buchungsdatum)::date
)
SELECT
    we.objekt_id,
    o.bezeichnung AS objekt_bezeichnung,
    we.id AS wohneinheit_id,
    we.bezeichnung AS wohneinheit_bezeichnung,
    we.lage_etage,
    we.status::text AS wohneinheit_status,
    km.monat_start AS monat,
    km.tage_im_monat,
    COALESCE(bjem.vermietete_tage, 0) AS vermietete_tage,
    (COALESCE(bjem.vermietete_tage, 0) = 0) AS ist_leerstand,
    (COALESCE(bjem.vermietete_tage, 0) > 0 AND COALESCE(bjem.vermietete_tage, 0) < km.tage_im_monat) AS ist_teilleerstand,
    lv.mietvertrag_id AS aktiver_mietvertrag_id,
    COALESCE(sa.kaltmiete_soll, 0.00)::numeric(10, 2) AS kaltmiete_soll,
    COALESCE(sa.bk_vorauszahlung_soll, 0.00)::numeric(10, 2) AS bk_vorauszahlung_soll,
    COALESCE(sa.hk_vorauszahlung_soll, 0.00)::numeric(10, 2) AS hk_vorauszahlung_soll,
    COALESCE(sa.nk_abschlag_soll, 0.00)::numeric(10, 2) AS nk_abschlag_soll,
    (COALESCE(sa.kaltmiete_soll, 0.00) + COALESCE(sa.nk_abschlag_soll, 0.00))::numeric(10, 2) AS gesamt_soll,
    COALESCE(iem.ist_zahlungseingang, 0.00)::numeric(10, 2) AS ist_zahlungseingang,
    (
        COALESCE(iem.ist_zahlungseingang, 0.00)
        - (COALESCE(sa.kaltmiete_soll, 0.00) + COALESCE(sa.nk_abschlag_soll, 0.00))
    )::numeric(10, 2) AS differenz_saldo,
    COALESCE(iem.sonderzahlungen, 0.00)::numeric(10, 2) AS sonderzahlungen,
    ks.status::text AS kaution_status,
    ks.aktueller_bestand AS kaution_bestand,
    ks.offene_einzahlung AS kaution_offen
FROM gefilterte_einheiten we
JOIN objekt o ON o.id = we.objekt_id
CROSS JOIN kalendermonate km
LEFT JOIN belegung_je_einheit_monat bjem
  ON bjem.wohneinheit_id = we.id AND bjem.monat_start = km.monat_start
LEFT JOIN letzter_vertrag_je_einheit_monat lv
  ON lv.wohneinheit_id = we.id AND lv.monat_start = km.monat_start
LEFT JOIN soll_anteilig sa
  ON sa.wohneinheit_id = we.id AND sa.monat_start = km.monat_start
LEFT JOIN ist_einheit_monat iem
  ON iem.wohneinheit_id = we.id AND iem.monat_start = km.monat_start
LEFT JOIN v_kaution_status_uebersicht ks
  ON ks.mietvertrag_id = lv.mietvertrag_id
ORDER BY o.bezeichnung, we.bezeichnung, km.monat_start;
""")

_SQL_OBJEKT_CASHFLOW_ZEITRAUM = text("""
WITH kalendermonate AS (
    SELECT
        gs::date AS monat_start,
        (gs + interval '1 month' - interval '1 day')::date AS monat_ende,
        ((gs + interval '1 month')::date - gs::date) AS tage_im_monat
    FROM generate_series(
        date_trunc('month', CAST(:von_monat AS date)),
        date_trunc('month', CAST(:bis_monat AS date)),
        interval '1 month'
    ) AS gs
),
gefilterte_objekte AS (
    SELECT o.*
    FROM objekt o
    WHERE (CAST(:objekt_id AS integer) IS NULL OR o.id = CAST(:objekt_id AS integer))
),
aktive_vertraege AS (
    SELECT
        we.objekt_id,
        km.monat_start,
        km.tage_im_monat,
        mv.id AS mietvertrag_id,
        GREATEST(km.monat_start, mv.vertragsbeginn) AS vertrag_eff_von,
        LEAST(km.monat_ende, COALESCE(mv.vertragsende, '9999-12-31'::date)) AS vertrag_eff_bis
    FROM gefilterte_objekte o
    JOIN wohneinheit we ON we.objekt_id = o.id
    CROSS JOIN kalendermonate km
    JOIN mietvertrag mv
      ON mv.wohneinheit_id = we.id
     AND mv.vertragsbeginn <= km.monat_ende
     AND COALESCE(mv.vertragsende, '9999-12-31'::date) >= km.monat_start
),
soll_je_objekt_monat AS (
    SELECT
        av.objekt_id,
        av.monat_start,
        ROUND(
            SUM(
                mk.kaltmiete
                * ((LEAST(av.vertrag_eff_bis, COALESCE(mk.gueltig_bis, '9999-12-31'::date))
                    - GREATEST(av.vertrag_eff_von, mk.gueltig_ab) + 1)::numeric)
                / av.tage_im_monat::numeric
            ),
            2
        )::numeric(10, 2) AS kaltmiete_soll,
        ROUND(
            SUM(
                (mk.betriebskosten_vorauszahlung + mk.heizkosten_vorauszahlung)
                * ((LEAST(av.vertrag_eff_bis, COALESCE(mk.gueltig_bis, '9999-12-31'::date))
                    - GREATEST(av.vertrag_eff_von, mk.gueltig_ab) + 1)::numeric)
                / av.tage_im_monat::numeric
            ),
            2
        )::numeric(10, 2) AS nk_abschlag_soll
    FROM aktive_vertraege av
    JOIN mietkonditionen_historie mk
      ON mk.mietvertrag_id = av.mietvertrag_id
     AND mk.gueltig_ab <= av.vertrag_eff_bis
     AND COALESCE(mk.gueltig_bis, '9999-12-31'::date) >= av.vertrag_eff_von
    GROUP BY av.objekt_id, av.monat_start
),
ist_je_objekt_monat AS (
    SELECT
        b.objekt_id,
        date_trunc('month', b.buchungsdatum)::date AS monat_start,
        COALESCE(SUM(b.betrag) FILTER (WHERE ka.richtung = 'einnahme' AND NOT b.ist_sonderzahlung), 0.00)::numeric(10, 2) AS ist_mieteinnahmen,
        COALESCE(SUM(b.betrag) FILTER (WHERE ka.richtung = 'einnahme' AND b.ist_sonderzahlung), 0.00)::numeric(10, 2) AS ist_sonderzahlungen,
        COALESCE(SUM(b.betrag) FILTER (WHERE ka.richtung = 'einnahme'), 0.00)::numeric(10, 2) AS ist_einnahmen_gesamt,
        COALESCE(SUM(b.betrag) FILTER (WHERE ka.richtung = 'ausgabe' AND ka.umlagefaehig), 0.00)::numeric(10, 2) AS ausgaben_umlagefaehig,
        COALESCE(SUM(b.betrag) FILTER (WHERE ka.richtung = 'ausgabe' AND NOT ka.umlagefaehig), 0.00)::numeric(10, 2) AS ausgaben_nicht_umlagefaehig,
        COALESCE(SUM(b.betrag) FILTER (WHERE ka.richtung = 'ausgabe'), 0.00)::numeric(10, 2) AS ausgaben_gesamt
    FROM buchung b
    JOIN kostenart ka ON ka.id = b.kostenart_id
    WHERE b.buchungsdatum >= date_trunc('month', CAST(:von_monat AS date))::date
      AND b.buchungsdatum < (date_trunc('month', CAST(:bis_monat AS date)) + interval '1 month')::date
      AND (CAST(:objekt_id AS integer) IS NULL OR b.objekt_id = CAST(:objekt_id AS integer))
    GROUP BY b.objekt_id, date_trunc('month', b.buchungsdatum)::date
)
SELECT
    o.id AS objekt_id,
    o.bezeichnung AS objekt_bezeichnung,
    km.monat_start AS monat,
    COALESCE(s.kaltmiete_soll, 0.00)::numeric(10, 2) AS kaltmiete_soll,
    COALESCE(s.nk_abschlag_soll, 0.00)::numeric(10, 2) AS nk_abschlag_soll,
    (COALESCE(s.kaltmiete_soll, 0.00) + COALESCE(s.nk_abschlag_soll, 0.00))::numeric(10, 2) AS gesamt_soll,
    COALESCE(i.ist_mieteinnahmen, 0.00)::numeric(10, 2) AS ist_mieteinnahmen,
    COALESCE(i.ist_sonderzahlungen, 0.00)::numeric(10, 2) AS ist_sonderzahlungen,
    COALESCE(i.ist_einnahmen_gesamt, 0.00)::numeric(10, 2) AS ist_einnahmen_gesamt,
    (
        COALESCE(i.ist_mieteinnahmen, 0.00)
        - (COALESCE(s.kaltmiete_soll, 0.00) + COALESCE(s.nk_abschlag_soll, 0.00))
    )::numeric(10, 2) AS miet_soll_ist_differenz,
    COALESCE(i.ausgaben_umlagefaehig, 0.00)::numeric(10, 2) AS ausgaben_umlagefaehig,
    COALESCE(i.ausgaben_nicht_umlagefaehig, 0.00)::numeric(10, 2) AS ausgaben_nicht_umlagefaehig,
    COALESCE(i.ausgaben_gesamt, 0.00)::numeric(10, 2) AS ausgaben_gesamt,
    (COALESCE(i.ist_einnahmen_gesamt, 0.00) - COALESCE(i.ausgaben_gesamt, 0.00))::numeric(10, 2) AS netto_cashflow
FROM gefilterte_objekte o
CROSS JOIN kalendermonate km
LEFT JOIN soll_je_objekt_monat s
  ON s.objekt_id = o.id AND s.monat_start = km.monat_start
LEFT JOIN ist_je_objekt_monat i
  ON i.objekt_id = o.id AND i.monat_start = km.monat_start
ORDER BY o.bezeichnung, km.monat_start;
""")


async def fetch_einheit_soll_ist(
    session: AsyncSession,
    von_monat: date,
    bis_monat: date,
    *,
    objekt_id: int | None = None,
    wohneinheit_id: int | None = None,
) -> list[EinheitMonatSollIstRow]:
    """Berechnet dynamisch Soll/Ist-Werte pro Wohneinheit und Kalendermonat via `generate_series`."""
    result = await session.execute(
        _SQL_EINHEIT_SOLL_IST_ZEITRAUM,
        {
            "von_monat": von_monat.replace(day=1),
            "bis_monat": bis_monat.replace(day=1),
            "objekt_id": objekt_id,
            "wohneinheit_id": wohneinheit_id,
        },
    )
    return [EinheitMonatSollIstRow(**dict(row)) for row in result.mappings().all()]


async def fetch_objekt_cashflow(
    session: AsyncSession,
    von_monat: date,
    bis_monat: date,
    *,
    objekt_id: int | None = None,
) -> list[ObjektCashflowMonatRow]:
    """Berechnet monatlichen Cashflow (Soll, Ist, umlagefähige/nicht-umlagefähige Kosten) je Objekt."""
    result = await session.execute(
        _SQL_OBJEKT_CASHFLOW_ZEITRAUM,
        {
            "von_monat": von_monat.replace(day=1),
            "bis_monat": bis_monat.replace(day=1),
            "objekt_id": objekt_id,
        },
    )
    return [ObjektCashflowMonatRow(**dict(row)) for row in result.mappings().all()]
