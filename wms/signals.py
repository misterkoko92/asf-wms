from django.apps import apps
from django.conf import settings
from django.db.models.signals import post_delete, post_save, pre_save
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .emailing import get_admin_emails, send_email_safe
from .models import Shipment, ShipmentStatus, ShipmentTrackingEvent, WmsChange


def _bump_change(**kwargs) -> None:
    WmsChange.bump()


def _build_site_url(path: str) -> str:
    base = getattr(settings, "SITE_BASE_URL", "").strip()
    if not base:
        return path
    if not base.startswith(("http://", "https://")):
        base = f"https://{base}"
    return f"{base.rstrip('/')}{path}"


def _capture_shipment_status(sender, instance, **kwargs) -> None:
    if not instance.pk:
        instance._previous_status = None
        return
    instance._previous_status = (
        sender.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    )


def _notify_shipment_status_change(sender, instance, created, **kwargs) -> None:
    if created:
        return
    previous_status = getattr(instance, "_previous_status", None)
    if not previous_status or previous_status == instance.status:
        return
    recipients = get_admin_emails()
    if not recipients:
        return
    try:
        old_label = ShipmentStatus(previous_status).label
    except ValueError:
        old_label = previous_status
    try:
        new_label = ShipmentStatus(instance.status).label
    except ValueError:
        new_label = instance.status
    admin_url = _build_site_url(
        reverse("admin:wms_shipment_change", args=[instance.id])
    )
    message = render_to_string(
        "emails/shipment_status_admin_notification.txt",
        {
            "shipment_reference": instance.reference,
            "old_status": old_label,
            "new_status": new_label,
            "destination_label": str(instance.destination)
            if instance.destination
            else instance.destination_address,
            "changed_at": timezone.localtime(timezone.now()),
            "tracking_url": instance.get_tracking_url(),
            "admin_url": admin_url,
        },
    )
    send_email_safe(
        subject=f"ASF WMS - Expedition {instance.reference} : statut mis a jour",
        message=message,
        recipient=recipients,
    )


def _notify_tracking_event(sender, instance, created, **kwargs) -> None:
    if not created:
        return
    recipients = get_admin_emails()
    if not recipients:
        return
    shipment = instance.shipment
    admin_url = _build_site_url(
        reverse("admin:wms_shipment_change", args=[shipment.id])
    )
    message = render_to_string(
        "emails/shipment_tracking_admin_notification.txt",
        {
            "shipment_reference": shipment.reference,
            "status": instance.get_status_display(),
            "actor_name": instance.actor_name,
            "actor_structure": instance.actor_structure,
            "comments": instance.comments or "-",
            "event_time": timezone.localtime(instance.created_at),
            "tracking_url": shipment.get_tracking_url(),
            "admin_url": admin_url,
        },
    )
    send_email_safe(
        subject=f"ASF WMS - Suivi expedition {shipment.reference}",
        message=message,
        recipient=recipients,
    )


def register_change_signals() -> None:
    for app_label in ("wms", "contacts"):
        app_config = apps.get_app_config(app_label)
        for model in app_config.get_models():
            if model is WmsChange:
                continue
            post_save.connect(
                _bump_change,
                sender=model,
                dispatch_uid=f"wms_change_save_{app_label}_{model.__name__}",
            )
            post_delete.connect(
                _bump_change,
                sender=model,
                dispatch_uid=f"wms_change_delete_{app_label}_{model.__name__}",
            )
    pre_save.connect(
        _capture_shipment_status,
        sender=Shipment,
        dispatch_uid="wms_shipment_status_pre_save",
    )
    post_save.connect(
        _notify_shipment_status_change,
        sender=Shipment,
        dispatch_uid="wms_shipment_status_post_save",
    )
    post_save.connect(
        _notify_tracking_event,
        sender=ShipmentTrackingEvent,
        dispatch_uid="wms_shipment_tracking_post_save",
    )
