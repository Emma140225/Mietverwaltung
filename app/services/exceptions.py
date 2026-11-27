"""Domänen-spezifische Ausnahmen für die Service-Schicht."""


class DomainError(Exception):
    """Basisklasse für fachliche Fehler in Services."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(DomainError):
    """Angeforderte Ressource existiert nicht."""


class ValidationError(DomainError):
    """Fachliche Eingabe- oder Konsistenzprüfung fehlgeschlagen."""


class ConflictError(DomainError):
    """Fachlicher Konflikt (z. B. Zeitraumüberschneidung oder Eindeutigkeitsverletzung)."""


class OptimisticLockError(ConflictError):
    """Versionskonflikt bei gleichzeitiger Bearbeitung durch zwei Clients."""


class StorageError(DomainError):
    """Fehler beim Lesen, Schreiben oder Prüfen einer PDF-Datei im NAS-Volume."""
