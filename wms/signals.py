from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.db.models.signals import post_delete, post_save, pre_save
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from contacts.models import Contact

from .emailing import enqueue_email_safe, get_admin_emails, get_group_emails
from .models import (
    AssociationProfile,
    AssociationRecipient,
    Order,
    OrderReviewStatus,
    OrderStatus,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
    WmsChange,
)
from .workflow_observability import (
    log_shipment_status_transition,
    log_shipment_tracking_event,
)

SHIPMENT_STATUS_UPDATE_GROUP_DEFAULT = "Shipment_Status_Update"
SHIPMENT_STATUS_CORRESPONDANT_GROUP_DEFAULT = "Shipment_Status_Update_Correspondant"
ORDER_STATUS_ASSOCIATION_TEMPLATE = "emails/order_status_association_notification.txt"
SHIPMENT_STATUS_PARTY_TEMPLATE = "emails/shipment_status_party_notification.txt"
SHIPMENT_STATUS_CORRESPONDANT_TEMPLATE = (
    "emails/shipment_status_correspondant_notification.txt"
)
SHIPMENT_CONTACT_NOTIFICATION_STATUSES = {
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
}
SHIPMENT_CORRESPONDANT_TRACKING_STATUSES = {
    ShipmentTrackingStatus.BOARDING_OK,
}


def _uniq_emails(values):
    emails = []
    seen = set()
    for raw in values:
        value = (raw or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        emails.append(value)
    return emails


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


def _split_email_values(value: str) -> list[str]:
    normalized = (value or "").replace("\n", ";").replace(",", ";")
    return [item.strip() for item in normalized.split(";") if item.strip()]


def _resolve_delivery_recipients(shipment) -> list[str]:
    shipper_contact_id = getattr(shipment, "shipper_contact_ref_id", None)
    if not shipper_contact_id:
        return []

    recipient_queryset = AssociationRecipient.objects.filter(
        association_contact_id=shipper_contact_id,
        is_active=True,
        notify_deliveries=True,
    )
    destination_id = getattr(shipment, "destination_id", None)
    if destination_id:
        recipient_queryset = recipient_queryset.filter(
            Q(destination_id=destination_id) | Q(destination__isnull=True)
        )
    else:
        recipient_queryset = recipient_queryset.filter(destination__isnull=True)

    resolved_recipients = []
    seen = set()
    for recipient in recipient_queryset.only("emails", "email"):
        candidates = [
            *_split_email_values(recipient.emails),
            (recipient.email or "").strip(),
        ]
        for candidate in candidates:
            normalized = candidate.lower()
            if not candidate or normalized in seen:
                continue
            seen.add(normalized)
            resolved_recipients.append(candidate)
    return resolved_recipients


def _notify_shipment_delivery(instance) -> None:
    recipients = _resolve_delivery_recipients(instance)
    if not recipients:
        return
    message = render_to_string(
        "emails/shipment_delivery_notification.txt",
        {
            "shipment_reference": instance.reference,
            "destination_label": str(instance.destination)
            if instance.destination
            else instance.destination_address,
            "delivered_at": timezone.localtime(timezone.now()),
            "tracking_url": instance.get_tracking_url(),
        },
    )
    transaction.on_commit(
        lambda: enqueue_email_safe(
            subject=f"ASF WMS - Expedition {instance.reference} : livraison confirmee",
            message=message,
            recipient=recipients,
        )
    )


def _shipment_status_admin_recipients():
    group_name = getattr(
        settings,
        "SHIPMENT_STATUS_UPDATE_GROUP_NAME",
        SHIPMENT_STATUS_UPDATE_GROUP_DEFAULT,
    )
    return _uniq_emails(
        get_admin_emails() + get_group_emails(group_name, require_staff=True)
    )


def _shipment_party_recipients(shipment):
    return _uniq_emails(
        [
            getattr(getattr(shipment, "shipper_contact_ref", None), "email", ""),
            getattr(getattr(shipment, "recipient_contact_ref", None), "email", ""),
        ]
    )


def _shipment_correspondant_recipients(shipment):
    group_name = getattr(
        settings,
        "SHIPMENT_STATUS_CORRESPONDANT_GROUP_NAME",
        SHIPMENT_STATUS_CORRESPONDANT_GROUP_DEFAULT,
    )
    group_recipients = get_group_emails(group_name, require_staff=True)
    correspondent_email = getattr(
        getattr(shipment, "correspondent_contact_ref", None), "email", ""
    )
    return _uniq_emails(group_recipients + [correspondent_email])


def _queue_shipment_party_notification(*, shipment, old_label, new_label):
    recipients = _shipment_party_recipients(shipment)
    if not recipients:
        return
    message = render_to_string(
        SHIPMENT_STATUS_PARTY_TEMPLATE,
        {
            "shipment_reference": shipment.reference,
            "old_status": old_label,
            "new_status": new_label,
            "destination_label": str(shipment.destination)
            if shipment.destination
            else shipment.destination_address,
            "changed_at": timezone.localtime(timezone.now()),
            "tracking_url": shipment.get_tracking_url(),
        },
    )
    transaction.on_commit(
        lambda: enqueue_email_safe(
            subject=f"ASF WMS - Expédition {shipment.reference} : statut {new_label}",
            message=message,
            recipient=recipients,
        )
    )


def _queue_shipment_correspondant_notification(
    *,
    shipment,
    old_label,
    new_label,
    tracking_status_label="",
):
    recipients = _shipment_correspondant_recipients(shipment)
    if not recipients:
        return
    message = render_to_string(
        SHIPMENT_STATUS_CORRESPONDANT_TEMPLATE,
        {
            "shipment_reference": shipment.reference,
            "old_status": old_label,
            "new_status": new_label,
            "tracking_status_label": tracking_status_label or "-",
            "destination_label": str(shipment.destination)
            if shipment.destination
            else shipment.destination_address,
            "tracking_url": shipment.get_tracking_url(),
        },
    )
    transaction.on_commit(
        lambda: enqueue_email_safe(
            subject=(
                f"ASF WMS - Suivi correspondant {shipment.reference} : {new_label}"
            ),
            message=message,
            recipient=recipients,
        )
    )


def _notify_shipment_status_change(sender, instance, created, **kwargs) -> None:
    if created:
        return
    previous_status = getattr(instance, "_previous_status", None)
    if not previous_status or previous_status == instance.status:
        return
    log_shipment_status_transition(
        shipment=instance,
        previous_status=previous_status,
        new_status=instance.status,
        source="shipment_post_save_signal",
    )
    admin_recipients = _shipment_status_admin_recipients()
    if admin_recipients:
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
                recipient=admin_recipients,
            )
        )
    else:
        try:
            old_label = ShipmentStatus(previous_status).label
        except ValueError:
            old_label = previous_status
        try:
            new_label = ShipmentStatus(instance.status).label
        except ValueError:
            new_label = instance.status
    if instance.status in SHIPMENT_CONTACT_NOTIFICATION_STATUSES:
        _queue_shipment_party_notification(
            shipment=instance,
            old_label=old_label,
            new_label=new_label,
        )
    if instance.status == ShipmentStatus.PLANNED:
        _queue_shipment_correspondant_notification(
            shipment=instance,
            old_label=old_label,
            new_label=new_label,
            tracking_status_label=ShipmentTrackingStatus.PLANNED.label,
        )
    if instance.status == ShipmentStatus.DELIVERED:
        _notify_shipment_delivery(instance)


def _notify_tracking_event(sender, instance, created, **kwargs) -> None:
    if not created:
        return
    log_shipment_tracking_event(
        tracking_event=instance,
        user=getattr(instance, "created_by", None),
    )
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
    tracking_status = getattr(instance, "status", "")
    if tracking_status in SHIPMENT_CORRESPONDANT_TRACKING_STATUSES:
        tracking_status_label = tracking_status
        if hasattr(instance, "get_status_display"):
            tracking_status_label = instance.get_status_display()
        _queue_shipment_correspondant_notification(
            shipment=shipment,
            old_label="-",
            new_label=tracking_status_label,
            tracking_status_label=tracking_status_label,
        )


def _capture_order_state(sender, instance, **kwargs) -> None:
    if not instance.pk:
        instance._previous_order_status = None
        instance._previous_order_review_status = None
        return
    previous_values = sender.objects.filter(pk=instance.pk).values(
        "status",
        "review_status",
    ).first()
    if not previous_values:
        instance._previous_order_status = None
        instance._previous_order_review_status = None
        return
    instance._previous_order_status = previous_values.get("status")
    instance._previous_order_review_status = previous_values.get("review_status")


def _resolve_order_association_recipients(order):
    recipients = []
    association_contact = getattr(order, "association_contact", None)
    if association_contact is not None:
        recipients.append(association_contact.email)
        profile = (
            AssociationProfile.objects.select_related("user")
            .filter(contact_id=association_contact.id)
            .first()
        )
        if profile is not None:
            recipients.append(profile.user.email)
            recipients.extend(profile.get_notification_emails())
    recipients.append(getattr(getattr(order, "shipper_contact", None), "email", ""))
    recipients.append(getattr(getattr(order, "recipient_contact", None), "email", ""))
    return _uniq_emails(recipients)


def _order_review_status_label(order_status):
    try:
        return dict(OrderReviewStatus.choices).get(order_status) or order_status
    except Exception:  # pragma: no cover - defensive
        return order_status


def _order_state_status_label(order_status):
    try:
        return dict(OrderStatus.choices).get(order_status) or order_status
    except Exception:  # pragma: no cover - defensive
        return order_status


def _notify_order_status_change(sender, instance, created, **kwargs) -> None:
    if created:
        return

    previous_status = getattr(instance, "_previous_order_status", None)
    previous_review_status = getattr(instance, "_previous_order_review_status", None)
    status_changed = previous_status and previous_status != instance.status
    review_changed = previous_review_status and previous_review_status != instance.review_status
    if not status_changed and not review_changed:
        return

    recipients = _uniq_emails(get_admin_emails() + _resolve_order_association_recipients(instance))
    if not recipients:
        return

    admin_url = _build_site_url(
        reverse("admin:wms_order_change", args=[instance.id])
    )
    message = render_to_string(
        ORDER_STATUS_ASSOCIATION_TEMPLATE,
        {
            "order_reference": instance.reference or f"Commande {instance.id}",
            "old_status": _order_state_status_label(previous_status) or "-",
            "new_status": _order_state_status_label(instance.status),
            "old_review_status": _order_review_status_label(previous_review_status) or "-",
            "new_review_status": _order_review_status_label(instance.review_status),
            "admin_url": admin_url,
        },
    )
    transaction.on_commit(
        lambda: enqueue_email_safe(
            subject=(
                f"ASF WMS - Commande {instance.reference or instance.id} : "
                "validation/statut mis à jour"
            ),
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
    pre_save.connect(
        _capture_order_state,
        sender=Order,
        dispatch_uid="wms_order_state_pre_save",
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
        _notify_order_status_change,
        sender=Order,
        dispatch_uid="wms_order_status_post_save",
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
