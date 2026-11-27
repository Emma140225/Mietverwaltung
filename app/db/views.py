"""PostgreSQL-View-Definitionen für Kautionsstatus sowie dynamische Soll/Ist- und Cashflow-Auswertungen."""

SQL_CREATE_VIEW_KAUTION_STATUS = """
CREATE OR REPLACE VIEW v_kaution_status_uebersicht AS
SELECT
    k.id AS kaution_id,
    k.mietvertrag_id,
    mv.wohneinheit_id,
    we.objekt_id,
    k.vereinbarte_summe,
    k.anlageform,
    k.kontoreferenz,
    k.status,
    COALESCE(SUM(kb.betrag) FILTER (WHERE kb.typ = 'einzahlung_rate'), 0.00)::numeric(10, 2) AS eingezahlt_summe,
    COALESCE(SUM(kb.betrag) FILTER (WHERE kb.typ = 'zinsgutschrift'), 0.00)::numeric(10, 2) AS zinsen_summe,
    COALESCE(SUM(kb.betrag) FILTER (WHERE kb.typ = 'einbehalt'), 0.00)::numeric(10, 2) AS einbehalten_summe,
    COALESCE(SUM(kb.betrag) FILTER (WHERE kb.typ = 'rueckzahlung'), 0.00)::numeric(10, 2) AS zurueckgezahlt_summe,
    (
        COALESCE(SUM(kb.betrag) FILTER (WHERE kb.typ IN ('einzahlung_rate', 'zinsgutschrift')), 0.00)
        - COALESCE(SUM(kb.betrag) FILTER (WHERE kb.typ IN ('einbehalt', 'rueckzahlung')), 0.00)
    )::numeric(10, 2) AS aktueller_bestand,
    GREATEST(
        k.vereinbarte_summe - COALESCE(SUM(kb.betrag) FILTER (WHERE kb.typ = 'einzahlung_rate'), 0.00),
        0.00
    )::numeric(10, 2) AS offene_einzahlung
FROM kaution k
JOIN mietvertrag mv ON mv.id = k.mietvertrag_id
JOIN wohneinheit we ON we.id = mv.wohneinheit_id
LEFT JOIN kaution_bewegung kb ON kb.kaution_id = k.id
GROUP BY k.id, mv.wohneinheit_id, we.objekt_id;
"""

SQL_CREATE_VIEW_EINHEIT_MONAT_SOLL_IST = """
CREATE OR REPLACE VIEW v_einheit_monat_soll_ist AS
WITH zeitraum_grenzen AS (
    SELECT
        date_trunc('month', LEAST(
            COALESCE((SELECT MIN(vertragsbeginn) FROM mietvertrag), CURRENT_DATE),
            COALESCE((SELECT MIN(buchungsdatum) FROM buchung), CURRENT_DATE),
            CURRENT_DATE
        ))::date AS min_monat,
        (date_trunc('month', CURRENT_DATE) + interval '12 months')::date AS max_monat
),
kalendermonate AS (
    SELECT
        gs::date AS monat_start,
        (gs + interval '1 month' - interval '1 day')::date AS monat_ende,
        ((gs + interval '1 month')::date - gs::date) AS tage_im_monat
    FROM zeitraum_grenzen zg,
    LATERAL generate_series(zg.min_monat, zg.max_monat, interval '1 month') AS gs
),
aktive_vertraege AS (
    SELECT
        we.id AS wohneinheit_id,
        km.monat_start,
        km.tage_im_monat,
        mv.id AS mietvertrag_id,
        GREATEST(km.monat_start, mv.vertragsbeginn) AS vertrag_eff_von,
        LEAST(km.monat_ende, COALESCE(mv.vertragsende, '9999-12-31'::date)) AS vertrag_eff_bis
    FROM wohneinheit we
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
    GROUP BY COALESCE(b.wohneinheit_id, mv.wohneinheit_id), date_trunc('month', b.buchungsdatum)::date
)
SELECT
    we.objekt_id,
    o.bezeichnung AS objekt_bezeichnung,
    we.id AS wohneinheit_id,
    we.bezeichnung AS wohneinheit_bezeichnung,
    we.lage_etage,
    we.status AS wohneinheit_status,
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
    ks.status AS kaution_status,
    ks.aktueller_bestand AS kaution_bestand,
    ks.offene_einzahlung AS kaution_offen
FROM wohneinheit we
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
  ON ks.mietvertrag_id = lv.mietvertrag_id;
"""

SQL_CREATE_VIEW_OBJEKT_CASHFLOW_MONAT = """
CREATE OR REPLACE VIEW v_objekt_cashflow_monat AS
WITH zeitraum_grenzen AS (
    SELECT
        date_trunc('month', LEAST(
            COALESCE((SELECT MIN(vertragsbeginn) FROM mietvertrag), CURRENT_DATE),
            COALESCE((SELECT MIN(buchungsdatum) FROM buchung), CURRENT_DATE),
            CURRENT_DATE
        ))::date AS min_monat,
        (date_trunc('month', CURRENT_DATE) + interval '12 months')::date AS max_monat
),
kalendermonate AS (
    SELECT gs::date AS monat_start
    FROM zeitraum_grenzen zg,
    LATERAL generate_series(zg.min_monat, zg.max_monat, interval '1 month') AS gs
),
soll_je_objekt_monat AS (
    SELECT
        objekt_id,
        monat AS monat_start,
        COALESCE(SUM(kaltmiete_soll), 0.00)::numeric(10, 2) AS kaltmiete_soll,
        COALESCE(SUM(nk_abschlag_soll), 0.00)::numeric(10, 2) AS nk_abschlag_soll,
        COALESCE(SUM(gesamt_soll), 0.00)::numeric(10, 2) AS gesamt_soll
    FROM v_einheit_monat_soll_ist
    GROUP BY objekt_id, monat
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
    GROUP BY b.objekt_id, date_trunc('month', b.buchungsdatum)::date
)
SELECT
    o.id AS objekt_id,
    o.bezeichnung AS objekt_bezeichnung,
    km.monat_start AS monat,
    COALESCE(s.kaltmiete_soll, 0.00)::numeric(10, 2) AS kaltmiete_soll,
    COALESCE(s.nk_abschlag_soll, 0.00)::numeric(10, 2) AS nk_abschlag_soll,
    COALESCE(s.gesamt_soll, 0.00)::numeric(10, 2) AS gesamt_soll,
    COALESCE(i.ist_mieteinnahmen, 0.00)::numeric(10, 2) AS ist_mieteinnahmen,
    COALESCE(i.ist_sonderzahlungen, 0.00)::numeric(10, 2) AS ist_sonderzahlungen,
    COALESCE(i.ist_einnahmen_gesamt, 0.00)::numeric(10, 2) AS ist_einnahmen_gesamt,
    (COALESCE(i.ist_mieteinnahmen, 0.00) - COALESCE(s.gesamt_soll, 0.00))::numeric(10, 2) AS miet_soll_ist_differenz,
    COALESCE(i.ausgaben_umlagefaehig, 0.00)::numeric(10, 2) AS ausgaben_umlagefaehig,
    COALESCE(i.ausgaben_nicht_umlagefaehig, 0.00)::numeric(10, 2) AS ausgaben_nicht_umlagefaehig,
    COALESCE(i.ausgaben_gesamt, 0.00)::numeric(10, 2) AS ausgaben_gesamt,
    (COALESCE(i.ist_einnahmen_gesamt, 0.00) - COALESCE(i.ausgaben_gesamt, 0.00))::numeric(10, 2) AS netto_cashflow
FROM objekt o
CROSS JOIN kalendermonate km
LEFT JOIN soll_je_objekt_monat s
  ON s.objekt_id = o.id AND s.monat_start = km.monat_start
LEFT JOIN ist_je_objekt_monat i
  ON i.objekt_id = o.id AND i.monat_start = km.monat_start;
"""

SQL_DROP_VIEWS = """
DROP VIEW IF EXISTS v_objekt_cashflow_monat;
DROP VIEW IF EXISTS v_einheit_monat_soll_ist;
DROP VIEW IF EXISTS v_kaution_status_uebersicht;
"""
