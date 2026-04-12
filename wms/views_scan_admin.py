from types import SimpleNamespace
from urllib.parse import urlencode

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from contacts.models import Contact, ContactType

from .admin_contacts_crud import (
    ACTION_DEACTIVATE_CONTACT,
    ACTION_MERGE_CONTACT,
    ACTION_SAVE_CONTACT,
    ACTION_SAVE_DESTINATION,
    build_admin_contacts_forms,
    handle_contact_deactivation,
    handle_contact_merge,
    handle_contact_submission,
    handle_destination_submission,
)
from .application.parties.use_cases import save_recipient_product_preference
from .forms_scan_admin_carton_formats import CartonFormatCrudForm
from .kit_components import KitCycleError, get_unit_component_quantities
from .models import (
    CartonFormat,
    Destination,
    PortalAccessGrant,
    Product,
    RecipientProductPreference,
    RecipientProductPreferencePeriodUnit,
    RecipientProductPreferenceSource,
    RecipientProductPreferenceStatus,
    RecipientStructureDocument,
    ShipmentRecipientOrganization,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from .product_label_printing import (
    render_product_labels_response,
    render_product_qr_labels_response,
)
from .recipient_preference_view_helpers import (
    build_recipient_preference_catalog_context,
    build_recipient_preference_filter_url,
    get_recipient_preference_filter_state,
)
from .recipient_product_preferences import (
    UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS,
)
from .scan_admin_contacts_cockpit import (
    ACTION_MERGE_SHIPMENT_RECIPIENT_ORGANIZATIONS,
    ACTION_SET_DEFAULT_AUTHORIZED_RECIPIENT_CONTACT,
    ACTION_SET_STOPOVER_CORRESPONDENT_RECIPIENT_ORGANIZATION,
    build_cockpit_context,
    merge_shipment_recipient_organizations,
    parse_cockpit_filters,
    set_default_authorized_recipient_contact,
    set_stopover_correspondent_recipient_organization,
)
from .view_permissions import require_superuser as _require_superuser
from .view_permissions import scan_staff_required


def _select_scan_copy(*, french, english):
    return english if (get_language() or "").startswith("en") else french


TEMPLATE_SCAN_ADMIN_CONTACTS = "scan/admin_contacts.html"
TEMPLATE_SCAN_CONTACT_ROLES = "scan/contact_roles.html"
TEMPLATE_SCAN_ADMIN_RECIPIENT_ORGANIZATION_DETAIL = "scan/admin_recipient_organization_detail.html"
TEMPLATE_SCAN_ADMIN_CARTON_FORMATS = "scan/admin_carton_formats.html"
TEMPLATE_SCAN_ADMIN_PRODUCTS = "scan/admin_products.html"
TEMPLATE_SCAN_PRODUCT_LABELS = "scan/admin_product_labels.html"
ACTIVE_SCAN_ADMIN_CONTACTS = "admin_contacts"
ACTIVE_SCAN_CONTACT_ROLES = "contacts_roles"
ACTIVE_SCAN_ADMIN_CARTON_FORMATS = "admin_carton_formats"
ACTIVE_SCAN_ADMIN_PRODUCTS = "admin_products"
ACTIVE_SCAN_PRODUCT_LABELS = "product_labels"
ACTION_SAVE_CARTON_FORMAT = "save_carton_format"
ACTION_SAVE_RECIPIENT_PREFERENCE = "save_recipient_preference"
ACTION_CREATE_RECIPIENT_PREFERENCE = "create_recipient_preference"
ACTION_UPDATE_RECIPIENT_PREFERENCE = "update_recipient_preference"
ACTION_DELETE_RECIPIENT_PREFERENCE = "delete_recipient_preference"
MESSAGE_RECIPIENT_PREFERENCE_ADDED = _("Préférence produit ajoutée.")
MESSAGE_RECIPIENT_PREFERENCE_UPDATED = _("Préférence produit modifiée.")
MESSAGE_RECIPIENT_PREFERENCE_DELETED = _("Préférence produit supprimée.")
ERROR_RECIPIENT_PRODUCT_REQUIRED = _("Produit requis.")
ERROR_RECIPIENT_PRODUCT_QUANTITY_INVALID = _("Quantite cible invalide.")
ERROR_RECIPIENT_PRODUCT_STATUS_INVALID = _("Statut produit invalide.")
ERROR_RECIPIENT_PRODUCT_PERIOD_INVALID = _("Periode invalide.")
ERROR_RECIPIENT_PREFERENCE_NOT_FOUND = _("Préférence produit introuvable.")

CONTACT_FILTER_ALL = "all"
CONTACT_FILTER_CHOICES = (
    (CONTACT_FILTER_ALL, "Tous"),
    (ContactType.ORGANIZATION, "Organisation"),
    (ContactType.PERSON, "Personne"),
)
CONTACT_FILTER_VALUES = {choice[0] for choice in CONTACT_FILTER_CHOICES}
ADMIN_CONTACTS_PAGE_SIZE = 100

PRODUCT_SELECTION_MODE_SELECTION = "selection"
PRODUCT_SELECTION_MODE_ALL_FILTERED = "all_filtered"
PRODUCT_SELECTION_MODE_VALUES = {
    PRODUCT_SELECTION_MODE_SELECTION,
    PRODUCT_SELECTION_MODE_ALL_FILTERED,
}


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_default_recipient_preference_form_data():
    return {
        "product_id": "",
        "status": UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS,
        "quantity_target": "",
        "period_unit": "",
        "notes": "",
    }


def _extract_recipient_preference_form_data(post_data):
    return {
        "product_id": (post_data.get("product_id") or "").strip(),
        "status": (post_data.get("status") or "").strip(),
        "quantity_target": (post_data.get("quantity_target") or "").strip(),
        "period_unit": (post_data.get("period_unit") or "").strip(),
        "notes": (post_data.get("notes") or "").strip(),
    }


def _build_recipient_preference_form_data_from_instance(preference):
    return {
        "product_id": str(preference.product_id),
        "status": preference.status,
        "quantity_target": str(preference.quantity_target or ""),
        "period_unit": preference.period_unit or "",
        "notes": preference.notes or "",
    }


def _build_recipient_preference_form_data_from_effective_preference(effective_preference):
    if effective_preference.preference is not None:
        return _build_recipient_preference_form_data_from_instance(effective_preference.preference)
    return {
        "product_id": str(effective_preference.product.pk),
        "status": UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS,
        "quantity_target": "",
        "period_unit": "",
        "notes": "",
    }


def _prepare_recipient_preference_form_data(form_data, products_by_id):
    errors = []
    product = products_by_id.get(_parse_int(form_data["product_id"]))
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
        quantity_target = _parse_int(quantity_raw)
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
    if getattr(error, "message_dict", None):
        flattened = []
        for values in error.message_dict.values():
            flattened.extend(str(value) for value in values)
        return flattened
    return [str(value) for value in getattr(error, "messages", [])]


def _apply_contact_query(queryset, query):
    if not query:
        return queryset
    return queryset.filter(
        Q(name__icontains=query)
        | Q(asf_id__icontains=query)
        | Q(email__icontains=query)
        | Q(phone__icontains=query)
    )


def _normalize_contact_filter(raw_value):
    value = (raw_value or CONTACT_FILTER_ALL).strip().lower()
    if value in CONTACT_FILTER_VALUES:
        return value
    return CONTACT_FILTER_ALL


def _apply_contact_filter(queryset, contact_filter):
    if contact_filter == CONTACT_FILTER_ALL:
        return queryset
    return queryset.filter(contact_type=contact_filter)


def _normalize_destination_filter(raw_value):
    value = (raw_value or "").strip()
    if not value or not value.isdigit():
        return ""
    if not Destination.objects.filter(pk=value, is_active=True).exists():
        return ""
    return value


def _build_contacts_redirect(
    *, query, contact_filter, destination_filter="", edit_id=None, page=None
):
    return redirect(
        _build_contacts_url(
            query=query,
            contact_filter=contact_filter,
            destination_filter=destination_filter,
            edit_id=edit_id,
            page=page,
        )
    )


def _build_contacts_url(*, query, contact_filter, destination_filter="", edit_id=None, page=None):
    params = {}
    if query:
        params["q"] = query
    if contact_filter != CONTACT_FILTER_ALL:
        params["contact_type"] = contact_filter
    if destination_filter:
        params["destination_id"] = destination_filter
    if edit_id:
        params["edit"] = str(edit_id)
    resolved_page = _parse_int(page)
    if resolved_page and resolved_page > 1:
        params["page"] = str(resolved_page)
    url = reverse("scan:scan_admin_contacts")
    if params:
        url = f"{url}?{urlencode(params)}"
    return url


def _build_contacts_roles_url(*, destination_filter=""):
    params = {}
    if destination_filter:
        params["destination_id"] = destination_filter
    url = reverse("scan:scan_contacts_roles")
    if params:
        url = f"{url}?{urlencode(params)}"
    return url


def _safe_registered_admin_url(*, model, viewname):
    if model not in admin.site._registry:
        return ""
    try:
        return reverse(viewname)
    except NoReverseMatch:
        return ""


def _build_recipient_organization_detail_url(
    *,
    recipient_organization_id,
    query="",
    contact_filter=CONTACT_FILTER_ALL,
    destination_filter="",
):
    url = reverse(
        "scan:scan_admin_recipient_organization_detail",
        kwargs={"recipient_organization_id": recipient_organization_id},
    )
    params = {}
    if query:
        params["q"] = query
    if contact_filter != CONTACT_FILTER_ALL:
        params["contact_type"] = contact_filter
    if destination_filter:
        params["destination_id"] = destination_filter
    if params:
        url = f"{url}?{urlencode(params)}"
    return url


def _build_pending_recipient_validations(*, query, contact_filter, destination_filter, page=None):
    pending_recipient_validations = (
        ShipmentRecipientOrganization.objects.filter(
            validation_status=ShipmentValidationStatus.PENDING,
            is_active=True,
            organization__is_active=True,
        )
        .select_related("organization", "destination")
        .prefetch_related(
            Prefetch(
                "shipper_links",
                queryset=ShipmentShipperRecipientLink.objects.filter(
                    is_active=True,
                    shipper__is_active=True,
                    shipper__organization__is_active=True,
                )
                .select_related("shipper__organization")
                .order_by("shipper__organization__name", "id"),
                to_attr="active_shipper_links",
            )
        )
        .order_by("destination__city", "organization__name", "id")
    )
    rows = []
    for recipient_validation in pending_recipient_validations:
        rows.append(
            {
                "organization": recipient_validation.organization,
                "destination": recipient_validation.destination,
                "allowed_shipper_names": [
                    link.shipper.organization.name
                    for link in recipient_validation.active_shipper_links
                ],
                "verify_url": _build_contacts_url(
                    query=query,
                    contact_filter=contact_filter,
                    destination_filter=destination_filter,
                    edit_id=recipient_validation.organization_id,
                    page=page,
                ),
            }
        )
    return rows


def _editing_contact_requires_recipient_validation(contact):
    if contact is None or contact.contact_type != ContactType.ORGANIZATION:
        return False
    return ShipmentRecipientOrganization.objects.filter(
        organization=contact,
        validation_status=ShipmentValidationStatus.PENDING,
        is_active=True,
    ).exists()


def _apply_product_query(queryset, query):
    if not query:
        return queryset
    return queryset.filter(
        Q(name__icontains=query)
        | Q(sku__icontains=query)
        | Q(barcode__icontains=query)
        | Q(ean__icontains=query)
    )


def _build_product_labels_queryset(query):
    queryset = Product.objects.filter(is_active=True).order_by("name", "id")
    return _apply_product_query(queryset, query)


def _normalize_product_selection_mode(raw_value):
    value = (raw_value or PRODUCT_SELECTION_MODE_SELECTION).strip().lower()
    if value in PRODUCT_SELECTION_MODE_VALUES:
        return value
    return PRODUCT_SELECTION_MODE_SELECTION


def _build_product_labels_redirect(*, query, selection_mode):
    params = {}
    if query:
        params["q"] = query
    if selection_mode != PRODUCT_SELECTION_MODE_SELECTION:
        params["selection_mode"] = selection_mode
    url = reverse("scan:scan_product_labels")
    if params:
        url = f"{url}?{urlencode(params)}"
    return redirect(url)


def _resolve_product_labels_selection(request):
    query = (request.POST.get("q") or "").strip()
    selection_mode = _normalize_product_selection_mode(request.POST.get("selection_mode"))
    queryset = _build_product_labels_queryset(query)
    if selection_mode == PRODUCT_SELECTION_MODE_ALL_FILTERED:
        return list(queryset), query, selection_mode

    product_ids = []
    for raw_value in request.POST.getlist("product_ids"):
        value = (raw_value or "").strip()
        if value.isdigit():
            product_ids.append(int(value))
    if not product_ids:
        return [], query, selection_mode
    return list(queryset.filter(pk__in=product_ids)), query, selection_mode


def _build_admin_recipient_preference_context(
    *,
    recipient_organization,
    query,
    contact_filter,
    destination_filter,
    preference_errors=None,
    preference_form_data_by_product_id=None,
    filter_state=None,
    preference_filter_reset_url="",
):
    catalog_context = build_recipient_preference_catalog_context(
        recipient_organization=recipient_organization,
        filter_state=filter_state or {},
        build_form_data=_build_recipient_preference_form_data_from_effective_preference,
        preference_form_data_by_product_id=preference_form_data_by_product_id,
    )
    return {
        "active": ACTIVE_SCAN_CONTACT_ROLES,
        "query": query,
        "contact_filter": contact_filter,
        "destination_filter": destination_filter,
        "recipient_organization": recipient_organization,
        "preference_errors": preference_errors or [],
        "back_url": _build_contacts_roles_url(destination_filter=destination_filter),
        "preference_filter_reset_url": preference_filter_reset_url,
        "preference_filter_hidden_fields": [
            {"name": "q", "value": query},
            {"name": "contact_type", "value": contact_filter},
            {"name": "destination_id", "value": destination_filter},
        ],
        **catalog_context,
    }


def _build_contacts_editing_structure_context(editing_contact):
    editing_structure_contact = None
    editing_structure_documents = []
    if editing_contact is not None:
        if editing_contact.contact_type == ContactType.PERSON and editing_contact.organization_id:
            editing_structure_contact = editing_contact.organization
        elif editing_contact.contact_type == ContactType.ORGANIZATION:
            editing_structure_contact = editing_contact
        if editing_structure_contact is not None:
            editing_structure_documents = list(
                editing_structure_contact.recipient_structure_documents.order_by("-uploaded_at")
            )
    return editing_structure_contact, editing_structure_documents


def _build_contacts_directory_context(*, query, contact_filter, destination_filter, page):
    base_contacts_qs = _apply_contact_filter(
        Contact.objects.select_related("organization").order_by("name", "id"),
        contact_filter,
    )
    contacts_qs = _apply_contact_query(base_contacts_qs, query)
    contacts_paginator = Paginator(contacts_qs, ADMIN_CONTACTS_PAGE_SIZE)
    contacts_page = contacts_paginator.get_page(page)
    contacts = list(contacts_page.object_list)

    correspondents = _apply_contact_filter(
        Contact.objects.filter(
            is_active=True,
            destinations_as_correspondent__is_active=True,
        )
        .select_related("organization")
        .prefetch_related(
            Prefetch(
                "destinations_as_correspondent",
                queryset=Destination.objects.filter(is_active=True).order_by(
                    "city", "iata_code", "id"
                ),
            )
        )
        .distinct()
        .order_by("name", "id"),
        contact_filter,
    )
    if destination_filter:
        correspondents = correspondents.filter(destinations_as_correspondent__id=destination_filter)
    correspondents = _apply_contact_query(correspondents, query)
    current_contacts_url = _build_contacts_url(
        query=query,
        contact_filter=contact_filter,
        destination_filter=destination_filter,
        page=contacts_page.number,
    )
    return {
        "query": query,
        "contact_filter": contact_filter,
        "destination_filter": destination_filter,
        "contact_filter_choices": CONTACT_FILTER_CHOICES,
        "destination_filter_choices": list(
            Destination.objects.filter(is_active=True).order_by("city", "iata_code", "id")
        ),
        "contacts": list(contacts_page.object_list),
        "contacts_page": contacts_page,
        "contacts_total_count": contacts_paginator.count,
        "contacts_page_prev_url": (
            _build_contacts_url(
                query=query,
                contact_filter=contact_filter,
                destination_filter=destination_filter,
                page=contacts_page.previous_page_number(),
            )
            if contacts_page.has_previous()
            else ""
        ),
        "contacts_page_next_url": (
            _build_contacts_url(
                query=query,
                contact_filter=contact_filter,
                destination_filter=destination_filter,
                page=contacts_page.next_page_number(),
            )
            if contacts_page.has_next()
            else ""
        ),
        "contacts_current_url": current_contacts_url,
        "correspondents": correspondents,
        "contacts_admin_url": reverse("admin:contacts_contact_changelist"),
        "contact_add_url": reverse("admin:contacts_contact_add"),
        "destination_admin_url": reverse("admin:wms_destination_changelist"),
        "destination_add_url": reverse("admin:wms_destination_add"),
        "portal_access_admin_url": _safe_registered_admin_url(
            model=PortalAccessGrant,
            viewname="admin:wms_portalaccessgrant_changelist",
        ),
        "recipient_organization_admin_url": _safe_registered_admin_url(
            model=ShipmentRecipientOrganization,
            viewname="admin:wms_shipmentrecipientorganization_changelist",
        ),
        "recipient_product_preference_admin_url": _safe_registered_admin_url(
            model=RecipientProductPreference,
            viewname="admin:wms_recipientproductpreference_changelist",
        ),
        "recipient_structure_document_admin_url": _safe_registered_admin_url(
            model=RecipientStructureDocument,
            viewname="admin:wms_recipientstructuredocument_changelist",
        ),
        "contact_action_merge_targets": list(contacts_page.object_list),
    }


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_admin_contacts(request):
    _require_superuser(request)
    query = (request.GET.get("q") or request.POST.get("q") or "").strip()
    edit_contact_id = (request.GET.get("edit") or "").strip()
    page = (request.GET.get("page") or request.POST.get("page") or "").strip()
    destination_filter = _normalize_destination_filter(
        request.GET.get("destination_id") or request.POST.get("destination_id")
    )
    contact_filter = _normalize_contact_filter(
        request.GET.get("contact_type") or request.POST.get("contact_type")
    )

    crud_context = build_admin_contacts_forms(edit_contact_id=edit_contact_id)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == ACTION_SAVE_DESTINATION:
            outcome = handle_destination_submission(request.POST)
            if outcome.should_redirect:
                getattr(messages, outcome.message_level or "success")(
                    request, outcome.message or ""
                )
                return _build_contacts_redirect(
                    query=query,
                    contact_filter=contact_filter,
                    destination_filter=destination_filter,
                    page=page,
                )
            crud_context.update(
                {
                    "destination_form": outcome.destination_form
                    or crud_context["destination_form"],
                    "destination_duplicate_candidates": outcome.destination_duplicate_candidates,
                }
            )
        elif action == ACTION_SAVE_CONTACT:
            outcome = handle_contact_submission(request.POST)
            if outcome.should_redirect:
                getattr(messages, outcome.message_level or "success")(
                    request, outcome.message or ""
                )
                return _build_contacts_redirect(
                    query=query,
                    contact_filter=contact_filter,
                    destination_filter=destination_filter,
                    page=page,
                )
            crud_context.update(
                {
                    "contact_form": outcome.contact_form or crud_context["contact_form"],
                    "contact_duplicate_candidates": outcome.contact_duplicate_candidates,
                    "contact_form_mode": outcome.contact_form_mode,
                    "editing_contact": outcome.editing_contact,
                }
            )
        elif action == ACTION_DEACTIVATE_CONTACT:
            outcome = handle_contact_deactivation(request.POST)
            getattr(messages, outcome.message_level or "success")(request, outcome.message or "")
            return _build_contacts_redirect(
                query=query,
                contact_filter=contact_filter,
                destination_filter=destination_filter,
                page=page,
            )
        elif action == ACTION_MERGE_CONTACT:
            outcome = handle_contact_merge(request.POST)
            getattr(messages, outcome.message_level or "success")(request, outcome.message or "")
            return _build_contacts_redirect(
                query=query,
                contact_filter=contact_filter,
                destination_filter=destination_filter,
                page=page,
            )
        else:
            messages.error(request, _("Action de contact non reconnue."))

    editing_structure_contact, editing_structure_documents = (
        _build_contacts_editing_structure_context(crud_context.get("editing_contact"))
    )
    editing_contact_requires_recipient_validation = _editing_contact_requires_recipient_validation(
        crud_context.get("editing_contact")
    )
    directory_context = _build_contacts_directory_context(
        query=query,
        contact_filter=contact_filter,
        destination_filter=destination_filter,
        page=page,
    )

    return render(
        request,
        TEMPLATE_SCAN_ADMIN_CONTACTS,
        {
            "active": ACTIVE_SCAN_ADMIN_CONTACTS,
            "editing_contact_requires_recipient_validation": (
                editing_contact_requires_recipient_validation
            ),
            "destination_form_open": bool(
                crud_context["destination_form"].is_bound
                or crud_context["destination_duplicate_candidates"]
            ),
            "contact_form_open": bool(
                crud_context["contact_form"].is_bound
                or crud_context["contact_form_mode"] == "edit"
                or crud_context["contact_duplicate_candidates"]
            ),
            "editing_structure_contact": editing_structure_contact,
            "editing_structure_documents": editing_structure_documents,
            **directory_context,
            **crud_context,
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_contacts_roles(request):
    _require_superuser(request)
    destination_filter = _normalize_destination_filter(
        request.GET.get("destination_id") or request.POST.get("destination_id")
    )
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == ACTION_SET_DEFAULT_AUTHORIZED_RECIPIENT_CONTACT:
            ok, message = set_default_authorized_recipient_contact(data=request.POST)
        elif action == ACTION_SET_STOPOVER_CORRESPONDENT_RECIPIENT_ORGANIZATION:
            ok, message = set_stopover_correspondent_recipient_organization(data=request.POST)
        elif action == ACTION_MERGE_SHIPMENT_RECIPIENT_ORGANIZATIONS:
            ok, message = merge_shipment_recipient_organizations(data=request.POST)
        else:
            ok, message = False, _("Action de role expédition non reconnue.")
        getattr(messages, "success" if ok else "error")(request, message)
        return redirect(_build_contacts_roles_url(destination_filter=destination_filter))

    return render(
        request,
        TEMPLATE_SCAN_CONTACT_ROLES,
        {
            "active": ACTIVE_SCAN_CONTACT_ROLES,
            "destination_filter": destination_filter,
            "destination_filter_choices": list(
                Destination.objects.filter(is_active=True).order_by("city", "iata_code", "id")
            ),
            "query": "",
            "contact_filter": CONTACT_FILTER_ALL,
            "contacts_page": SimpleNamespace(number=1),
            **build_cockpit_context(
                query="",
                filters=parse_cockpit_filters(),
                destination_id=destination_filter,
            ),
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_admin_recipient_organization_detail(request, recipient_organization_id):
    _require_superuser(request)
    query = (request.GET.get("q") or request.POST.get("q") or "").strip()
    contact_filter = _normalize_contact_filter(
        request.GET.get("contact_type") or request.POST.get("contact_type")
    )
    destination_filter = _normalize_destination_filter(
        request.GET.get("destination_id") or request.POST.get("destination_id")
    )
    recipient_organization = get_object_or_404(
        ShipmentRecipientOrganization.objects.select_related("organization", "destination"),
        pk=recipient_organization_id,
        is_active=True,
        organization__is_active=True,
        destination__is_active=True,
    )
    filter_state = get_recipient_preference_filter_state(request)
    detail_url = _build_recipient_organization_detail_url(
        recipient_organization_id=recipient_organization.id,
        query=query,
        contact_filter=contact_filter,
        destination_filter=destination_filter,
    )
    preference_errors = []
    preference_form_data_by_product_id = {}

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == ACTION_SAVE_RECIPIENT_PREFERENCE:
            products = list(Product.objects.filter(is_active=True).order_by("name", "id"))
            products_by_id = {product.id: product for product in products}
            form_data = _extract_recipient_preference_form_data(request.POST)
            preference_errors.extend(
                _prepare_recipient_preference_form_data(form_data, products_by_id)
            )

            if preference_errors:
                product_id = _parse_int(request.POST.get("product_id"))
                if product_id is not None:
                    preference_form_data_by_product_id[product_id] = form_data
            else:
                preference = RecipientProductPreference.objects.filter(
                    recipient_organization=recipient_organization,
                    product=form_data["product"],
                ).first()
                if form_data["status"] == UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS:
                    if preference is not None:
                        preference.delete()
                        messages.success(request, MESSAGE_RECIPIENT_PREFERENCE_DELETED)
                    return redirect(
                        build_recipient_preference_filter_url(
                            detail_url,
                            query=filter_state["query"],
                            category_id=filter_state["category_id"],
                            sort=filter_state["sort"],
                        )
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
                        source=RecipientProductPreferenceSource.SCAN_ADMIN,
                        user=request.user,
                    )
                except ValidationError as error:
                    preference_errors.extend(_flatten_validation_error_messages(error))
                    preference_form_data_by_product_id[form_data["product"].id] = form_data
                else:
                    messages.success(
                        request,
                        (
                            MESSAGE_RECIPIENT_PREFERENCE_ADDED
                            if created
                            else MESSAGE_RECIPIENT_PREFERENCE_UPDATED
                        ),
                    )
                    return redirect(
                        build_recipient_preference_filter_url(
                            detail_url,
                            query=filter_state["query"],
                            category_id=filter_state["category_id"],
                            sort=filter_state["sort"],
                        )
                    )
        else:
            messages.error(request, _("Action de préférence destinataire non reconnue."))

    return render(
        request,
        TEMPLATE_SCAN_ADMIN_RECIPIENT_ORGANIZATION_DETAIL,
        _build_admin_recipient_preference_context(
            recipient_organization=recipient_organization,
            query=query,
            contact_filter=contact_filter,
            destination_filter=destination_filter,
            preference_errors=preference_errors,
            preference_form_data_by_product_id=preference_form_data_by_product_id,
            filter_state=filter_state,
            preference_filter_reset_url=detail_url,
        ),
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_admin_products(request):
    _require_superuser(request)
    query = (request.GET.get("q") or "").strip()
    kits_qs = (
        Product.objects.filter(is_active=True, kit_items__isnull=False)
        .prefetch_related("kit_items__component")
        .distinct()
        .order_by("name", "id")
    )
    if query:
        kits_qs = kits_qs.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(barcode__icontains=query)
            | Q(ean__icontains=query)
        )
    kits = list(kits_qs)
    flattened_by_kit = {}
    flattened_component_ids = set()
    kit_cycle_ids = set()
    for kit in kits:
        try:
            flattened_quantities = get_unit_component_quantities(kit)
        except KitCycleError:
            flattened_quantities = {}
            kit_cycle_ids.add(kit.id)
        flattened_by_kit[kit.id] = flattened_quantities
        flattened_component_ids.update(flattened_quantities.keys())

    component_name_by_id = dict(
        Product.objects.filter(id__in=flattened_component_ids).values_list("id", "name")
    )
    kit_rows = []
    for kit in kits:
        direct_lines = [
            f"{item.component.name} - {item.quantity} unite(s)"
            for item in sorted(
                kit.kit_items.all(),
                key=lambda current: ((current.component.name or "").lower(), current.component_id),
            )
            if item.quantity > 0
        ]
        flattened_quantities = flattened_by_kit.get(kit.id, {})
        flattened_lines = [
            f"{component_name_by_id.get(component_id, '-')} - {quantity} unite(s)"
            for component_id, quantity in sorted(
                flattened_quantities.items(),
                key=lambda pair: ((component_name_by_id.get(pair[0]) or "").lower(), pair[0]),
            )
            if quantity > 0
        ]
        kit_rows.append(
            {
                "kit": kit,
                "direct_lines": direct_lines,
                "flattened_lines": flattened_lines,
                "has_cycle": kit.id in kit_cycle_ids,
                "edit_url": reverse("admin:wms_product_change", args=[kit.id]),
                "delete_url": reverse("admin:wms_product_delete", args=[kit.id]),
            }
        )
    return render(
        request,
        TEMPLATE_SCAN_ADMIN_PRODUCTS,
        {
            "active": ACTIVE_SCAN_ADMIN_PRODUCTS,
            "query": query,
            "kit_rows": kit_rows,
            "products_admin_url": reverse("admin:wms_product_changelist"),
            "product_add_url": reverse("admin:wms_product_add"),
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_admin_carton_formats(request):
    _require_superuser(request)
    form = CartonFormatCrudForm(request.POST or None)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == ACTION_SAVE_CARTON_FORMAT:
            if form.is_valid():
                form.save()
                messages.success(request, _("Format carton enregistré."))
                return redirect("scan:scan_admin_carton_formats")
        else:
            messages.error(request, _("Action de format carton non reconnue."))

    return render(
        request,
        TEMPLATE_SCAN_ADMIN_CARTON_FORMATS,
        {
            "active": ACTIVE_SCAN_ADMIN_CARTON_FORMATS,
            "form": form,
            "carton_formats": list(CartonFormat.objects.all().order_by("name", "id")),
        },
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_product_labels(request):
    _require_superuser(request)
    query = (request.GET.get("q") or "").strip()
    selection_mode = _normalize_product_selection_mode(request.GET.get("selection_mode"))
    products = list(_build_product_labels_queryset(query))
    return render(
        request,
        TEMPLATE_SCAN_PRODUCT_LABELS,
        {
            "active": ACTIVE_SCAN_PRODUCT_LABELS,
            "query": query,
            "selection_mode": selection_mode,
            "products": products,
            "selection_mode_selection": PRODUCT_SELECTION_MODE_SELECTION,
            "selection_mode_all_filtered": PRODUCT_SELECTION_MODE_ALL_FILTERED,
            "products_admin_url": reverse("admin:wms_product_changelist"),
            "print_templates_url": reverse("scan:scan_print_templates"),
            "product_label_template_url": reverse(
                "scan:scan_print_template_edit",
                args=["product_label"],
            ),
            "product_qr_template_url": reverse(
                "scan:scan_print_template_edit",
                args=["product_qr"],
            ),
            "print_labels_url": reverse("scan:scan_product_labels_print_labels"),
            "print_qr_url": reverse("scan:scan_product_labels_print_qr"),
        },
    )


@scan_staff_required
@require_http_methods(["POST"])
def scan_product_labels_print_labels(request):
    _require_superuser(request)
    products, query, selection_mode = _resolve_product_labels_selection(request)
    if not products:
        messages.warning(
            request,
            _select_scan_copy(
                french="Aucun produit sélectionné.",
                english="No product selected.",
            ),
        )
        return _build_product_labels_redirect(query=query, selection_mode=selection_mode)
    return render_product_labels_response(request, products)


@scan_staff_required
@require_http_methods(["POST"])
def scan_product_labels_print_qr(request):
    _require_superuser(request)
    products, query, selection_mode = _resolve_product_labels_selection(request)
    if not products:
        messages.warning(
            request,
            _select_scan_copy(
                french="Aucun produit sélectionné.",
                english="No product selected.",
            ),
        )
        return _build_product_labels_redirect(query=query, selection_mode=selection_mode)
    return render_product_qr_labels_response(request, products)
