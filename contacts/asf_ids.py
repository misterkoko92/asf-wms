from django.db.models import Q

from wms.config import get_installation_config


def resolve_contact_identifier_generated_prefix() -> str:
    prefix = get_installation_config().references.contact_identifier_generated_prefix
    if not isinstance(prefix, str) or not prefix:
        raise ValueError("Contact identifier generated prefix must not be empty.")
    if any(char.isspace() for char in prefix):
        raise ValueError("Contact identifier generated prefix must not contain whitespace.")
    if prefix.startswith("-") or prefix.endswith("-"):
        raise ValueError("Contact identifier generated prefix must not start or end with '-'.")
    return prefix


def build_generated_asf_id(contact_pk: int | None) -> str:
    if not contact_pk:
        raise ValueError("Contact primary key is required.")
    prefix = resolve_contact_identifier_generated_prefix()
    return f"{prefix}-{contact_pk:08d}"


def ensure_contact_asf_id(contact) -> str:
    if contact.pk is None:
        raise ValueError("Contact primary key is required.")
    if (contact.asf_id or "").strip():
        return contact.asf_id

    generated_asf_id = build_generated_asf_id(contact.pk)
    contact.__class__.objects.filter(pk=contact.pk).filter(
        Q(asf_id__isnull=True) | Q(asf_id="")
    ).update(asf_id=generated_asf_id)
    contact.asf_id = generated_asf_id
    return generated_asf_id


def backfill_missing_contact_asf_ids(*, dry_run: bool) -> dict[str, int]:
    from .models import Contact

    contacts = Contact.objects.order_by("pk")
    missing_contacts = contacts.filter(Q(asf_id__isnull=True) | Q(asf_id=""))

    summary = {
        "scanned_contacts": contacts.count(),
        "missing_contacts": missing_contacts.count(),
        "backfilled_contacts": 0,
    }
    if dry_run:
        summary["backfilled_contacts"] = summary["missing_contacts"]
        return summary

    for contact in missing_contacts.iterator():
        ensure_contact_asf_id(contact)
        summary["backfilled_contacts"] += 1
    return summary
