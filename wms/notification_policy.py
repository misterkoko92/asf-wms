from __future__ import annotations

from .models import (
    ContactSubscription,
    NotificationChannel,
    OrganizationRoleAssignment,
    OrganizationRoleContact,
    RoleEventPolicy,
)


def _uniq_emails(values):
    emails = []
    seen = set()
    for raw in values:
        value = (raw or "").strip()
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        emails.append(value)
    return emails


def resolve_notification_recipients(
    *,
    role_assignment: OrganizationRoleAssignment,
    event_type: str,
    destination=None,
    shipper_org=None,
    recipient_org=None,
) -> list[str]:
    policy_exists = RoleEventPolicy.objects.filter(
        role=role_assignment.role,
        event_type=event_type,
        is_active=True,
        is_notifiable=True,
    ).exists()
    if not policy_exists:
        return []

    subscriptions = ContactSubscription.objects.filter(
        role_contact__role_assignment=role_assignment,
        role_contact__is_active=True,
        role_contact__contact__is_active=True,
        event_type=event_type,
        channel=NotificationChannel.EMAIL,
        is_active=True,
    ).select_related("role_contact__contact", "destination", "shipper_org", "recipient_org")

    subscribed_emails = []
    for subscription in subscriptions:
        if not subscription.matches_context(
            destination=destination,
            shipper_org=shipper_org,
            recipient_org=recipient_org,
        ):
            continue
        subscribed_emails.append(subscription.role_contact.contact.email)

    deduped_subscription_emails = _uniq_emails(subscribed_emails)
    if deduped_subscription_emails:
        return deduped_subscription_emails

    primary_contact = (
        OrganizationRoleContact.objects.filter(
            role_assignment=role_assignment,
            is_primary=True,
            is_active=True,
            contact__is_active=True,
        )
        .select_related("contact")
        .first()
    )
    if not primary_contact:
        return []
    return _uniq_emails([primary_contact.contact.email])
