from __future__ import annotations

from django.utils import timezone

from .emailing import get_admin_emails
from .models import (
    ComplianceOverride,
    DocumentRequirementTemplate,
    DocumentReviewStatus,
    OrganizationRoleContact,
    OrganizationRoleDocument,
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


def is_role_compliant(role_assignment, *, now=None) -> bool:
    required_templates_qs = DocumentRequirementTemplate.objects.filter(
        role=role_assignment.role,
        is_required=True,
        is_active=True,
    )
    required_template_ids = set(
        required_templates_qs.values_list("id", flat=True)
    )
    if not required_template_ids:
        return True

    approved_template_ids = set(
        OrganizationRoleDocument.objects.filter(
            role_assignment=role_assignment,
            requirement_template_id__in=required_template_ids,
            is_active=True,
            status=DocumentReviewStatus.APPROVED,
        ).values_list("requirement_template_id", flat=True)
    )
    return required_template_ids.issubset(approved_template_ids)


def can_bypass_with_override(role_assignment, *, now=None) -> bool:
    reference = now or timezone.now()
    return ComplianceOverride.objects.filter(
        role_assignment=role_assignment,
        is_active=True,
        expires_at__gt=reference,
    ).exists()


def is_role_operation_allowed(role_assignment, *, now=None) -> bool:
    reference = now or timezone.now()
    return is_role_compliant(role_assignment, now=reference) or can_bypass_with_override(
        role_assignment,
        now=reference,
    )


def _primary_role_contact_email(role_assignment) -> str:
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
        return ""
    return (primary_contact.contact.email or "").strip()


def list_compliance_override_reminders(*, now=None, day_offsets=(3, 1)):
    reference = now or timezone.now()
    target_days = {int(day) for day in day_offsets}
    base_recipients = get_admin_emails()

    overrides = ComplianceOverride.objects.filter(
        is_active=True,
        expires_at__gt=reference,
    ).select_related("role_assignment", "role_assignment__organization")

    reminders = []
    reference_date = timezone.localdate(reference)
    for override in overrides:
        days_left = (timezone.localdate(override.expires_at) - reference_date).days
        if days_left not in target_days:
            continue
        recipients = _uniq_emails(
            base_recipients + [_primary_role_contact_email(override.role_assignment)]
        )
        reminders.append(
            {
                "override": override,
                "days_left": days_left,
                "recipients": recipients,
            }
        )

    reminders.sort(
        key=lambda item: (
            item["days_left"],
            item["override"].expires_at,
            item["override"].id,
        )
    )
    return reminders
