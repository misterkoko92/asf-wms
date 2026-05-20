import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import EmailValidator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from contacts.models import Contact, RecipientLegalForm

from .account_request_handlers import handle_account_request_form
from .application.parties.use_cases import (
    save_recipient_product_preference,
    update_recipient_shared_profile,
    update_runtime_recipient_profile,
    upsert_recipient_structure_documents,
)
from .application.portal.account_use_cases import save_portal_account_profile
from .application.portal.dashboard_queries import (
    build_recipient_scope_home_payload,
    build_runtime_recipient_profile_payload,
)
from .country_choices import DEFAULT_COUNTRY, build_country_choices, is_known_country
from .document_scan import DocumentScanStatus
from .document_scan_queue import queue_document_scan
from .document_uploads import validate_document_upload
from .emailing import get_admin_emails, get_group_emails, send_or_enqueue_email_safe
from .models import (
    AccountDocument,
    AccountDocumentType,
    AssociationBillingChangeRequest,
    AssociationBillingFrequency,
    AssociationBillingGroupingMode,
    AssociationContactTitle,
    AssociationPortalContact,
    AssociationRecipient,
    Destination,
    DocumentReviewStatus,
    PortalAccessGrant,
    PortalAccessRole,
    Product,
    ProductCategory,
    RecipientProductPreference,
    RecipientProductPreferencePeriodUnit,
    RecipientProductPreferenceSource,
    RecipientProductPreferenceStatus,
    RecipientStructureDocumentType,
    ShipmentRecipientOrganization,
    ShipmentValidationStatus,
)
from .portal_helpers import build_public_base_url, get_contact_address
from .recipient_preference_view_helpers import (
    build_recipient_preference_catalog_context,
    build_recipient_preference_filter_url,
    get_recipient_preference_filter_state,
)
from .recipient_product_preferences import (
    UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS,
    list_effective_recipient_product_preferences,
)
from .scan_helpers import parse_int
from .upload_utils import validate_upload
from .view_permissions import (
    BLOCKED_MESSAGES,
    BLOCKED_REASON_MISSING_DELIVERY_CONTACT,
    BLOCKED_REASON_QUERY_PARAM,
    association_required,
    portal_scope_required,
)
from .view_utils import sorted_choices

LOGGER = logging.getLogger(__name__)

TEMPLATE_RECIPIENTS = "portal/recipients.html"
TEMPLATE_RECIPIENT_DETAIL = "portal/recipient_detail.html"
TEMPLATE_RECIPIENT_PREFERENCES = "portal/recipient_preferences.html"
TEMPLATE_RECIPIENT_PROFILE = "portal/recipient_profile.html"
TEMPLATE_ACCOUNT = "portal/account.html"
TEMPLATE_RECIPIENT_VALIDATION_ADMIN_NOTIFICATION = (
    "emails/recipient_validation_admin_notification.txt"
)

ACCOUNT_REQUEST_VALIDATION_GROUP_DEFAULT = "Account_User_Validation"

ACTION_CREATE_RECIPIENT = "create_recipient"
ACTION_UPDATE_RECIPIENT = "update_recipient"
ACTION_UPDATE_RECIPIENT_PROFILE = "update_recipient_profile"
ACTION_SAVE_PRODUCT_PREFERENCE = "save_product_preference"
ACTION_DELETE_PRODUCT_PREFERENCE = "delete_product_preference"
ACTION_SAVE_RECIPIENT_PREFERENCE = "save_recipient_preference"
ACTION_SAVE_RECIPIENT_PREFERENCES_BULK = "save_recipient_preferences_bulk"
ACTION_CREATE_RECIPIENT_PREFERENCE = "create_recipient_preference"
ACTION_UPDATE_RECIPIENT_PREFERENCE = "update_recipient_preference"
ACTION_DELETE_RECIPIENT_PREFERENCE = "delete_recipient_preference"
ACTION_UPDATE_NOTIFICATIONS = "update_notifications"
ACTION_UPDATE_PROFILE = "update_profile"
ACTION_UPLOAD_ACCOUNT_DOC = "upload_account_doc"
ACTION_UPLOAD_ACCOUNT_DOCS = "upload_account_docs"
ACTION_REQUEST_BILLING_PREFERENCES = "request_billing_preferences"

MAX_PORTAL_CONTACTS = 10
MESSAGE_RECIPIENT_ADDED = _("Destinataire ajouté.")
MESSAGE_RECIPIENT_UPDATED = _("Destinataire modifié.")
MESSAGE_RECIPIENT_PRODUCT_PREFERENCE_SAVED = _("Préférence produit enregistrée.")
MESSAGE_RECIPIENT_PRODUCT_PREFERENCE_DELETED = _("Préférence produit supprimée.")
MESSAGE_RECIPIENT_PREFERENCE_ADDED = _("Préférence produit ajoutée.")
MESSAGE_RECIPIENT_PREFERENCE_UPDATED = _("Préférence produit modifiée.")
MESSAGE_RECIPIENT_PREFERENCE_DELETED = _("Préférence produit supprimée.")
MESSAGE_RECIPIENT_PREFERENCES_BULK_UPDATED = _("Préférences produits mises à jour.")
MESSAGE_RECIPIENT_PREFERENCES_BULK_NO_CHANGES = _("Aucune modification à enregistrer.")
MESSAGE_PROFILE_UPDATED = _("Compte mis à jour.")
MESSAGE_CONTACTS_UPDATED = _("Contacts emails mis à jour.")
MESSAGE_UPDATE_NOTIFICATIONS_DEPRECATED = _(
    "Action obsolète: mettez à jour les contacts emails depuis le formulaire principal."
)
MESSAGE_DOCUMENT_ADDED = _("Document ajouté.")
MESSAGE_DOCUMENTS_ADDED = _("Documents ajoutés.")
MESSAGE_BILLING_PREFERENCES_REQUESTED = _("Demande de préférences de facturation envoyée.")
SUBJECT_RECIPIENT_VALIDATION_PENDING = _("ASF WMS - Nouveau destinataire en attente de validation")
ERROR_NO_DOCUMENT_SELECTED = _("Aucun fichier sélectionné.")
ERROR_RECIPIENT_DESTINATION_REQUIRED = _("Escale de livraison requise.")
ERROR_RECIPIENT_STRUCTURE_REQUIRED = _("Nom de la structure requis.")
ERROR_RECIPIENT_ADDRESS_REQUIRED = _("Adresse requise.")
ERROR_RECIPIENT_TITLE_INVALID = _("Titre de contact invalide.")
ERROR_RECIPIENT_LEGAL_FORM_REQUIRED = _("Forme juridique requise.")
ERROR_RECIPIENT_LEGAL_FORM_INVALID = _("Forme juridique invalide.")
ERROR_RECIPIENT_BENEFICIARY_COUNT_REQUIRED = _("Nombre de bénéficiaires requis.")
ERROR_RECIPIENT_BENEFICIARY_COUNT_INVALID = _("Nombre de bénéficiaires invalide.")
ERROR_RECIPIENT_COUNTRY_INVALID = _("Pays invalide.")
ERROR_RECIPIENT_REGISTRATION_PROOF_REQUIRED = _("Preuve d'enregistrement requise.")
ERROR_RECIPIENT_STATUTES_REQUIRED = _("Statut requis.")
ERROR_RECIPIENT_EMAILS_INVALID = _("Adresses e-mail invalides: %(values)s.")
ERROR_RECIPIENT_NOTIFY_EMAIL_REQUIRED = _(
    "Ajoutez au moins un email pour activer l'alerte de livraison."
)
ERROR_RECIPIENT_NOT_FOUND = _("Destinataire introuvable.")
ERROR_RECIPIENT_PREFERENCE_NOT_FOUND = _("Préférence produit introuvable.")
ERROR_RECIPIENT_PREFERENCE_SCOPE_INVALID = _("Choisissez un produit ou une catégorie valide.")
ERROR_RECIPIENT_PREFERENCE_RECIPIENT_REQUIRED = _(
    "Enregistrez d'abord le destinataire avant de saisir ses préférences produits."
)
ERROR_RECIPIENT_PRODUCT_REQUIRED = _("Produit requis.")
ERROR_RECIPIENT_PRODUCT_QUANTITY_INVALID = _("Quantité cible invalide.")
ERROR_RECIPIENT_PRODUCT_STATUS_INVALID = _("Statut produit invalide.")
ERROR_RECIPIENT_PRODUCT_PERIOD_INVALID = _("Période invalide.")
ERROR_RECIPIENT_PREFERENCE_NOT_FOUND = _("Préférence produit introuvable.")
ERROR_RECIPIENT_RUNTIME_REQUIRED = _("La structure destinataire operationnelle est introuvable.")
ERROR_RECIPIENT_SHARED_READ_ONLY = _(
    "Cette fiche destinataire est en lecture seule dans le portail expéditeur car un accès destinataire est actif."
)
ERROR_ASSOCIATION_NAME_REQUIRED = _("Nom de l'association requis.")
ERROR_ASSOCIATION_ADDRESS_REQUIRED = _("Adresse requise.")
ERROR_CONTACT_ROWS_LIMIT = _("Maximum %(count)s contacts.")
ERROR_CONTACT_REQUIRED = _("Ajoutez au moins un contact email.")
ERROR_ADMIN_CONTACT_REQUIRED = _("Ajoutez au moins un contact administratif.")
ERROR_PREPARATION_CONTACT_REQUIRED = _("Ajoutez au moins un contact préparation/logistique.")
ERROR_BILLING_PREFERENCES_INVALID = _(
    "Choisissez une périodicité et un mode de regroupement valides."
)
RECIPIENT_STATUS_PENDING_LABEL = _("En attente validation")
RECIPIENT_STATUS_VALIDATED_LABEL = _("Validé")
RECIPIENT_STRUCTURE_DOCUMENT_FIELDS = (
    (
        RecipientStructureDocumentType.REGISTRATION_PROOF,
        "doc_registration_proof",
        ERROR_RECIPIENT_REGISTRATION_PROOF_REQUIRED,
    ),
    (
        RecipientStructureDocumentType.STATUTES,
        "doc_statutes",
        ERROR_RECIPIENT_STATUTES_REQUIRED,
    ),
)
RECIPIENT_STRUCTURE_UPLOAD_FIELDS = {
    doc_type: field_name
    for doc_type, field_name, _error_message in RECIPIENT_STRUCTURE_DOCUMENT_FIELDS
}
PRODUCT_PREFERENCE_SCOPE_PRODUCT = "product"
PRODUCT_PREFERENCE_SCOPE_CATEGORY = "category"
PRODUCT_PREFERENCE_SCOPE_CHOICES = (
    (PRODUCT_PREFERENCE_SCOPE_PRODUCT, "Produit"),
    (PRODUCT_PREFERENCE_SCOPE_CATEGORY, "Catégorie"),
)
PRODUCT_PREFERENCE_STATUS_LABELS = {
    RecipientProductPreferenceStatus.REQUESTED: "Demandé",
    RecipientProductPreferenceStatus.ALLOWED: "Autorisé",
    RecipientProductPreferenceStatus.REFUSED: "Refusé",
}


def _build_default_product_preference_form_data():
    return {
        "preference_id": "",
        "scope_type": PRODUCT_PREFERENCE_SCOPE_PRODUCT,
        "product_id": "",
        "category_id": "",
        "status": RecipientProductPreferenceStatus.REQUESTED,
        "quantity_target": "",
        "period_unit": RecipientProductPreferencePeriodUnit.WEEK,
        "notes": "",
    }


def _split_multi_values(value):
    raw = (value or "").replace("\n", ";").replace(",", ";")
    return [item.strip() for item in raw.split(";") if item.strip()]


def _build_default_recipient_form_data():
    return {
        "destination_id": "",
        "structure_name": "",
        "legal_form": "",
        "beneficiary_count": "",
        "reuse_existing_structure": True,
        "contact_title": "",
        "contact_last_name": "",
        "contact_first_name": "",
        "phones": "",
        "emails": "",
        "address_line1": "",
        "address_line2": "",
        "postal_code": "",
        "city": "",
        "country": DEFAULT_COUNTRY,
        "notes": "",
        "notify_deliveries": False,
        "is_delivery_contact": False,
    }


def _build_default_preference_form_data():
    return {
        "product_id": "",
        "status": UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS,
        "quantity_target": "",
        "period_unit": "",
        "notes": "",
    }


def _extract_recipient_form_data(post_data):
    return {
        "destination_id": (post_data.get("destination_id") or "").strip(),
        "structure_name": (post_data.get("structure_name") or "").strip(),
        "legal_form": (post_data.get("legal_form") or "").strip(),
        "beneficiary_count": (post_data.get("beneficiary_count") or "").strip(),
        "reuse_existing_structure": bool(post_data.get("reuse_existing_structure")),
        "contact_title": (post_data.get("contact_title") or "").strip(),
        "contact_last_name": (post_data.get("contact_last_name") or "").strip(),
        "contact_first_name": (post_data.get("contact_first_name") or "").strip(),
        "phones": (post_data.get("phones") or "").strip(),
        "emails": (post_data.get("emails") or "").strip(),
        "address_line1": (post_data.get("address_line1") or "").strip(),
        "address_line2": (post_data.get("address_line2") or "").strip(),
        "postal_code": (post_data.get("postal_code") or "").strip(),
        "city": (post_data.get("city") or "").strip(),
        "country": (post_data.get("country") or DEFAULT_COUNTRY).strip(),
        "notes": (post_data.get("notes") or "").strip(),
        "notify_deliveries": bool(post_data.get("notify_deliveries")),
        "is_delivery_contact": bool(post_data.get("is_delivery_contact")),
    }


def _extract_preference_form_data(post_data):
    return {
        "product_id": (post_data.get("product_id") or "").strip(),
        "status": (post_data.get("status") or "").strip(),
        "quantity_target": (post_data.get("quantity_target") or "").strip(),
        "period_unit": (post_data.get("period_unit") or "").strip(),
        "notes": (post_data.get("notes") or "").strip(),
    }


def _preference_bulk_field_name(product_id, field_name):
    return f"preference_{product_id}_{field_name}"


def _extract_bulk_preference_form_data(post_data, product):
    product_id = product.id
    return {
        "product_id": str(product_id),
        "status": (post_data.get(_preference_bulk_field_name(product_id, "status")) or "").strip(),
        "quantity_target": (
            post_data.get(_preference_bulk_field_name(product_id, "quantity_target")) or ""
        ).strip(),
        "period_unit": (
            post_data.get(_preference_bulk_field_name(product_id, "period_unit")) or ""
        ).strip(),
        "notes": (post_data.get(_preference_bulk_field_name(product_id, "notes")) or "").strip(),
    }


def _normalize_preference_form_data_for_compare(form_data):
    return {
        "status": (form_data.get("status") or "").strip(),
        "quantity_target": (form_data.get("quantity_target") or "").strip(),
        "period_unit": (form_data.get("period_unit") or "").strip(),
        "notes": (form_data.get("notes") or "").strip(),
    }


def _preference_form_data_has_changes(form_data, current_form_data):
    return _normalize_preference_form_data_for_compare(
        form_data
    ) != _normalize_preference_form_data_for_compare(current_form_data)


def _build_recipient_form_data_from_instance(recipient):
    return {
        "destination_id": str(recipient.destination_id or ""),
        "structure_name": recipient.structure_name or "",
        "legal_form": recipient.legal_form or "",
        "beneficiary_count": str(recipient.beneficiary_count or ""),
        "reuse_existing_structure": True,
        "contact_title": recipient.contact_title or "",
        "contact_last_name": recipient.contact_last_name or "",
        "contact_first_name": recipient.contact_first_name or "",
        "phones": recipient.phones or recipient.phone or "",
        "emails": recipient.emails or recipient.email or "",
        "address_line1": recipient.address_line1 or "",
        "address_line2": recipient.address_line2 or "",
        "postal_code": recipient.postal_code or "",
        "city": recipient.city or "",
        "country": recipient.country or DEFAULT_COUNTRY,
        "notes": recipient.notes or "",
        "notify_deliveries": bool(recipient.notify_deliveries),
        "is_delivery_contact": bool(recipient.is_delivery_contact),
    }


def _extract_product_preference_form_data(post_data):
    return {
        "preference_id": (post_data.get("preference_id") or "").strip(),
        "scope_type": (post_data.get("scope_type") or "").strip(),
        "product_id": (post_data.get("product_id") or "").strip(),
        "category_id": (post_data.get("category_id") or "").strip(),
        "status": (post_data.get("status") or "").strip(),
        "quantity_target": (post_data.get("quantity_target") or "").strip(),
        "period_unit": (post_data.get("period_unit") or "").strip(),
        "notes": (post_data.get("notes") or "").strip(),
    }


def _build_preference_form_data_from_instance(preference):
    return {
        "product_id": str(preference.product_id),
        "status": preference.status,
        "quantity_target": str(preference.quantity_target or ""),
        "period_unit": preference.period_unit or "",
        "notes": preference.notes or "",
    }


def _build_preference_form_data_from_effective_preference(effective_preference):
    if effective_preference.preference is not None:
        return _build_preference_form_data_from_instance(effective_preference.preference)
    return {
        "product_id": str(effective_preference.product.pk),
        "status": UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS,
        "quantity_target": "",
        "period_unit": "",
        "notes": "",
    }


def _validate_recipient_form_data(form_data, destinations_by_id):
    errors = []
    valid_titles = {choice for choice, _label in AssociationContactTitle.choices}
    valid_legal_forms = {choice for choice, _label in RecipientLegalForm.choices}
    if form_data["contact_title"] and form_data["contact_title"] not in valid_titles:
        errors.append(ERROR_RECIPIENT_TITLE_INVALID)

    destination = None
    destination_id = parse_int(form_data["destination_id"])
    if destination_id is None:
        errors.append(ERROR_RECIPIENT_DESTINATION_REQUIRED)
    else:
        destination = destinations_by_id.get(destination_id)
        if destination is None:
            errors.append(ERROR_RECIPIENT_DESTINATION_REQUIRED)
    form_data["destination"] = destination

    if not form_data["structure_name"]:
        errors.append(ERROR_RECIPIENT_STRUCTURE_REQUIRED)
    if not form_data["legal_form"]:
        errors.append(ERROR_RECIPIENT_LEGAL_FORM_REQUIRED)
    elif form_data["legal_form"] not in valid_legal_forms:
        errors.append(ERROR_RECIPIENT_LEGAL_FORM_INVALID)
    if not form_data["address_line1"]:
        errors.append(ERROR_RECIPIENT_ADDRESS_REQUIRED)
    if not form_data["beneficiary_count"]:
        errors.append(ERROR_RECIPIENT_BENEFICIARY_COUNT_REQUIRED)
    else:
        beneficiary_count = parse_int(form_data["beneficiary_count"])
        if beneficiary_count is None or beneficiary_count < 0:
            errors.append(ERROR_RECIPIENT_BENEFICIARY_COUNT_INVALID)
        else:
            form_data["beneficiary_count_value"] = beneficiary_count
    if not is_known_country(form_data["country"]):
        errors.append(ERROR_RECIPIENT_COUNTRY_INVALID)

    email_values = _split_multi_values(form_data["emails"])
    invalid_emails = []
    validator = EmailValidator()
    for value in email_values:
        try:
            validator(value)
        except ValidationError:
            invalid_emails.append(value)
    if invalid_emails:
        errors.append(ERROR_RECIPIENT_EMAILS_INVALID % {"values": ", ".join(invalid_emails)})
    if form_data["notify_deliveries"] and not email_values:
        errors.append(ERROR_RECIPIENT_NOTIFY_EMAIL_REQUIRED)

    form_data["email_values"] = email_values
    form_data["phone_values"] = _split_multi_values(form_data["phones"])
    return errors


def _prepare_preference_form_data(form_data, products_by_id):
    errors = []
    product = products_by_id.get(parse_int(form_data["product_id"]))
    if product is None:
        errors.append(ERROR_RECIPIENT_PRODUCT_REQUIRED)
    form_data["product"] = product

    valid_statuses = {choice for choice, _label in RecipientProductPreferenceStatus.choices} | {
        UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS
    }
    if form_data["status"] not in valid_statuses:
        errors.append(ERROR_RECIPIENT_PRODUCT_STATUS_INVALID)

    if form_data["status"] == UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS:
        form_data["quantity_target_value"] = None
        form_data["period_unit"] = ""
        return errors

    quantity_raw = form_data["quantity_target"]
    if quantity_raw:
        quantity_target = parse_int(quantity_raw)
        if quantity_target is None or quantity_target < 0:
            errors.append(ERROR_RECIPIENT_PRODUCT_QUANTITY_INVALID)
        else:
            form_data["quantity_target_value"] = quantity_target
    else:
        form_data["quantity_target_value"] = None

    valid_period_units = {choice for choice, _label in RecipientProductPreferencePeriodUnit.choices}
    if form_data["period_unit"] and form_data["period_unit"] not in valid_period_units:
        errors.append(ERROR_RECIPIENT_PRODUCT_PERIOD_INVALID)

    return errors


def _flatten_validation_error_messages(error):
    if hasattr(error, "message_dict"):
        messages_list = []
        for values in error.message_dict.values():
            messages_list.extend(str(value) for value in values)
        return messages_list
    return [str(value) for value in error.messages]


def _validate_recipient_creation_documents(request):
    errors = []
    for _doc_type, field_name, missing_error in RECIPIENT_STRUCTURE_DOCUMENT_FIELDS:
        uploaded = request.FILES.get(field_name)
        if not uploaded:
            errors.append(missing_error)
            continue
        validation_error = validate_upload(uploaded)
        if validation_error:
            errors.append(validation_error)
    return errors


def _validate_recipient_uploaded_documents(files):
    errors = []
    for _doc_type, field_name, _missing_error in RECIPIENT_STRUCTURE_DOCUMENT_FIELDS:
        uploaded = files.get(field_name) if files else None
        if not uploaded:
            continue
        validation_error = validate_upload(uploaded)
        if validation_error:
            errors.append(validation_error)
    return errors


def _build_recipient_payload(form_data):
    title_label = dict(AssociationContactTitle.choices).get(form_data["contact_title"], "")
    contact_display = " ".join(
        part
        for part in [
            str(title_label) if title_label else "",
            form_data["contact_first_name"],
            (form_data["contact_last_name"] or "").upper(),
        ]
        if part
    ).strip()
    legacy_name = form_data["structure_name"] or contact_display
    primary_email = form_data["email_values"][0] if form_data["email_values"] else ""
    primary_phone = form_data["phone_values"][0] if form_data["phone_values"] else ""
    return {
        "destination": form_data.get("destination"),
        "name": legacy_name,
        "structure_name": form_data["structure_name"],
        "contact_title": form_data["contact_title"],
        "contact_last_name": form_data["contact_last_name"],
        "contact_first_name": form_data["contact_first_name"],
        "phones": "; ".join(form_data["phone_values"]),
        "emails": "; ".join(form_data["email_values"]),
        "email": primary_email,
        "phone": primary_phone,
        "address_line1": form_data["address_line1"],
        "address_line2": form_data["address_line2"],
        "postal_code": form_data["postal_code"],
        "city": form_data["city"],
        "country": form_data["country"] or DEFAULT_COUNTRY,
        "legal_form": form_data["legal_form"],
        "beneficiary_count": form_data.get("beneficiary_count_value"),
        "notes": form_data["notes"],
        "notify_deliveries": form_data["notify_deliveries"],
        "is_delivery_contact": form_data["is_delivery_contact"],
    }


def _create_recipient_structure_documents(*, contact, uploaded_by, files):
    if contact is None:
        return []

    files_by_type = {}
    for doc_type, field_name, _missing_error in RECIPIENT_STRUCTURE_DOCUMENT_FIELDS:
        uploaded = files.get(field_name) if files else None
        if uploaded:
            files_by_type[doc_type] = uploaded

    return upsert_recipient_structure_documents(
        contact=contact,
        files_by_type=files_by_type,
        uploaded_by=uploaded_by,
        queue_scan=True,
    )


def _create_recipient(profile, form_data, *, uploaded_by=None, files=None):
    payload = _build_recipient_payload(form_data)
    with transaction.atomic():
        result = update_recipient_shared_profile(
            association_contact=profile.contact,
            destination=payload["destination"],
            structure_name=payload["structure_name"],
            contact_title=payload["contact_title"],
            contact_first_name=payload["contact_first_name"],
            contact_last_name=payload["contact_last_name"],
            emails=payload["emails"],
            phones=payload["phones"],
            address_line1=payload["address_line1"],
            address_line2=payload["address_line2"],
            postal_code=payload["postal_code"],
            city=payload["city"],
            country=payload["country"],
            legal_form=payload["legal_form"],
            beneficiary_count=payload["beneficiary_count"],
            notes=payload["notes"],
            notify_deliveries=payload["notify_deliveries"],
            is_delivery_contact=payload["is_delivery_contact"],
            persist_projection=True,
            prefer_existing_structure=form_data["reuse_existing_structure"],
        )
        _create_recipient_structure_documents(
            contact=result.synced_contact,
            uploaded_by=uploaded_by,
            files=files or {},
        )
    return result


def _recipient_validation_contact_details(result):
    shipment_contact = getattr(result, "shipment_contact", None)
    contact = getattr(shipment_contact, "contact", None)
    synced_contact = getattr(result, "synced_contact", None)
    return {
        "email": (getattr(contact, "email", "") or getattr(synced_contact, "email", "") or ""),
        "phone": (getattr(contact, "phone", "") or getattr(synced_contact, "phone", "") or ""),
    }


def _queue_recipient_validation_notification(request, *, profile, result):
    recipient_organization = getattr(result, "recipient_organization", None)
    if recipient_organization is None:
        return
    if recipient_organization.validation_status != ShipmentValidationStatus.PENDING:
        return

    admin_recipients = get_admin_emails() + get_group_emails(
        getattr(
            settings,
            "ACCOUNT_REQUEST_VALIDATION_GROUP_NAME",
            ACCOUNT_REQUEST_VALIDATION_GROUP_DEFAULT,
        ),
        require_staff=True,
    )
    if not admin_recipients:
        return

    contact_details = _recipient_validation_contact_details(result)
    base_url = build_public_base_url(request)
    scan_url = f"{base_url}{reverse('scan:scan_recipient_validation_detail', args=[recipient_organization.id])}"
    message = render_to_string(
        TEMPLATE_RECIPIENT_VALIDATION_ADMIN_NOTIFICATION,
        {
            "association_name": profile.contact.name,
            "recipient_name": recipient_organization.organization.name,
            "destination": recipient_organization.destination,
            "email": contact_details["email"],
            "phone": contact_details["phone"],
            "scan_url": scan_url,
        },
    )

    def _send_notification():
        sent = send_or_enqueue_email_safe(
            subject=SUBJECT_RECIPIENT_VALIDATION_PENDING,
            message=message,
            recipient=admin_recipients,
        )
        if not sent:
            LOGGER.warning(
                "Recipient validation notification was not sent nor queued for %s",
                recipient_organization.id,
            )

    transaction.on_commit(_send_notification)


def _update_recipient(recipient, form_data):
    payload = _build_recipient_payload(form_data)
    result = update_recipient_shared_profile(
        association_contact=recipient.association_contact,
        destination=payload["destination"],
        structure_name=payload["structure_name"],
        contact_title=payload["contact_title"],
        contact_first_name=payload["contact_first_name"],
        contact_last_name=payload["contact_last_name"],
        emails=payload["emails"],
        phones=payload["phones"],
        address_line1=payload["address_line1"],
        address_line2=payload["address_line2"],
        postal_code=payload["postal_code"],
        city=payload["city"],
        country=payload["country"],
        legal_form=payload["legal_form"],
        beneficiary_count=payload["beneficiary_count"],
        notes=payload["notes"],
        notify_deliveries=payload["notify_deliveries"],
        is_delivery_contact=payload["is_delivery_contact"],
        legacy_projection=recipient,
        persist_projection=True,
        prefer_existing_structure=form_data["reuse_existing_structure"],
    )
    return result.legacy_projection or recipient


def _get_recipient_for_profile(profile, recipient_id):
    return (
        AssociationRecipient.objects.filter(
            association_contact=profile.contact,
            is_active=True,
            pk=recipient_id,
        )
        .select_related("destination")
        .first()
    )


def _get_shipment_recipient_for_association_recipient(recipient):
    if recipient is None or recipient.synced_contact_id is None or recipient.destination_id is None:
        return None
    return ShipmentRecipientOrganization.objects.filter(
        organization_id=recipient.synced_contact_id,
        destination_id=recipient.destination_id,
        is_active=True,
    ).first()


def _get_portal_recipient_or_404(profile, recipient_id):
    return get_object_or_404(
        AssociationRecipient.objects.select_related("destination", "synced_contact"),
        pk=recipient_id,
        association_contact=profile.contact,
        is_active=True,
    )


def _get_active_recipients(profile):
    return (
        AssociationRecipient.objects.filter(
            association_contact=profile.contact,
            is_active=True,
        )
        .select_related("destination", "synced_contact")
        .order_by("structure_name", "name", "contact_last_name", "contact_first_name")
    )


def _build_recipient_validation_status_display(validation_status):
    if validation_status == ShipmentValidationStatus.VALIDATED:
        return {
            "value": ShipmentValidationStatus.VALIDATED,
            "label": RECIPIENT_STATUS_VALIDATED_LABEL,
            "badge_class": "portal-badge is-ready",
        }
    return {
        "value": ShipmentValidationStatus.PENDING,
        "label": RECIPIENT_STATUS_PENDING_LABEL,
        "badge_class": "portal-badge is-info",
    }


def _decorate_recipient_validation_statuses(recipients):
    recipients = list(recipients)
    recipient_keys = {
        (recipient.synced_contact_id, recipient.destination_id)
        for recipient in recipients
        if recipient.synced_contact_id and recipient.destination_id
    }
    recipient_orgs_by_key = {
        (recipient_org.organization_id, recipient_org.destination_id): recipient_org
        for recipient_org in ShipmentRecipientOrganization.objects.filter(
            organization_id__in={key[0] for key in recipient_keys},
            destination_id__in={key[1] for key in recipient_keys},
            is_active=True,
        ).only("organization_id", "destination_id", "validation_status", "is_active")
    }
    for recipient in recipients:
        recipient_org = recipient_orgs_by_key.get(
            (recipient.synced_contact_id, recipient.destination_id)
        )
        recipient.validation_status_display = _build_recipient_validation_status_display(
            recipient_org.validation_status if recipient_org is not None else None
        )
    return recipients


def _get_runtime_recipient_organization(recipient):
    if recipient.synced_contact_id is None or recipient.destination_id is None:
        return None

    return (
        ShipmentRecipientOrganization.objects.filter(
            organization_id=recipient.synced_contact_id,
            destination_id=recipient.destination_id,
            is_active=True,
        )
        .select_related("organization", "destination")
        .first()
    )


def _build_recipient_form_data_from_runtime(recipient_organization):
    payload = build_runtime_recipient_profile_payload(recipient_organization=recipient_organization)
    return {
        "destination_id": str(recipient_organization.destination_id or ""),
        "structure_name": payload["structure_name"],
        "legal_form": payload["legal_form"],
        "beneficiary_count": str(payload["beneficiary_count"] or ""),
        "reuse_existing_structure": True,
        **{
            **payload,
            "country": payload["country"] or DEFAULT_COUNTRY,
        },
    }


def _recipient_shared_fields_are_read_only(recipient_organization):
    if recipient_organization is None:
        return False
    return PortalAccessGrant.objects.filter(
        recipient_organization=recipient_organization,
        role=PortalAccessRole.RECIPIENT_ADMIN,
        is_active=True,
    ).exists()


def _build_recipient_detail_context(
    *,
    recipient,
    recipient_organization,
    recipient_shared_fields_read_only=False,
    preference_errors=None,
    preference_form_data_by_product_id=None,
    preference_errors_by_product_id=None,
    filter_state=None,
    preference_filter_reset_url="",
):
    catalog_context = {
        "recipient_preferences": [],
        "recipient_product_rows": [],
        "recipient_preference_coverage_rows": [],
        "preference_products": [],
        "preference_query": (filter_state or {}).get("query", ""),
        "preference_category_id": (filter_state or {}).get("category_id", ""),
        "preference_sort": (filter_state or {}).get("sort", ""),
    }
    if recipient_organization is not None:
        catalog_context = build_recipient_preference_catalog_context(
            recipient_organization=recipient_organization,
            filter_state=filter_state or {},
            build_form_data=_build_preference_form_data_from_effective_preference,
            preference_form_data_by_product_id=preference_form_data_by_product_id,
            preference_errors_by_product_id=preference_errors_by_product_id,
        )

    return {
        "recipient": recipient,
        "recipient_organization": recipient_organization,
        "recipient_shared_fields_read_only": recipient_shared_fields_read_only,
        "preference_errors": preference_errors or [],
        "preference_filter_reset_url": preference_filter_reset_url,
        "preference_filter_hidden_fields": [],
        **catalog_context,
    }


def _build_recipient_preferences_context(
    *,
    recipient_organization,
    preference_errors=None,
    preference_form_data_by_product_id=None,
    preference_errors_by_product_id=None,
    filter_state=None,
    preference_filter_reset_url="",
):
    context = _build_recipient_detail_context(
        recipient=None,
        recipient_organization=recipient_organization,
        recipient_shared_fields_read_only=False,
        preference_errors=preference_errors,
        preference_form_data_by_product_id=preference_form_data_by_product_id,
        preference_errors_by_product_id=preference_errors_by_product_id,
        filter_state=filter_state,
        preference_filter_reset_url=preference_filter_reset_url,
    )
    context.update(
        {
            "recipient_structure_name": recipient_organization.organization.name or "-",
            "recipient_destination_label": str(recipient_organization.destination)
            if recipient_organization.destination
            else "-",
        }
    )
    return context


def _build_recipient_profile_context(
    *,
    recipient_organization,
    errors=None,
    form_data=None,
):
    payload = build_recipient_scope_home_payload(recipient_organization=recipient_organization)
    current_form_data = form_data or _build_recipient_form_data_from_runtime(recipient_organization)
    return {
        **payload,
        "errors": errors or [],
        "form_data": current_form_data,
        "contact_title_choices": sorted_choices(AssociationContactTitle.choices),
        "legal_form_choices": sorted_choices(RecipientLegalForm.choices),
        "country_choices": build_country_choices(current_form_data.get("country")),
    }


def _build_duplicate_recipient_suggestions(*, form_data, editing_recipient=None):
    destination = form_data.get("destination")
    structure_name = (form_data.get("structure_name") or "").strip()
    if destination is None or not structure_name:
        return []

    suggestions = (
        ShipmentRecipientOrganization.objects.filter(
            destination=destination,
            organization__is_active=True,
        )
        .filter(
            Q(organization__name__iexact=structure_name)
            | Q(organization__name__icontains=structure_name)
            | Q(organization__name__istartswith=structure_name)
        )
        .select_related("organization", "destination")
        .order_by("organization__name", "id")
    )

    current_synced_contact_id = getattr(editing_recipient, "synced_contact_id", None)
    if current_synced_contact_id:
        suggestions = suggestions.exclude(organization_id=current_synced_contact_id)

    return [
        {
            "id": suggestion.id,
            "name": suggestion.organization.name,
            "destination": str(suggestion.destination),
            "validation_status": suggestion.validation_status,
            "is_correspondent": suggestion.is_correspondent,
        }
        for suggestion in suggestions[:5]
    ]


def _product_preference_validation_messages(exc):
    if getattr(exc, "message_dict", None):
        messages = []
        for field_messages in exc.message_dict.values():
            messages.extend(str(message) for message in field_messages if message)
        return messages
    return [str(message) for message in getattr(exc, "messages", []) if message]


def _product_preference_category_label(category):
    parts = []
    current = category
    while current is not None:
        parts.append(current.name)
        current = current.parent
    return " > ".join(reversed(parts))


def _product_preference_status_label(status):
    return PRODUCT_PREFERENCE_STATUS_LABELS.get(status, status)


def _build_product_preference_choices():
    product_choices = [
        (str(product.id), product.name)
        for product in Product.objects.filter(is_active=True).order_by("name", "id")
    ]
    categories = list(ProductCategory.objects.select_related("parent").order_by("name", "id"))
    category_choices = [
        (str(category.id), _product_preference_category_label(category)) for category in categories
    ]
    category_choices = sorted(category_choices, key=lambda choice: choice[1].lower())
    return product_choices, category_choices


def _build_product_preference_rows(recipient_organization):
    if recipient_organization is None:
        return []
    rows = []
    preferences = recipient_organization.product_preferences.select_related(
        "product",
        "category",
    ).order_by("id")
    for preference in preferences:
        rows.append(
            {
                "id": preference.id,
                "scope_type": (
                    PRODUCT_PREFERENCE_SCOPE_PRODUCT
                    if preference.product_id
                    else PRODUCT_PREFERENCE_SCOPE_CATEGORY
                ),
                "target_label": (
                    preference.product.name
                    if preference.product_id
                    else _product_preference_category_label(preference.category)
                ),
                "status_label": _product_preference_status_label(preference.status),
                "quantity_target": preference.quantity_target,
                "period_unit_label": preference.get_period_unit_display()
                if preference.period_unit
                else "-",
                "notes": preference.notes,
            }
        )
    return rows


def _build_product_preference_form_data_from_instance(preference):
    return {
        "preference_id": str(preference.id),
        "scope_type": (
            PRODUCT_PREFERENCE_SCOPE_PRODUCT
            if preference.product_id
            else PRODUCT_PREFERENCE_SCOPE_CATEGORY
        ),
        "product_id": str(preference.product_id or ""),
        "category_id": str(preference.category_id or ""),
        "status": preference.status,
        "quantity_target": str(preference.quantity_target or ""),
        "period_unit": preference.period_unit or "",
        "notes": preference.notes or "",
    }


def _save_product_preference(
    *,
    recipient_organization,
    form_data,
    user,
):
    errors = []
    scope_type = form_data["scope_type"]
    valid_statuses = {choice for choice, _label in RecipientProductPreferenceStatus.choices}
    valid_period_units = {choice for choice, _label in RecipientProductPreferencePeriodUnit.choices}
    if scope_type not in {PRODUCT_PREFERENCE_SCOPE_PRODUCT, PRODUCT_PREFERENCE_SCOPE_CATEGORY}:
        errors.append(ERROR_RECIPIENT_PREFERENCE_SCOPE_INVALID)
        return None, errors
    if form_data["status"] not in valid_statuses:
        errors.append("Statut de préférence invalide.")
        return None, errors

    product = None
    category = None
    if scope_type == PRODUCT_PREFERENCE_SCOPE_PRODUCT:
        product = Product.objects.filter(
            pk=parse_int(form_data["product_id"]),
            is_active=True,
        ).first()
        if product is None:
            errors.append(ERROR_RECIPIENT_PREFERENCE_SCOPE_INVALID)
    else:
        category = ProductCategory.objects.filter(pk=parse_int(form_data["category_id"])).first()
        if category is None:
            errors.append(ERROR_RECIPIENT_PREFERENCE_SCOPE_INVALID)

    quantity_target = None
    if form_data["quantity_target"]:
        quantity_target = parse_int(form_data["quantity_target"])
        if quantity_target is None or quantity_target <= 0:
            errors.append("Quantité cible invalide.")
    period_unit = form_data["period_unit"]
    if period_unit and period_unit not in valid_period_units:
        errors.append("Période invalide.")

    if errors:
        return None, errors

    preference_id = parse_int(form_data["preference_id"])
    if preference_id is not None:
        preference = recipient_organization.product_preferences.filter(pk=preference_id).first()
        if preference is None:
            return None, [ERROR_RECIPIENT_PREFERENCE_NOT_FOUND]
    elif scope_type == PRODUCT_PREFERENCE_SCOPE_PRODUCT and product is not None:
        preference = recipient_organization.product_preferences.filter(product=product).first()
    elif scope_type == PRODUCT_PREFERENCE_SCOPE_CATEGORY and category is not None:
        preference = recipient_organization.product_preferences.filter(category=category).first()
    else:
        preference = None

    try:
        preference = save_recipient_product_preference(
            recipient_organization=recipient_organization,
            product=product if scope_type == PRODUCT_PREFERENCE_SCOPE_PRODUCT else None,
            category=category if scope_type == PRODUCT_PREFERENCE_SCOPE_CATEGORY else None,
            status=form_data["status"],
            quantity_target=quantity_target,
            period_unit=period_unit,
            notes=form_data["notes"],
            source=RecipientProductPreferenceSource.PORTAL,
            user=user,
        )
    except ValidationError as exc:
        return None, _product_preference_validation_messages(exc)

    return preference, []


def _handle_account_document_upload(request, association):
    payload, error = validate_document_upload(
        request,
        doc_type_choices=AccountDocumentType.choices,
    )
    if error:
        messages.error(request, error)
        return redirect("portal:portal_account")

    doc_type, uploaded = payload
    document = AccountDocument.objects.create(
        association_contact=association,
        doc_type=doc_type,
        status=DocumentReviewStatus.PENDING,
        file=uploaded,
        uploaded_by=request.user,
        scan_status=DocumentScanStatus.PENDING,
        scan_message="Scan antivirus en cours.",
    )
    queue_document_scan(document)
    messages.success(request, MESSAGE_DOCUMENT_ADDED)
    return redirect("portal:portal_account")


def _build_profile_form_data(*, association, address):
    return {
        "association_name": association.name or "",
        "association_email": association.email or "",
        "association_phone": association.phone or "",
        "address_line1": address.address_line1 if address else "",
        "address_line2": address.address_line2 if address else "",
        "postal_code": address.postal_code if address else "",
        "city": address.city if address else "",
        "country": (address.country if address else "") or DEFAULT_COUNTRY,
    }


def _build_default_contact_row(*, index):
    return {
        "index": index,
        "title": "",
        "last_name": "",
        "first_name": "",
        "phone": "",
        "email": "",
        "phones": "",
        "emails": "",
        "address_line1": "",
        "address_line2": "",
        "postal_code": "",
        "city": "",
        "country": DEFAULT_COUNTRY,
        "is_administrative": False,
        "is_shipping": False,
        "is_billing": False,
    }


def _build_contact_rows(profile):
    contacts = list(profile.portal_contacts.filter(is_active=True))
    if not contacts:
        return [_build_default_contact_row(index=0)]
    rows = []
    for index, contact in enumerate(contacts[:MAX_PORTAL_CONTACTS]):
        rows.append(
            {
                "index": index,
                "title": contact.title or "",
                "last_name": contact.last_name or "",
                "first_name": contact.first_name or "",
                "phone": contact.phone or "",
                "email": contact.email or "",
                "phones": contact.phones or contact.phone or "",
                "emails": contact.emails or contact.email or "",
                "address_line1": contact.address_line1 or "",
                "address_line2": contact.address_line2 or "",
                "postal_code": contact.postal_code or "",
                "city": contact.city or "",
                "country": contact.country or DEFAULT_COUNTRY,
                "is_administrative": contact.is_administrative,
                "is_shipping": contact.is_shipping,
                "is_billing": contact.is_billing,
            }
        )
    return rows or [_build_default_contact_row(index=0)]


def _extract_profile_form_data(post_data):
    return {
        "association_name": (post_data.get("association_name") or "").strip(),
        "association_email": (post_data.get("association_email") or "").strip(),
        "association_phone": (post_data.get("association_phone") or "").strip(),
        "address_line1": (post_data.get("address_line1") or "").strip(),
        "address_line2": (post_data.get("address_line2") or "").strip(),
        "postal_code": (post_data.get("postal_code") or "").strip(),
        "city": (post_data.get("city") or "").strip(),
        "country": (post_data.get("country") or DEFAULT_COUNTRY).strip(),
    }


def _extract_contact_rows(post_data):
    errors = []
    requested_count = parse_int(post_data.get("contact_count")) or 1
    if requested_count > MAX_PORTAL_CONTACTS:
        errors.append(ERROR_CONTACT_ROWS_LIMIT % {"count": MAX_PORTAL_CONTACTS})
    count = min(max(1, requested_count), MAX_PORTAL_CONTACTS)
    rows = []
    for index in range(count):
        row = {
            "index": index,
            "title": (post_data.get(f"contact_{index}_title") or "").strip(),
            "last_name": (post_data.get(f"contact_{index}_last_name") or "").strip(),
            "first_name": (post_data.get(f"contact_{index}_first_name") or "").strip(),
            "phone": (post_data.get(f"contact_{index}_phone") or "").strip(),
            "email": (post_data.get(f"contact_{index}_email") or "").strip(),
            "phones": (
                post_data.get(f"contact_{index}_phones")
                or post_data.get(f"contact_{index}_phone")
                or ""
            ).strip(),
            "emails": (
                post_data.get(f"contact_{index}_emails")
                or post_data.get(f"contact_{index}_email")
                or ""
            ).strip(),
            "address_line1": (
                post_data.get(f"contact_{index}_address_line1")
                or post_data.get("address_line1")
                or ""
            ).strip(),
            "address_line2": (
                post_data.get(f"contact_{index}_address_line2")
                or post_data.get("address_line2")
                or ""
            ).strip(),
            "postal_code": (
                post_data.get(f"contact_{index}_postal_code") or post_data.get("postal_code") or ""
            ).strip(),
            "city": (post_data.get(f"contact_{index}_city") or post_data.get("city") or "").strip(),
            "country": (
                post_data.get(f"contact_{index}_country")
                or post_data.get("country")
                or DEFAULT_COUNTRY
            ).strip(),
            "is_administrative": bool(post_data.get(f"contact_{index}_is_administrative")),
            "is_shipping": bool(post_data.get(f"contact_{index}_is_shipping")),
            "is_billing": bool(post_data.get(f"contact_{index}_is_billing")),
        }
        has_values = any(
            [
                row["title"],
                row["last_name"],
                row["first_name"],
                row["phone"],
                row["email"],
                row["address_line1"],
                row["city"],
                row["country"],
                row["is_administrative"],
                row["is_shipping"],
                row["is_billing"],
            ]
        )
        if not has_values:
            continue
        if not row["email"]:
            errors.append(_("Ligne %(index)s: email requis.") % {"index": index + 1})
        if not row["phone"]:
            errors.append(_("Ligne %(index)s: téléphone requis.") % {"index": index + 1})
        if not row["title"]:
            errors.append(_("Ligne %(index)s: titre requis.") % {"index": index + 1})
        if not row["last_name"]:
            errors.append(_("Ligne %(index)s: nom requis.") % {"index": index + 1})
        if not row["first_name"]:
            errors.append(_("Ligne %(index)s: prénom requis.") % {"index": index + 1})
        if not row["address_line1"]:
            errors.append(_("Ligne %(index)s: adresse requise.") % {"index": index + 1})
        if not row["city"]:
            errors.append(_("Ligne %(index)s: ville requise.") % {"index": index + 1})
        if not row["country"]:
            errors.append(_("Ligne %(index)s: pays requis.") % {"index": index + 1})
        if not (row["is_administrative"] or row["is_shipping"] or row["is_billing"]):
            errors.append(_("Ligne %(index)s: cochez au moins un type.") % {"index": index + 1})
        rows.append(row)

    if not rows:
        errors.append(ERROR_CONTACT_REQUIRED)
        rows = [_build_default_contact_row(index=0)]
    if not any(row["is_administrative"] for row in rows):
        errors.append(ERROR_ADMIN_CONTACT_REQUIRED)
    if not any(row["is_shipping"] for row in rows):
        errors.append(ERROR_PREPARATION_CONTACT_REQUIRED)
    return rows, errors


def _validate_profile_form_data(form_data):
    errors = []
    if not form_data["association_name"]:
        errors.append(ERROR_ASSOCIATION_NAME_REQUIRED)
    if not form_data["address_line1"]:
        errors.append(ERROR_ASSOCIATION_ADDRESS_REQUIRED)
    return errors


def _handle_account_document_uploads(request, association):
    created = 0
    for doc_type, _label in AccountDocumentType.choices:
        file_field = f"doc_file_{doc_type}"
        uploaded = request.FILES.get(file_field)
        if not uploaded:
            continue
        validation_error = validate_upload(uploaded)
        if validation_error:
            messages.error(request, validation_error)
            continue
        document = AccountDocument.objects.create(
            association_contact=association,
            doc_type=doc_type,
            status=DocumentReviewStatus.PENDING,
            file=uploaded,
            uploaded_by=request.user,
            scan_status=DocumentScanStatus.PENDING,
            scan_message="Scan antivirus en cours.",
        )
        queue_document_scan(document)
        created += 1
    if not created:
        messages.error(request, ERROR_NO_DOCUMENT_SELECTED)
        return redirect("portal:portal_account")
    messages.success(request, MESSAGE_DOCUMENTS_ADDED)
    return redirect("portal:portal_account")


def _build_portal_account_context(
    *,
    profile,
    address,
    user,
    account_form_errors=None,
    profile_form_data=None,
    portal_contact_rows=None,
):
    association = profile.contact
    account_documents = AccountDocument.objects.filter(association_contact=association).order_by(
        "-uploaded_at"
    )
    return {
        "association": association,
        "address": address,
        "notification_emails": profile.notification_emails,
        "billing_profile": profile.billing_profile,
        "billing_frequency_choices": sorted_choices(AssociationBillingFrequency.choices),
        "billing_grouping_mode_choices": sorted_choices(AssociationBillingGroupingMode.choices),
        "billing_change_requests": list(
            profile.billing_change_requests.order_by("-requested_at")[:5]
        ),
        "account_documents": account_documents,
        "account_doc_types": list(AccountDocumentType.choices),
        "account_form_errors": account_form_errors or [],
        "profile_form_data": profile_form_data
        or _build_profile_form_data(association=association, address=address),
        "portal_contact_rows": portal_contact_rows or _build_contact_rows(profile),
        "empty_portal_contact_row": _build_default_contact_row(index="__INDEX__"),
        "contact_title_choices": sorted_choices(AssociationContactTitle.choices),
        "max_portal_contacts": MAX_PORTAL_CONTACTS,
        "portal_account_add_contact_button_attrs": {"id": "add-contact-row"},
        "user": user,
    }


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_recipients(request):
    profile = request.association_profile
    errors = []
    form_data = _build_default_recipient_form_data()
    editing_recipient = None
    recipient_shared_fields_read_only = False
    product_preference_errors = []
    product_preference_form_data = _build_default_product_preference_form_data()
    editing_product_preference = None
    destinations = sorted(
        Destination.objects.filter(is_active=True),
        key=lambda destination: str(destination).lower(),
    )
    destinations_by_id = {destination.id: destination for destination in destinations}
    product_choices, category_choices = _build_product_preference_choices()
    blocked_reason = (request.GET.get(BLOCKED_REASON_QUERY_PARAM) or "").strip()
    blocked_popup_message = ""
    duplicate_recipient_suggestions = []
    legal_form_choices = sorted_choices(RecipientLegalForm.choices)
    if blocked_reason in {BLOCKED_REASON_MISSING_DELIVERY_CONTACT}:
        blocked_popup_message = BLOCKED_MESSAGES.get(blocked_reason, "")

    if request.method == "POST":
        action = request.POST.get("action")
        if action in {ACTION_CREATE_RECIPIENT, ACTION_UPDATE_RECIPIENT}:
            form_data = _extract_recipient_form_data(request.POST)
            errors = _validate_recipient_form_data(form_data, destinations_by_id)
            if action == ACTION_CREATE_RECIPIENT:
                errors.extend(_validate_recipient_creation_documents(request))
            if action == ACTION_UPDATE_RECIPIENT:
                recipient_id = parse_int(request.POST.get("recipient_id"))
                editing_recipient = _get_recipient_for_profile(profile, recipient_id)
                if editing_recipient is None:
                    errors.append(ERROR_RECIPIENT_NOT_FOUND)
                else:
                    recipient_organization = _get_shipment_recipient_for_association_recipient(
                        editing_recipient
                    )
                    recipient_shared_fields_read_only = _recipient_shared_fields_are_read_only(
                        recipient_organization
                    )
                    if recipient_shared_fields_read_only:
                        errors.append(ERROR_RECIPIENT_SHARED_READ_ONLY)
            duplicate_recipient_suggestions = _build_duplicate_recipient_suggestions(
                form_data=form_data,
                editing_recipient=editing_recipient,
            )
            if not errors:
                if action == ACTION_UPDATE_RECIPIENT:
                    _update_recipient(editing_recipient, form_data)
                    messages.success(request, MESSAGE_RECIPIENT_UPDATED)
                else:
                    recipient_result = _create_recipient(
                        profile,
                        form_data,
                        uploaded_by=request.user,
                        files=request.FILES,
                    )
                    _queue_recipient_validation_notification(
                        request,
                        profile=profile,
                        result=recipient_result,
                    )
                    messages.success(request, MESSAGE_RECIPIENT_ADDED)
                return redirect("portal:portal_recipients")
        elif action in {ACTION_SAVE_PRODUCT_PREFERENCE, ACTION_DELETE_PRODUCT_PREFERENCE}:
            recipient_id = parse_int(request.POST.get("recipient_id"))
            editing_recipient = _get_recipient_for_profile(profile, recipient_id)
            if editing_recipient is None:
                product_preference_errors.append(ERROR_RECIPIENT_NOT_FOUND)
            else:
                form_data = _build_recipient_form_data_from_instance(editing_recipient)
                duplicate_recipient_suggestions = _build_duplicate_recipient_suggestions(
                    form_data=form_data,
                    editing_recipient=editing_recipient,
                )
                recipient_organization = _get_shipment_recipient_for_association_recipient(
                    editing_recipient
                )
                recipient_shared_fields_read_only = _recipient_shared_fields_are_read_only(
                    recipient_organization
                )
                if recipient_organization is None:
                    product_preference_errors.append(ERROR_RECIPIENT_PREFERENCE_RECIPIENT_REQUIRED)
                elif recipient_shared_fields_read_only:
                    product_preference_errors.append(ERROR_RECIPIENT_SHARED_READ_ONLY)
                elif action == ACTION_DELETE_PRODUCT_PREFERENCE:
                    preference_id = parse_int(request.POST.get("preference_id"))
                    preference = recipient_organization.product_preferences.filter(
                        pk=preference_id
                    ).first()
                    if preference is None:
                        product_preference_errors.append(ERROR_RECIPIENT_PREFERENCE_NOT_FOUND)
                    else:
                        preference.delete()
                        messages.success(request, MESSAGE_RECIPIENT_PRODUCT_PREFERENCE_DELETED)
                        return redirect(
                            f"{reverse('portal:portal_recipients')}?edit={editing_recipient.id}#recipient-product-preferences"
                        )
                else:
                    product_preference_form_data = _extract_product_preference_form_data(
                        request.POST
                    )
                    saved_preference, product_preference_errors = _save_product_preference(
                        recipient_organization=recipient_organization,
                        form_data=product_preference_form_data,
                        user=request.user,
                    )
                    if not product_preference_errors:
                        messages.success(request, MESSAGE_RECIPIENT_PRODUCT_PREFERENCE_SAVED)
                        return redirect(
                            f"{reverse('portal:portal_recipients')}?edit={editing_recipient.id}#recipient-product-preferences"
                        )
                    if saved_preference is not None:
                        editing_product_preference = saved_preference

    if request.method == "GET":
        edit_recipient_id = parse_int(request.GET.get("edit"))
        if edit_recipient_id is not None:
            editing_recipient = _get_recipient_for_profile(profile, edit_recipient_id)
            if editing_recipient is not None:
                form_data = _build_recipient_form_data_from_instance(editing_recipient)
                duplicate_recipient_suggestions = _build_duplicate_recipient_suggestions(
                    form_data=form_data,
                    editing_recipient=editing_recipient,
                )
                recipient_organization = _get_shipment_recipient_for_association_recipient(
                    editing_recipient
                )
                recipient_shared_fields_read_only = _recipient_shared_fields_are_read_only(
                    recipient_organization
                )
                preference_edit_id = parse_int(request.GET.get("preference_edit"))
                if recipient_organization is not None and preference_edit_id is not None:
                    editing_product_preference = recipient_organization.product_preferences.filter(
                        pk=preference_edit_id
                    ).first()
                    if editing_product_preference is not None:
                        product_preference_form_data = (
                            _build_product_preference_form_data_from_instance(
                                editing_product_preference
                            )
                        )

    recipients = _decorate_recipient_validation_statuses(_get_active_recipients(profile))
    recipient_preference_rows = []
    recipient_organization = None
    if editing_recipient is not None:
        recipient_organization = _get_shipment_recipient_for_association_recipient(
            editing_recipient
        )
        recipient_preference_rows = _build_product_preference_rows(recipient_organization)
    return render(
        request,
        TEMPLATE_RECIPIENTS,
        {
            "recipients": recipients,
            "errors": errors,
            "form_data": form_data,
            "editing_recipient": editing_recipient,
            "destinations": destinations,
            "contact_title_choices": sorted_choices(AssociationContactTitle.choices),
            "legal_form_choices": legal_form_choices,
            "country_choices": build_country_choices(form_data.get("country")),
            "blocked_popup_message": blocked_popup_message,
            "duplicate_recipient_suggestions": duplicate_recipient_suggestions,
            "recipient_organization": recipient_organization,
            "recipient_shared_fields_read_only": recipient_shared_fields_read_only,
            "recipient_shared_read_only_message": ERROR_RECIPIENT_SHARED_READ_ONLY,
            "recipient_product_preferences": recipient_preference_rows,
            "product_preference_errors": product_preference_errors,
            "product_preference_form_data": product_preference_form_data,
            "editing_product_preference": editing_product_preference,
            "product_preference_scope_choices": sorted_choices(PRODUCT_PREFERENCE_SCOPE_CHOICES),
            "product_preference_status_choices": sorted_choices(
                [
                    (value, _product_preference_status_label(value))
                    for value, _label in RecipientProductPreferenceStatus.choices
                ]
            ),
            "product_preference_period_choices": sorted_choices(
                RecipientProductPreferencePeriodUnit.choices
            ),
            "product_choices": product_choices,
            "category_choices": category_choices,
        },
    )


def _get_bulk_preference_products(post_data):
    product_ids = []
    seen_product_ids = set()
    for raw_product_id in post_data.getlist("preference_product_ids"):
        product_id = parse_int(raw_product_id)
        if product_id is None or product_id in seen_product_ids:
            continue
        product_ids.append(product_id)
        seen_product_ids.add(product_id)

    if not product_ids:
        return [], []

    products_by_id = {
        product.id: product
        for product in Product.objects.filter(id__in=product_ids, is_active=True)
        .select_related("category")
        .order_by("name", "id")
    }
    products = [
        products_by_id[product_id] for product_id in product_ids if product_id in products_by_id
    ]
    if len(products) != len(product_ids):
        return products, [ERROR_RECIPIENT_PRODUCT_REQUIRED]
    return products, []


def _build_bulk_current_preference_form_data_by_product_id(*, recipient_organization, products):
    effective_preferences = list_effective_recipient_product_preferences(
        recipient_organization=recipient_organization,
        products=products,
    )
    return {
        effective_preference.product.pk: _build_preference_form_data_from_effective_preference(
            effective_preference
        )
        for effective_preference in effective_preferences
    }


def _validate_bulk_preference_model_payload(
    *,
    recipient_organization,
    form_data,
    existing_preference,
    user,
):
    if form_data["status"] == UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS:
        return []

    preference = existing_preference or RecipientProductPreference(
        recipient_organization=recipient_organization,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    preference.product = form_data["product"]
    preference.category = None
    preference.status = form_data["status"]
    preference.quantity_target = form_data.get("quantity_target_value")
    preference.period_unit = form_data["period_unit"]
    preference.notes = form_data["notes"]
    preference.source = RecipientProductPreferenceSource.PORTAL
    preference.updated_by = user if getattr(user, "is_authenticated", False) else None
    try:
        preference.full_clean()
    except ValidationError as error:
        return _flatten_validation_error_messages(error)
    return []


def _add_bulk_preference_row_errors(
    *,
    product_id,
    errors,
    preference_errors,
    preference_errors_by_product_id,
):
    if not errors:
        return
    preference_errors.extend(errors)
    preference_errors_by_product_id.setdefault(product_id, []).extend(errors)


def _handle_recipient_preferences_bulk_post(*, request, recipient_organization, success_url):
    preference_errors = []
    preference_form_data_by_product_id = {}
    preference_errors_by_product_id = {}
    products, product_errors = _get_bulk_preference_products(request.POST)
    if product_errors:
        preference_errors.extend(product_errors)
        return (
            None,
            preference_errors,
            preference_form_data_by_product_id,
            preference_errors_by_product_id,
        )

    if not products:
        messages.info(request, MESSAGE_RECIPIENT_PREFERENCES_BULK_NO_CHANGES)
        return (
            redirect(success_url),
            preference_errors,
            preference_form_data_by_product_id,
            preference_errors_by_product_id,
        )

    products_by_id = {product.id: product for product in products}
    current_form_data_by_product_id = _build_bulk_current_preference_form_data_by_product_id(
        recipient_organization=recipient_organization,
        products=products,
    )
    changed_form_data = []
    for product in products:
        form_data = _extract_bulk_preference_form_data(request.POST, product)
        current_form_data = current_form_data_by_product_id.get(
            product.id,
            {
                **_build_default_preference_form_data(),
                "product_id": str(product.id),
            },
        )
        if not _preference_form_data_has_changes(form_data, current_form_data):
            continue

        preference_form_data_by_product_id[product.id] = form_data
        row_errors = _prepare_preference_form_data(form_data, products_by_id)
        _add_bulk_preference_row_errors(
            product_id=product.id,
            errors=row_errors,
            preference_errors=preference_errors,
            preference_errors_by_product_id=preference_errors_by_product_id,
        )
        changed_form_data.append(form_data)

    if preference_errors:
        return (
            None,
            preference_errors,
            preference_form_data_by_product_id,
            preference_errors_by_product_id,
        )

    if not changed_form_data:
        messages.info(request, MESSAGE_RECIPIENT_PREFERENCES_BULK_NO_CHANGES)
        return (
            redirect(success_url),
            preference_errors,
            preference_form_data_by_product_id,
            preference_errors_by_product_id,
        )

    existing_preferences_by_product_id = {
        preference.product_id: preference
        for preference in RecipientProductPreference.objects.filter(
            recipient_organization=recipient_organization,
            product_id__in=[form_data["product"].id for form_data in changed_form_data],
        )
    }
    for form_data in changed_form_data:
        row_errors = _validate_bulk_preference_model_payload(
            recipient_organization=recipient_organization,
            form_data=form_data,
            existing_preference=existing_preferences_by_product_id.get(form_data["product"].id),
            user=request.user,
        )
        _add_bulk_preference_row_errors(
            product_id=form_data["product"].id,
            errors=row_errors,
            preference_errors=preference_errors,
            preference_errors_by_product_id=preference_errors_by_product_id,
        )

    if preference_errors:
        return (
            None,
            preference_errors,
            preference_form_data_by_product_id,
            preference_errors_by_product_id,
        )

    with transaction.atomic():
        for form_data in changed_form_data:
            product = form_data["product"]
            if form_data["status"] == UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS:
                existing_preference = existing_preferences_by_product_id.get(product.id)
                if existing_preference is not None:
                    existing_preference.delete()
                continue

            save_recipient_product_preference(
                recipient_organization=recipient_organization,
                product=product,
                status=form_data["status"],
                quantity_target=form_data.get("quantity_target_value"),
                period_unit=form_data["period_unit"],
                notes=form_data["notes"],
                source=RecipientProductPreferenceSource.PORTAL,
                user=request.user,
            )

    messages.success(request, MESSAGE_RECIPIENT_PREFERENCES_BULK_UPDATED)
    return (
        redirect(success_url),
        preference_errors,
        preference_form_data_by_product_id,
        preference_errors_by_product_id,
    )


def _handle_recipient_preference_post(
    *,
    request,
    recipient_organization,
    success_url,
    recipient_shared_fields_read_only=False,
):
    preference_errors = []
    preference_form_data_by_product_id = {}
    preference_errors_by_product_id = {}
    action = request.POST.get("action")
    if action not in {
        ACTION_SAVE_RECIPIENT_PREFERENCE,
        ACTION_SAVE_RECIPIENT_PREFERENCES_BULK,
        ACTION_DELETE_RECIPIENT_PREFERENCE,
    }:
        return (
            None,
            preference_errors,
            preference_form_data_by_product_id,
            preference_errors_by_product_id,
        )

    if recipient_organization is None:
        preference_errors.append(ERROR_RECIPIENT_RUNTIME_REQUIRED)
        return (
            None,
            preference_errors,
            preference_form_data_by_product_id,
            preference_errors_by_product_id,
        )

    if recipient_shared_fields_read_only:
        preference_errors.append(ERROR_RECIPIENT_SHARED_READ_ONLY)
        return (
            None,
            preference_errors,
            preference_form_data_by_product_id,
            preference_errors_by_product_id,
        )

    if action == ACTION_DELETE_RECIPIENT_PREFERENCE:
        preference_id = parse_int(request.POST.get("preference_id"))
        preference = (
            RecipientProductPreference.objects.filter(
                recipient_organization=recipient_organization,
                pk=preference_id,
            ).first()
            if preference_id is not None
            else None
        )
        if preference is None:
            preference_errors.append(ERROR_RECIPIENT_PREFERENCE_NOT_FOUND)
            return (
                None,
                preference_errors,
                preference_form_data_by_product_id,
                preference_errors_by_product_id,
            )
        preference.delete()
        messages.success(request, MESSAGE_RECIPIENT_PREFERENCE_DELETED)
        return (
            redirect(success_url),
            preference_errors,
            preference_form_data_by_product_id,
            preference_errors_by_product_id,
        )

    if action == ACTION_SAVE_RECIPIENT_PREFERENCES_BULK:
        return _handle_recipient_preferences_bulk_post(
            request=request,
            recipient_organization=recipient_organization,
            success_url=success_url,
        )

    products = list(Product.objects.filter(is_active=True).order_by("name", "id"))
    products_by_id = {product.id: product for product in products}
    form_data = _extract_preference_form_data(request.POST)
    preference_errors.extend(_prepare_preference_form_data(form_data, products_by_id))

    if preference_errors:
        product_id = parse_int(request.POST.get("product_id"))
        if product_id is not None:
            preference_form_data_by_product_id[product_id] = form_data
            preference_errors_by_product_id[product_id] = preference_errors
        return (
            None,
            preference_errors,
            preference_form_data_by_product_id,
            preference_errors_by_product_id,
        )

    preference = RecipientProductPreference.objects.filter(
        recipient_organization=recipient_organization,
        product=form_data["product"],
    ).first()
    if form_data["status"] == UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS:
        if preference is not None:
            preference.delete()
            messages.success(request, MESSAGE_RECIPIENT_PREFERENCE_DELETED)
        return (
            redirect(success_url),
            preference_errors,
            preference_form_data_by_product_id,
            preference_errors_by_product_id,
        )

    created = preference is None
    try:
        save_recipient_product_preference(
            recipient_organization=recipient_organization,
            product=form_data["product"],
            status=form_data["status"],
            quantity_target=form_data.get("quantity_target_value"),
            period_unit=form_data["period_unit"],
            notes=form_data["notes"],
            source=RecipientProductPreferenceSource.PORTAL,
            user=request.user,
        )
    except ValidationError as error:
        row_errors = _flatten_validation_error_messages(error)
        preference_errors.extend(row_errors)
        preference_form_data_by_product_id[form_data["product"].id] = form_data
        preference_errors_by_product_id[form_data["product"].id] = row_errors
        return (
            None,
            preference_errors,
            preference_form_data_by_product_id,
            preference_errors_by_product_id,
        )

    messages.success(
        request,
        MESSAGE_RECIPIENT_PREFERENCE_ADDED if created else MESSAGE_RECIPIENT_PREFERENCE_UPDATED,
    )
    return (
        redirect(success_url),
        preference_errors,
        preference_form_data_by_product_id,
        preference_errors_by_product_id,
    )


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_recipient_detail(request, recipient_id):
    profile = request.association_profile
    recipient = _get_portal_recipient_or_404(profile, recipient_id)
    recipient = _decorate_recipient_validation_statuses([recipient])[0]
    recipient_organization = _get_runtime_recipient_organization(recipient)
    recipient_shared_fields_read_only = _recipient_shared_fields_are_read_only(
        recipient_organization
    )
    filter_state = get_recipient_preference_filter_state(request)
    detail_url = reverse(
        "portal:portal_recipient_detail",
        kwargs={"recipient_id": recipient.id},
    )
    preference_errors = []
    preference_form_data_by_product_id = {}
    preference_errors_by_product_id = {}

    if request.method == "POST":
        (
            response,
            preference_errors,
            preference_form_data_by_product_id,
            preference_errors_by_product_id,
        ) = _handle_recipient_preference_post(
            request=request,
            recipient_organization=recipient_organization,
            success_url=build_recipient_preference_filter_url(
                detail_url,
                query=filter_state["query"],
                category_id=filter_state["category_id"],
                sort=filter_state["sort"],
            ),
            recipient_shared_fields_read_only=recipient_shared_fields_read_only,
        )
        if response is not None:
            return response

    return render(
        request,
        TEMPLATE_RECIPIENT_DETAIL,
        _build_recipient_detail_context(
            recipient=recipient,
            recipient_organization=recipient_organization,
            recipient_shared_fields_read_only=recipient_shared_fields_read_only,
            preference_errors=preference_errors,
            preference_form_data_by_product_id=preference_form_data_by_product_id,
            preference_errors_by_product_id=preference_errors_by_product_id,
            filter_state=filter_state,
            preference_filter_reset_url=detail_url,
        ),
    )


@login_required(login_url="portal:portal_login")
@portal_scope_required
@require_http_methods(["GET", "POST"])
def portal_recipient_preferences(request):
    scope = request.portal_scope
    if scope.role != PortalAccessRole.RECIPIENT_ADMIN or scope.recipient_organization is None:
        raise PermissionDenied

    recipient_organization = get_object_or_404(
        ShipmentRecipientOrganization.objects.select_related("organization", "destination"),
        pk=scope.recipient_organization.pk,
        is_active=True,
    )
    filter_state = get_recipient_preference_filter_state(request)
    preferences_url = reverse("portal:portal_recipient_preferences")
    preference_errors = []
    preference_form_data_by_product_id = {}
    preference_errors_by_product_id = {}

    if request.method == "POST":
        (
            response,
            preference_errors,
            preference_form_data_by_product_id,
            preference_errors_by_product_id,
        ) = _handle_recipient_preference_post(
            request=request,
            recipient_organization=recipient_organization,
            success_url=build_recipient_preference_filter_url(
                preferences_url,
                query=filter_state["query"],
                category_id=filter_state["category_id"],
                sort=filter_state["sort"],
            ),
        )
        if response is not None:
            return response

    return render(
        request,
        TEMPLATE_RECIPIENT_PREFERENCES,
        _build_recipient_preferences_context(
            recipient_organization=recipient_organization,
            preference_errors=preference_errors,
            preference_form_data_by_product_id=preference_form_data_by_product_id,
            preference_errors_by_product_id=preference_errors_by_product_id,
            filter_state=filter_state,
            preference_filter_reset_url=preferences_url,
        ),
    )


@login_required(login_url="portal:portal_login")
@portal_scope_required
@require_http_methods(["GET", "POST"])
def portal_recipient_profile(request):
    scope = request.portal_scope
    if scope.role != PortalAccessRole.RECIPIENT_ADMIN or scope.recipient_organization is None:
        raise PermissionDenied

    recipient_organization = get_object_or_404(
        ShipmentRecipientOrganization.objects.select_related("organization", "destination"),
        pk=scope.recipient_organization.pk,
        is_active=True,
    )
    errors = []
    form_data = _build_recipient_form_data_from_runtime(recipient_organization)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == ACTION_UPDATE_RECIPIENT_PROFILE:
            form_data = _extract_recipient_form_data(request.POST)
            errors = _validate_recipient_form_data(
                form_data,
                {recipient_organization.destination_id: recipient_organization.destination},
            )
            if form_data.get("destination") != recipient_organization.destination:
                errors.append(ERROR_RECIPIENT_DESTINATION_REQUIRED)
            errors.extend(_validate_recipient_uploaded_documents(request.FILES))
            if not errors:
                update_runtime_recipient_profile(
                    recipient_organization=recipient_organization,
                    structure_name=form_data["structure_name"],
                    contact_title=form_data["contact_title"],
                    contact_first_name=form_data["contact_first_name"],
                    contact_last_name=form_data["contact_last_name"],
                    email_values=form_data["email_values"],
                    phone_values=form_data["phone_values"],
                    address_line1=form_data["address_line1"],
                    address_line2=form_data["address_line2"],
                    postal_code=form_data["postal_code"],
                    city=form_data["city"],
                    country=form_data["country"] or DEFAULT_COUNTRY,
                    legal_form=form_data["legal_form"],
                    beneficiary_count=form_data.get("beneficiary_count_value"),
                    notes=form_data["notes"],
                    notify_deliveries=form_data["notify_deliveries"],
                    is_delivery_contact=form_data["is_delivery_contact"],
                    uploaded_by=request.user,
                    files_by_type={
                        doc_type: request.FILES.get(field_name)
                        for doc_type, field_name in RECIPIENT_STRUCTURE_UPLOAD_FIELDS.items()
                    },
                )
                messages.success(request, MESSAGE_RECIPIENT_UPDATED)
                return redirect("portal:portal_recipient_profile")

    return render(
        request,
        TEMPLATE_RECIPIENT_PROFILE,
        _build_recipient_profile_context(
            recipient_organization=recipient_organization,
            errors=errors,
            form_data=form_data,
        ),
    )


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_account(request):
    profile = request.association_profile
    association = profile.contact
    address = get_contact_address(association)
    account_form_errors = []
    profile_form_data = _build_profile_form_data(association=association, address=address)
    portal_contact_rows = _build_contact_rows(profile)

    if request.method == "POST":
        action = request.POST.get("action") or ""
        if action == ACTION_UPDATE_PROFILE:
            profile_form_data = _extract_profile_form_data(request.POST)
            portal_contact_rows, contact_errors = _extract_contact_rows(request.POST)
            account_form_errors = _validate_profile_form_data(profile_form_data)
            account_form_errors.extend(contact_errors)
            if not account_form_errors:
                save_portal_account_profile(
                    user=request.user,
                    profile=profile,
                    form_data=profile_form_data,
                    contact_rows=portal_contact_rows,
                )
                messages.success(request, MESSAGE_PROFILE_UPDATED)
                return redirect("portal:portal_account")
        elif action == ACTION_UPDATE_NOTIFICATIONS:
            messages.error(request, MESSAGE_UPDATE_NOTIFICATIONS_DEPRECATED)
            return redirect("portal:portal_account")
        elif action == ACTION_UPLOAD_ACCOUNT_DOCS:
            return _handle_account_document_uploads(request, association)
        elif action == ACTION_UPLOAD_ACCOUNT_DOC:
            return _handle_account_document_upload(request, association)
        elif action == ACTION_REQUEST_BILLING_PREFERENCES:
            requested_frequency = (request.POST.get("billing_frequency") or "").strip()
            requested_grouping_mode = (request.POST.get("billing_grouping_mode") or "").strip()
            valid_frequencies = {choice for choice, _label in AssociationBillingFrequency.choices}
            valid_grouping_modes = {
                choice for choice, _label in AssociationBillingGroupingMode.choices
            }
            if (
                requested_frequency not in valid_frequencies
                or requested_grouping_mode not in valid_grouping_modes
            ):
                account_form_errors.append(ERROR_BILLING_PREFERENCES_INVALID)
            else:
                AssociationBillingChangeRequest.objects.create(
                    association_profile=profile,
                    requested_frequency=requested_frequency,
                    requested_grouping_mode=requested_grouping_mode,
                    requested_by=request.user,
                )
                messages.success(request, MESSAGE_BILLING_PREFERENCES_REQUESTED)
                return redirect("portal:portal_account")

    return render(
        request,
        TEMPLATE_ACCOUNT,
        _build_portal_account_context(
            profile=profile,
            address=address,
            user=request.user,
            account_form_errors=account_form_errors,
            profile_form_data=profile_form_data,
            portal_contact_rows=portal_contact_rows,
        ),
    )


@require_http_methods(["GET", "POST"])
def portal_account_request(request):
    return handle_account_request_form(
        request,
        link=None,
        redirect_url=reverse("portal:portal_account_request"),
        allow_user_request=True,
        show_user_account_type=False,
    )
