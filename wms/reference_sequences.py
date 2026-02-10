import re
import unicodedata

from django.db import IntegrityError, connection, transaction
from django.db.models.functions import Length
from django.utils import timezone

RECEIPT_REFERENCE_RE = re.compile(
    r"^(?P<year>\d{2})-(?P<seq>\d{2,})-(?P<donor>[A-Z0-9]{3})-(?P<count>\d{2,})$"
)


def normalize_reference_fragment(value: str, length: int) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(ch for ch in ascii_value if ch.isalnum())
    cleaned = cleaned.upper()
    if not cleaned:
        cleaned = "X" * length
    if len(cleaned) < length:
        cleaned = cleaned.ljust(length, "X")
    return cleaned[:length]


def generate_receipt_reference(
    *,
    received_on=None,
    source_contact=None,
    receipt_model,
    receipt_sequence_model,
    receipt_donor_sequence_model,
    transaction_module=transaction,
    connection_obj=connection,
    integrity_error=IntegrityError,
    receipt_reference_re=RECEIPT_REFERENCE_RE,
    localdate_fn=timezone.localdate,
) -> str:
    received_on = received_on or localdate_fn()
    year = received_on.year
    year_prefix = f"{year % 100:02d}"
    donor_code = normalize_reference_fragment(
        source_contact.name if source_contact else "",
        3,
    )
    with transaction_module.atomic():
        try:
            sequence_query = receipt_sequence_model.objects.filter(year=year)
            if connection_obj.features.has_select_for_update:
                sequence_query = sequence_query.select_for_update()
            sequence = sequence_query.get()
        except receipt_sequence_model.DoesNotExist:
            last_number = 0
            references = receipt_model.objects.filter(
                reference__startswith=f"{year_prefix}-"
            ).values_list("reference", flat=True)
            for reference in references:
                match = receipt_reference_re.match(reference or "")
                if not match:
                    continue
                try:
                    number = int(match.group("seq"))
                except (TypeError, ValueError):
                    continue
                if number > last_number:
                    last_number = number
            if last_number == 0:
                last_number = receipt_model.objects.filter(received_on__year=year).count()
            try:
                sequence = receipt_sequence_model.objects.create(
                    year=year,
                    last_number=last_number,
                )
            except integrity_error:
                sequence_query = receipt_sequence_model.objects.filter(year=year)
                if connection_obj.features.has_select_for_update:
                    sequence_query = sequence_query.select_for_update()
                sequence = sequence_query.get()
        sequence.last_number += 1
        sequence.save(update_fields=["last_number"])

        donor_number = 0
        if source_contact:
            try:
                donor_query = receipt_donor_sequence_model.objects.filter(
                    year=year,
                    donor=source_contact,
                )
                if connection_obj.features.has_select_for_update:
                    donor_query = donor_query.select_for_update()
                donor_sequence = donor_query.get()
            except receipt_donor_sequence_model.DoesNotExist:
                donor_last_number = 0
                donor_refs = receipt_model.objects.filter(
                    source_contact=source_contact,
                    received_on__year=year,
                ).values_list("reference", flat=True)
                for reference in donor_refs:
                    match = receipt_reference_re.match(reference or "")
                    if not match:
                        continue
                    try:
                        number = int(match.group("count"))
                    except (TypeError, ValueError):
                        continue
                    if number > donor_last_number:
                        donor_last_number = number
                if donor_last_number == 0:
                    donor_last_number = receipt_model.objects.filter(
                        source_contact=source_contact,
                        received_on__year=year,
                    ).count()
                try:
                    donor_sequence = receipt_donor_sequence_model.objects.create(
                        year=year,
                        donor=source_contact,
                        last_number=donor_last_number,
                    )
                except integrity_error:
                    donor_query = receipt_donor_sequence_model.objects.filter(
                        year=year,
                        donor=source_contact,
                    )
                    if connection_obj.features.has_select_for_update:
                        donor_query = donor_query.select_for_update()
                    donor_sequence = donor_query.get()
            donor_sequence.last_number += 1
            donor_sequence.save(update_fields=["last_number"])
            donor_number = donor_sequence.last_number

    return f"{year_prefix}-{sequence.last_number:02d}-{donor_code}-{donor_number:02d}"


def generate_shipment_reference(
    *,
    shipment_model,
    shipment_sequence_model,
    transaction_module=transaction,
    connection_obj=connection,
    integrity_error=IntegrityError,
    length_cls=Length,
    localdate_fn=timezone.localdate,
) -> str:
    year = localdate_fn().year
    year_prefix = f"{year % 100:02d}"
    with transaction_module.atomic():
        try:
            sequence_query = shipment_sequence_model.objects.filter(year=year)
            if connection_obj.features.has_select_for_update:
                sequence_query = sequence_query.select_for_update()
            sequence = sequence_query.get()
        except shipment_sequence_model.DoesNotExist:
            last_ref = (
                shipment_model.objects.annotate(ref_len=length_cls("reference"))
                .filter(reference__startswith=year_prefix, ref_len=6)
                .order_by("-reference")
                .values_list("reference", flat=True)
                .first()
            )
            last_number = 0
            if last_ref and last_ref.isdigit():
                last_number = int(last_ref[2:])
            try:
                sequence = shipment_sequence_model.objects.create(
                    year=year,
                    last_number=last_number,
                )
            except integrity_error:
                sequence_query = shipment_sequence_model.objects.filter(year=year)
                if connection_obj.features.has_select_for_update:
                    sequence_query = sequence_query.select_for_update()
                sequence = sequence_query.get()
        sequence.last_number += 1
        sequence.save(update_fields=["last_number"])
        return f"{year_prefix}{sequence.last_number:04d}"
