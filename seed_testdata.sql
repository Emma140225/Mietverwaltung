-- ============================================================================
-- Private Hausverwaltung – Umfassende Testdaten (Stand: 2026)
-- ============================================================================
-- Deckt alle Kernfunktionen ab:
--   1. 2 Objekte & 4 Wohneinheiten (inkl. Leerstand & halbe Zimmer)
--   2. 5 Mieter inkl. Nachsendeanschrift nach Auszug & IBAN
--   3. 4 Mietverträge (inkl. 2 Mieter in einem Vertrag, Kündigung, Mieterwechsel)
--   4. Historisierte Mietkonditionen (Mieterhöhung zum Stichtag 01.07.2026)
--   5. Unterjähriger Ein-/Auszug (taggenaue Proration im April & Mai 2026)
--   6. Getrennte Kautionskonten (vollständig, abgerechnet mit Einbehalt, offene Raten)
--   7. Lückenlose Buchungen 2026 (Mieteinnahmen, Sonderzahlung, Rückstände,
--      umlagefähige BetrKV-Gesamtobjektkosten & nicht umlagefähige Eigentümerkosten)
--
-- Einspielen (lokal via Docker):
--   docker exec -i mietverwaltung-db psql -U hausverwaltung -d mietverwaltung < seed_testdata.sql
-- ============================================================================

BEGIN;

-- Bestehende Bewegungs-/Stammdaten sauber zurücksetzen (Kostenarten bleiben erhalten)
TRUNCATE TABLE
    dokument,
    kaution_bewegung,
    kaution,
    buchung,
    mietkonditionen_historie,
    vertrag_mieter,
    mietvertrag,
    mieter,
    wohneinheit,
    objekt
RESTART IDENTITY CASCADE;

-- ----------------------------------------------------------------------------
-- 1. Objekte
-- ----------------------------------------------------------------------------
INSERT INTO objekt (id, bezeichnung, strasse, plz, ort, baujahr, gesamtflaeche_qm, notizen)
VALUES
    (1, 'MFH Hauptstraße 12', 'Hauptstraße 12', '10115', 'Berlin', 1978, 320.00, '3-Parteien-Mehrfamilienhaus mit Gaszentralheizung'),
    (2, 'DHH Gartenweg 4', 'Gartenweg 4', '80331', 'München', 2012, 135.00, 'Doppelhaushälfte mit Wärmepumpe und Carport');

SELECT setval(pg_get_serial_sequence('objekt', 'id'), (SELECT MAX(id) FROM objekt));

-- ----------------------------------------------------------------------------
-- 2. Wohneinheiten
-- ----------------------------------------------------------------------------
INSERT INTO wohneinheit (id, objekt_id, bezeichnung, lage_etage, wohnflaeche_qm, zimmeranzahl, status, notizen)
VALUES
    (1, 1, 'WE 01 - EG links', 'EG links', 75.00, 3.0, 'vermietet', 'Mit Balkon zum Innenhof'),
    (2, 1, 'WE 02 - 1. OG rechts', '1. OG rechts', 82.50, 3.5, 'vermietet', 'Saniert 2023; Mieterwechsel im Frühjahr 2026'),
    (3, 1, 'WE 03 - Dachgeschoss', 'DG', 58.00, 2.5, 'leerstand', 'Aktuell in Neuvermietung nach Grundrenovierung'),
    (4, 2, 'Gartenweg 4 (Gesamthaus)', 'EG + OG + DG', 135.00, 5.0, 'vermietet', 'Einfamilien-Vermietung inkl. Gartenanteil');

SELECT setval(pg_get_serial_sequence('wohneinheit', 'id'), (SELECT MAX(id) FROM wohneinheit));

-- ----------------------------------------------------------------------------
-- 3. Mieter
-- ----------------------------------------------------------------------------
INSERT INTO mieter (id, anrede, vorname, nachname, email, telefon, aktuelle_strasse, aktuelle_plz, aktueller_ort, iban, notizen)
VALUES
    (1, 'Frau', 'Anna', 'Weber', 'anna.weber@example.de', '0171 1122334', 'Hauptstraße 12', '10115', 'Berlin', 'DE89370400440532013000', 'Langjährige Mieterin'),
    (2, 'Herr', 'Lukas', 'Bauer', 'lukas.bauer@example.de', '0172 9988776', 'Schillerweg 8 (Nachsendeanschrift)', '10625', 'Berlin', 'DE12500105170648489890', 'Ausgezogen am 15.04.2026'),
    (3, 'Frau', 'Sofia', 'Keller', 'sofia.keller@example.de', '0176 5544332', 'Hauptstraße 12', '10115', 'Berlin', 'DE44500105175407324931', 'Eingezogen am 16.05.2026'),
    (4, 'Herr', 'Maximilian', 'Hoffmann', 'm.hoffmann@example.de', '0151 2233445', 'Gartenweg 4', '80331', 'München', 'DE75512108001245126199', 'Hauptmieter DHH'),
    (5, 'Frau', 'Laura', 'Hoffmann', 'l.hoffmann@example.de', '0151 2233446', 'Gartenweg 4', '80331', 'München', NULL, 'Mitmieterin DHH');

SELECT setval(pg_get_serial_sequence('mieter', 'id'), (SELECT MAX(id) FROM mieter));

-- ----------------------------------------------------------------------------
-- 4. Mietverträge & Mieterzuordnungen
-- ----------------------------------------------------------------------------
INSERT INTO mietvertrag (id, wohneinheit_id, vertragsnummer, vertragsbeginn, vertragsende, kuendigungsdatum, zahlungsziel_werktag, notizen)
VALUES
    (1, 1, 'MV-2024-001', '2024-01-01', NULL, NULL, 3, 'Unbefristeter Mietvertrag WE 01'),
    (2, 2, 'MV-2023-002', '2023-03-01', '2026-04-15', '2026-01-20', 3, 'Unterjähriger Auszug zum 15.04.2026'),
    (3, 2, 'MV-2026-003', '2026-05-16', NULL, NULL, 3, 'Unterjähriger Einzug zum 16.05.2026'),
    (4, 4, 'MV-2025-004', '2025-10-01', NULL, NULL, 3, 'Ehepaar gemeinsam im Vertrag');

SELECT setval(pg_get_serial_sequence('mietvertrag', 'id'), (SELECT MAX(id) FROM mietvertrag));

INSERT INTO vertrag_mieter (mietvertrag_id, mieter_id, hauptmieter, einzugsdatum_mieter, auszugsdatum_mieter)
VALUES
    (1, 1, true,  '2024-01-01', NULL),
    (2, 2, true,  '2023-03-01', '2026-04-15'),
    (3, 3, true,  '2026-05-16', NULL),
    (4, 4, true,  '2025-10-01', NULL),
    (4, 5, false, '2025-10-01', NULL);

-- ----------------------------------------------------------------------------
-- 5. Historisierte Miet- und Abschlagskonditionen (überlappungsfrei)
-- ----------------------------------------------------------------------------
INSERT INTO mietkonditionen_historie
    (mietvertrag_id, gueltig_ab, gueltig_bis, kaltmiete, betriebskosten_vorauszahlung, heizkosten_vorauszahlung, aenderungsgrund)
VALUES
    -- Vertrag 1 (WE 01): Mieterhöhung & NK-Anpassung zum 01.07.2026
    (1, '2024-01-01', '2026-06-30', 750.00, 150.00, 90.00, 'Vertragsbeginn'),
    (1, '2026-07-01', NULL,         810.00, 170.00, 95.00, 'Mieterhöhung § 558 BGB & NK-Anpassung'),
    -- Vertrag 2 (WE 02 Altmieter)
    (2, '2023-03-01', '2026-04-15', 820.00, 160.00, 100.00, 'Vertragsbeginn'),
    -- Vertrag 3 (WE 02 Neumieter)
    (3, '2026-05-16', NULL,         890.00, 180.00, 110.00, 'Neuvermietung nach Sanierung'),
    -- Vertrag 4 (WE 04)
    (4, '2025-10-01', NULL,        1450.00, 220.00, 150.00, 'Vertragsbeginn');

-- ----------------------------------------------------------------------------
-- 6. Getrennte Kautionskonten & Bewegungen
-- ----------------------------------------------------------------------------
INSERT INTO kaution (id, mietvertrag_id, vereinbarte_summe, anlageform, kontoreferenz, status, notizen)
VALUES
    (1, 1, 2250.00, 'mietkautionskonto', 'DE90100500000190123456', 'vollstaendig', 'Vollständig in 3 Raten gezahlt'),
    (2, 2, 2460.00, 'sparbuch_verpfaendet', 'SB-44120987', 'abgerechnet', 'Nach Auszug abgerechnet (350 EUR Einbehalt)'),
    (3, 3, 2670.00, 'mietkautionskonto', 'DE90100500000190654321', 'teilweise_eingegangen', 'Rate 3 noch offen'),
    (4, 4, 4350.00, 'mietkautionskonto', 'DE11700500000088112233', 'teilweise_eingegangen', 'Rate 1 gezahlt, Raten 2 und 3 offen');

SELECT setval(pg_get_serial_sequence('kaution', 'id'), (SELECT MAX(id) FROM kaution));

INSERT INTO kaution_bewegung (kaution_id, datum, typ, betrag, rate_nummer, bemerkung)
VALUES
    -- Kaution 1 (vollständig + Zinsgutschrift)
    (1, '2024-01-05', 'einzahlung_rate', 750.00, 1, '1. Rate bei Einzug'),
    (1, '2024-02-05', 'einzahlung_rate', 750.00, 2, '2. Rate'),
    (1, '2024-03-05', 'einzahlung_rate', 750.00, 3, '3. Rate'),
    (1, '2025-12-31', 'zinsgutschrift',   18.45, NULL, 'Jahreszins 2025'),
    -- Kaution 2 (abgerechnet bei Auszug)
    (2, '2023-03-02', 'einzahlung_rate', 2460.00, 1, 'Einmalzahlung bei Einzug'),
    (2, '2025-12-31', 'zinsgutschrift',    22.10, NULL, 'Zinsgutschrift bis Auszug'),
    (2, '2026-05-10', 'einbehalt',        350.00, NULL, 'Einbehalt Schönheitsreparaturen Flur'),
    (2, '2026-05-10', 'rueckzahlung',    2132.10, NULL, 'Restauszahlung auf Mieter-IBAN'),
    -- Kaution 3 (2 von 3 Raten gezahlt -> 890,00 EUR offen)
    (3, '2026-05-18', 'einzahlung_rate', 890.00, 1, '1. Rate (§ 551 BGB)'),
    (3, '2026-06-04', 'einzahlung_rate', 890.00, 2, '2. Rate (§ 551 BGB)'),
    -- Kaution 4 (1 von 3 Raten gezahlt -> 2.900,00 EUR offen)
    (4, '2025-10-05', 'einzahlung_rate', 1450.00, 1, '1. Rate (§ 551 BGB)');

-- ----------------------------------------------------------------------------
-- 7. Buchungen 2026: Mieteinnahmen, Sonderzahlung, Umlagefähige & Eigentümerkosten
-- ----------------------------------------------------------------------------

-- 7a) WE 01 (Vertrag 1): Jan-Jun je 990,00 EUR, Jul-Okt je 1.075,00 EUR, Nov nur 875,00 EUR (200 EUR Rückstand!)
INSERT INTO buchung (objekt_id, wohneinheit_id, mietvertrag_id, kostenart_id, buchungsdatum, betrag, empfaenger_sender, verwendungszweck, ist_sonderzahlung)
SELECT 1, 1, 1,
       (SELECT id FROM kostenart WHERE name = 'Mietzahlung (Kalt + Abschläge)' LIMIT 1),
       d::date,
       CASE WHEN d < '2026-07-01' THEN 990.00
            WHEN d = '2026-11-03' THEN 875.00
            ELSE 1075.00
       END,
       'Anna Weber',
       'Miete ' || to_char(d, 'MM/YYYY') || ' WE 01',
       false
FROM generate_series('2026-01-03'::date, '2026-11-03'::date, interval '1 month') AS d;

-- 7b) WE 02: Altmieter Jan-März voll (1.080,00 EUR), April anteilig 15/30 Tage (540,00 EUR)
INSERT INTO buchung (objekt_id, wohneinheit_id, mietvertrag_id, kostenart_id, buchungsdatum, betrag, empfaenger_sender, verwendungszweck, ist_sonderzahlung)
VALUES
    (1, 2, 2, (SELECT id FROM kostenart WHERE name = 'Mietzahlung (Kalt + Abschläge)' LIMIT 1), '2026-01-03', 1080.00, 'Lukas Bauer', 'Miete 01/2026 WE 02', false),
    (1, 2, 2, (SELECT id FROM kostenart WHERE name = 'Mietzahlung (Kalt + Abschläge)' LIMIT 1), '2026-02-03', 1080.00, 'Lukas Bauer', 'Miete 02/2026 WE 02', false),
    (1, 2, 2, (SELECT id FROM kostenart WHERE name = 'Mietzahlung (Kalt + Abschläge)' LIMIT 1), '2026-03-03', 1080.00, 'Lukas Bauer', 'Miete 03/2026 WE 02', false),
    (1, 2, 2, (SELECT id FROM kostenart WHERE name = 'Mietzahlung (Kalt + Abschläge)' LIMIT 1), '2026-04-03',  540.00, 'Lukas Bauer', 'Miete anteilig 01.-15.04.2026 WE 02', false),
    -- Sonderzahlung aus externer NK-Abrechnung 2025 (darf laufendes Miet-Soll/Ist nicht verzerren)
    (1, 2, 2, (SELECT id FROM kostenart WHERE name = 'NK-Nachzahlung (Sonderzahlung)' LIMIT 1), '2026-08-14',  245.80, 'Lukas Bauer', 'Nachzahlung NK-Abrechnung 2025', true);

-- 7c) WE 02: Neumieter Mai anteilig 16/31 Tage (609,03 EUR), Jun-Nov voll (1.180,00 EUR)
INSERT INTO buchung (objekt_id, wohneinheit_id, mietvertrag_id, kostenart_id, buchungsdatum, betrag, empfaenger_sender, verwendungszweck, ist_sonderzahlung)
VALUES
    (1, 2, 3, (SELECT id FROM kostenart WHERE name = 'Mietzahlung (Kalt + Abschläge)' LIMIT 1), '2026-05-18',  609.03, 'Sofia Keller', 'Miete anteilig 16.-31.05.2026 WE 02', false);

INSERT INTO buchung (objekt_id, wohneinheit_id, mietvertrag_id, kostenart_id, buchungsdatum, betrag, empfaenger_sender, verwendungszweck, ist_sonderzahlung)
SELECT 1, 2, 3,
       (SELECT id FROM kostenart WHERE name = 'Mietzahlung (Kalt + Abschläge)' LIMIT 1),
       d::date,
       1180.00,
       'Sofia Keller',
       'Miete ' || to_char(d, 'MM/YYYY') || ' WE 02',
       false
FROM generate_series('2026-06-03'::date, '2026-11-03'::date, interval '1 month') AS d;

-- 7d) WE 04 (Objekt 2): Jan-Nov je 1.820,00 EUR, im Oktober Teilzahlung 1.500,00 EUR (320 EUR Rückstand!)
INSERT INTO buchung (objekt_id, wohneinheit_id, mietvertrag_id, kostenart_id, buchungsdatum, betrag, empfaenger_sender, verwendungszweck, ist_sonderzahlung)
SELECT 2, 4, 4,
       (SELECT id FROM kostenart WHERE name = 'Mietzahlung (Kalt + Abschläge)' LIMIT 1),
       d::date,
       CASE WHEN d = '2026-10-03' THEN 1500.00 ELSE 1820.00 END,
       'Maximilian Hoffmann',
       'Miete ' || to_char(d, 'MM/YYYY') || ' Gartenweg 4',
       false
FROM generate_series('2026-01-03'::date, '2026-11-03'::date, interval '1 month') AS d;

-- 7e) Umlagefähige Betriebskosten (BetrKV) - Gesamtobjektkosten (wohneinheit_id = NULL)
INSERT INTO buchung (objekt_id, wohneinheit_id, mietvertrag_id, kostenart_id, buchungsdatum, leistungszeitraum_von, leistungszeitraum_bis, betrag, empfaenger_sender, verwendungszweck, ist_sonderzahlung, belegnummer)
VALUES
    -- Objekt 1 (MFH Hauptstraße 12)
    (1, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Grundsteuer' LIMIT 1), '2026-02-15', '2026-01-01', '2026-03-31', 312.50, 'Finanzamt Berlin', 'Grundsteuer Q1/2026', false, 'GS-2026-Q1'),
    (1, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Grundsteuer' LIMIT 1), '2026-05-15', '2026-04-01', '2026-06-30', 312.50, 'Finanzamt Berlin', 'Grundsteuer Q2/2026', false, 'GS-2026-Q2'),
    (1, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Grundsteuer' LIMIT 1), '2026-08-15', '2026-07-01', '2026-09-30', 312.50, 'Finanzamt Berlin', 'Grundsteuer Q3/2026', false, 'GS-2026-Q3'),
    (1, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Grundsteuer' LIMIT 1), '2026-11-15', '2026-10-01', '2026-12-31', 312.50, 'Finanzamt Berlin', 'Grundsteuer Q4/2026', false, 'GS-2026-Q4'),
    (1, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Sach- und Haftpflichtversicherung' LIMIT 1), '2026-01-12', '2026-01-01', '2026-12-31', 1480.00, 'Allianz Wohngebäude', 'Wohngebäude- & Haus-Haftpflicht 2026', false, 'VERS-2026-12'),
    (1, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Wasserversorgung & Entwässerung' LIMIT 1), '2026-03-20', '2026-01-01', '2026-06-30', 740.00, 'Berliner Wasserbetriebe', 'Abschlag Wasser/Abwasser H1/2026', false, 'BWB-2026-01'),
    (1, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Wasserversorgung & Entwässerung' LIMIT 1), '2026-09-20', '2026-07-01', '2026-12-31', 740.00, 'Berliner Wasserbetriebe', 'Abschlag Wasser/Abwasser H2/2026', false, 'BWB-2026-02'),
    (1, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Straßenreinigung & Müllbeseitigung' LIMIT 1), '2026-04-05', '2026-01-01', '2026-06-30', 495.60, 'BSR Berlin', 'Restmüll & Biotonne H1/2026', false, 'BSR-2026-H1'),
    (1, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Heizung & Warmwasser (Brennstoff/Wartung)' LIMIT 1), '2026-06-18', '2026-01-01', '2026-12-31', 2650.00, 'GASAG Energie', 'Heizgaslieferung & Brennerwartung', false, 'GAS-2026-01'),
    (1, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Allgemeinstrom / Beleuchtung' LIMIT 1), '2026-07-08', '2026-01-01', '2026-06-30', 184.20, 'Vattenfall', 'Treppenhaus- und Kellerstrom H1/2026', false, 'VAT-2026-01'),
    (1, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Schornsteinfeger' LIMIT 1), '2026-10-12', '2026-01-01', '2026-12-31', 128.90, 'Bezirksschornsteinfeger', 'Abgaswegprüfung & Kehrgebühr 2026', false, 'SF-2026-01'),

    -- Objekt 2 (DHH Gartenweg 4)
    (2, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Grundsteuer' LIMIT 1), '2026-02-15', '2026-01-01', '2026-12-31', 420.00, 'Stadtkasse München', 'Grundsteuer Jahresbescheid 2026', false, 'MUC-GS-2026'),
    (2, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Sach- und Haftpflichtversicherung' LIMIT 1), '2026-01-20', '2026-01-01', '2026-12-31', 690.00, 'HUK-Coburg', 'Wohngebäudeversicherung 2026', false, 'HUK-2026-04');

-- 7f) Nicht umlagefähige Eigentümerkosten
INSERT INTO buchung (objekt_id, wohneinheit_id, mietvertrag_id, kostenart_id, buchungsdatum, betrag, empfaenger_sender, verwendungszweck, ist_sonderzahlung, belegnummer)
VALUES
    (1, 3,    NULL, (SELECT id FROM kostenart WHERE name = 'Instandhaltung & Reparatur' LIMIT 1), '2026-03-14', 1950.00, 'Malerbetrieb Schulz', 'Grundrenovierung WE 03 (Leerstand)', false, 'REP-2026-01'),
    (1, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Instandhaltung & Reparatur' LIMIT 1), '2026-09-05',  640.00, 'Heizungsbau Richter', 'Umwälzpumpe Heizung erneuert', false, 'REP-2026-02'),
    (1, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Verwaltungskosten / Steuerberater' LIMIT 1), '2026-06-30', 420.00, 'Steuerkanzlei Berg', 'Anlage V Erstellung 2025', false, 'STB-2026-01'),
    (1, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Darlehenszinsen' LIMIT 1), '2026-06-01', 980.00, 'DKB Immobilienkredit', 'Darlehenszinsen H1/2026 Objekt 1', false, 'DKB-Z-01'),
    (2, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Darlehenszinsen' LIMIT 1), '2026-06-01', 1120.00, 'Sparkasse München', 'Darlehenszinsen H1/2026 Objekt 2', false, 'SPK-Z-01'),
    (2, NULL, NULL, (SELECT id FROM kostenart WHERE name = 'Instandhaltung & Reparatur' LIMIT 1), '2026-08-22',  385.00, 'Sanitär Meier GmbH', 'Austausch Außenwasserhahn frostsicher', false, 'MUC-REP-01');

COMMIT;
