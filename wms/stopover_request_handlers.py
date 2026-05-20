from __future__ import annotations

import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.template.loader import render_to_string

from .emailing import get_admin_emails, get_group_emails, send_or_enqueue_email_safe
from .models import StopoverFeasibilityRequest

LOGGER = logging.getLogger(__name__)
ACCOUNT_REQUEST_VALIDATION_GROUP_DEFAULT = "Account_User_Validation"
TEMPLATE_STOPOVER_FEASIBILITY_REQUEST_ADMIN = "emails/stopover_feasibility_request_admin.txt"
SUBJECT_STOPOVER_FEASIBILITY_REQUEST = "Demande nouvelle escale"

REQUIRED_FIELDS = (
    "requester_type",
    "requested_stopovers",
    "structure_name",
    "legal_form",
    "beneficiary_count",
    "contact_title",
    "contact_last_name",
    "contact_first_name",
    "contact_email",
    "contact_phone",
    "address_line1",
    "city",
    "country",
)


def _clean_text(value) -> str:
    return str(value or "").strip()


def _clean_payload(payload: dict) -> dict:
    cleaned = {}
    for key, value in (payload or {}).items():
        if isinstance(value, str):
            cleaned[key] = value.strip()
        else:
            cleaned[key] = value
    return cleaned


def _validate_required_fields(payload: dict):
    errors = {}
    for field in REQUIRED_FIELDS:
        if not _clean_text(payload.get(field)):
            errors[field] = "Champ obligatoire."
    if errors:
        raise ValidationError(errors)


def _build_internal_recipients() -> list[str]:
    return get_admin_emails() + get_group_emails(
        getattr(
            settings,
            "ACCOUNT_REQUEST_VALIDATION_GROUP_NAME",
            ACCOUNT_REQUEST_VALIDATION_GROUP_DEFAULT,
        ),
        require_staff=True,
    )


def _queue_admin_notification(request: StopoverFeasibilityRequest):
    recipients = _build_internal_recipients()
    if not recipients:
        return
    message = render_to_string(
        TEMPLATE_STOPOVER_FEASIBILITY_REQUEST_ADMIN,
        {"request": request},
    )

    def _send_notification():
        sent = send_or_enqueue_email_safe(
            subject=SUBJECT_STOPOVER_FEASIBILITY_REQUEST,
            message=message,
            recipient=recipients,
        )
        if not sent:
            LOGGER.warning(
                "Stopover feasibility request notification was not sent nor queued for %s",
                request.id,
            )

    transaction.on_commit(_send_notification)


def submit_stopover_feasibility_request(
    payload: dict,
    *,
    source: str = "",
    created_by=None,
) -> StopoverFeasibilityRequest:
    cleaned = _clean_payload(payload)
    _validate_required_fields(cleaned)
    request = StopoverFeasibilityRequest(
        requester_type=cleaned.get("requester_type"),
        requested_stopovers=cleaned.get("requested_stopovers", ""),
        structure_name=cleaned.get("structure_name", ""),
        legal_form=cleaned.get("legal_form", ""),
        beneficiary_count=cleaned.get("beneficiary_count"),
        contact_title=cleaned.get("contact_title", ""),
        contact_last_name=cleaned.get("contact_last_name", ""),
        contact_first_name=cleaned.get("contact_first_name", ""),
        contact_email=cleaned.get("contact_email", ""),
        contact_phone=cleaned.get("contact_phone", ""),
        address_line1=cleaned.get("address_line1", ""),
        address_line2=cleaned.get("address_line2", ""),
        postal_code=cleaned.get("postal_code", ""),
        city=cleaned.get("city", ""),
        country=cleaned.get("country", ""),
        message=cleaned.get("message", ""),
        source=source or cleaned.get("source", ""),
        created_by=created_by,
    )
    request.full_clean()
    request.save()
    _queue_admin_notification(request)
    return request
