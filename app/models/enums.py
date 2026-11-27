"""Domänen-Enums für konsistente Status-, Richtungs- und Kautionswerte."""

from enum import StrEnum


class WohneinheitStatus(StrEnum):
    """Nutzungsstatus einer Wohneinheit."""

    VERMIETET = "vermietet"
    LEERSTAND = "leerstand"
    EIGENNUTZUNG = "eigennutzung"
    RENOVIERUNG = "renovierung"


class Buchungsrichtung(StrEnum):
    """Finanzfluss-Richtung einer Kostenart."""

    EINNAHME = "einnahme"
    AUSGABE = "ausgabe"


class Verteilerschluessel(StrEnum):
    """Standard-Umlageschlüssel für den Export an den externen Abrechner."""

    WOHNFLAECHE = "wohnflaeche"
    EINHEITEN = "einheiten"
    PERSONEN = "personen"
    VERBRAUCH = "verbrauch"
    DIREKT = "direkt"
    KEINER = "keiner"


class KautionAnlageform(StrEnum):
    """Gesetzlich zulässige Anlageformen einer Mietkaution (§ 551 BGB)."""

    MIETKAUTIONSKONTO = "mietkautionskonto"
    SPARBUCH_VERPFAENDET = "sparbuch_verpfaendet"
    BANKBUERGSCHAFT = "bankbuergschaft"
    BAR = "bar"


class KautionStatus(StrEnum):
    """Lebenszyklus-Status einer hinterlegten Kaution."""

    OFFEN = "offen"
    TEILWEISE_EINGEGANGEN = "teilweise_eingegangen"
    VOLLSTAENDIG = "vollstaendig"
    TEILWEISE_ZURUECKGEZAHLT = "teilweise_zurueckgezahlt"
    ABGERECHNET = "abgerechnet"


class KautionBewegungTyp(StrEnum):
    """Bewegungsarten auf dem getrennten Kautionskonto."""

    EINZAHLUNG_RATE = "einzahlung_rate"
    ZINSGUTSCHRIFT = "zinsgutschrift"
    EINBEHALT = "einbehalt"
    RUECKZAHLUNG = "rueckzahlung"


class DokumentKategorie(StrEnum):
    """Ablagekategorien für PDF-Dokumente auf dem NAS-Volume."""

    BELEG_RECHNUNG = "beleg_rechnung"
    MIETVERTRAG = "mietvertrag"
    UEBERGABEPROTOKOLL = "uebergabeprotokoll"
    KAUTION = "kaution"
    SONSTIGES = "sonstiges"
