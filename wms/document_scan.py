from django.db import models


class DocumentScanStatus(models.TextChoices):
    PENDING = "pending", "Scan en cours"
    CLEAN = "clean", "Sain"
    INFECTED = "infected", "Infecte"
    ERROR = "error", "Erreur scan"


def is_scan_clean(document_obj) -> bool:
    return (
        getattr(document_obj, "scan_status", DocumentScanStatus.CLEAN)
        == DocumentScanStatus.CLEAN
    )
