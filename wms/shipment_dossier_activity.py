from django.utils import timezone


def record_shipment_dossier_activity(*, shipment, label, occurred_at=None):
    shipment.dossier_last_activity_at = occurred_at or timezone.now()
    shipment.dossier_last_activity_label = (label or "").strip()
    shipment.save(
        update_fields=[
            "dossier_last_activity_at",
            "dossier_last_activity_label",
        ]
    )
    return shipment
