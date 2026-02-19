from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from contacts.models import Contact

from .emailing import enqueue_email_safe, get_admin_emails
from .models import AssociationProfile, Shipment, ShipmentStatus, ShipmentTrackingEvent, WmsChange


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
    transaction.on_commit(
        lambda: enqueue_email_safe(
            subject=f"ASF WMS - Expédition {instance.reference} : statut mis à jour",
            message=message,
            recipient=recipients,
        )
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
    transaction.on_commit(
        lambda: enqueue_email_safe(
            subject=f"ASF WMS - Suivi expédition {shipment.reference}",
            message=message,
            recipient=recipients,
        )
    )


def _ensure_association_portal_group(sender, instance, **kwargs) -> None:
    user = getattr(instance, "user", None)
    if not user or not getattr(user, "pk", None):
        return
    from .portal_permissions import assign_association_portal_group

    assign_association_portal_group(user)


def _sync_profile_emails_on_create(sender, instance, created, **kwargs) -> None:
    if not created:
        return
    user = getattr(instance, "user", None)
    contact = getattr(instance, "contact", None)
    if not user or not contact:
        return
    user_email = (user.email or "").strip()
    contact_email = (contact.email or "").strip()
    # Preserve user login identity when already set; otherwise backfill user email
    # from the association contact.
    if user_email and contact_email != user_email:
        Contact.objects.filter(pk=contact.pk).update(email=user_email)
        return
    if not user_email and contact_email:
        get_user_model().objects.filter(pk=user.pk).update(email=contact_email)


def _sync_profile_user_email_from_contact(sender, instance, **kwargs) -> None:
    profiles = AssociationProfile.objects.select_related("user").filter(contact=instance)
    if not profiles.exists():
        return
    target_email = (instance.email or "").strip()
    user_ids_to_update = [
        profile.user_id
        for profile in profiles
        if (profile.user.email or "").strip() != target_email
    ]
    if user_ids_to_update:
        get_user_model().objects.filter(pk__in=user_ids_to_update).update(email=target_email)


def _sync_profile_contact_email_from_user(sender, instance, **kwargs) -> None:
    profile = (
        AssociationProfile.objects.select_related("contact")
        .filter(user=instance)
        .first()
    )
    if not profile:
        return
    target_email = (instance.email or "").strip()
    if (profile.contact.email or "").strip() == target_email:
        return
    Contact.objects.filter(pk=profile.contact_id).update(email=target_email)


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
    post_save.connect(
        _ensure_association_portal_group,
        sender=AssociationProfile,
        dispatch_uid="wms_association_profile_group_post_save",
    )
    post_save.connect(
        _sync_profile_emails_on_create,
        sender=AssociationProfile,
        dispatch_uid="wms_association_profile_sync_emails_post_save",
    )
    post_save.connect(
        _sync_profile_user_email_from_contact,
        sender=Contact,
        dispatch_uid="wms_association_profile_sync_user_email_from_contact_post_save",
    )
    post_save.connect(
        _sync_profile_contact_email_from_user,
        sender=get_user_model(),
        dispatch_uid="wms_association_profile_sync_contact_email_from_user_post_save",
    )
