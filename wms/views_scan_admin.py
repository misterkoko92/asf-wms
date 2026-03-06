from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from contacts.models import Contact, ContactType
from contacts.querysets import contacts_with_tags
from contacts.tagging import TAG_CORRESPONDENT

from .kit_components import KitCycleError, get_unit_component_quantities
from .models import Product
from .product_label_printing import (
    render_product_labels_response,
    render_product_qr_labels_response,
)
from .scan_admin_contacts_cockpit import (
    ACTION_ASSIGN_ROLE,
    ACTION_CLOSE_RECIPIENT_BINDING,
    ACTION_CREATE_GUIDED_CONTACT,
    ACTION_DISABLE_SHIPPER_SCOPE,
    ACTION_LINK_ROLE_CONTACT,
    ACTION_SET_PRIMARY_ROLE_CONTACT,
    ACTION_UNASSIGN_ROLE,
    ACTION_UNLINK_ROLE_CONTACT,
    ACTION_UPSERT_ORG_CONTACT,
    ACTION_UPSERT_RECIPIENT_BINDING,
    ACTION_UPSERT_SHIPPER_SCOPE,
    assign_role,
    build_cockpit_context,
    close_recipient_binding,
    create_guided_contact,
    disable_shipper_scope,
    link_role_contact,
    parse_cockpit_filters,
    set_primary_role_contact,
    unassign_role,
    unlink_role_contact,
    upsert_org_contact,
    upsert_recipient_binding,
    upsert_shipper_scope,
)
from .view_permissions import require_superuser as _require_superuser
from .view_permissions import scan_staff_required

TEMPLATE_SCAN_ADMIN_CONTACTS = "scan/admin_contacts.html"
TEMPLATE_SCAN_ADMIN_PRODUCTS = "scan/admin_products.html"
TEMPLATE_SCAN_PRODUCT_LABELS = "scan/admin_product_labels.html"
ACTIVE_SCAN_ADMIN_CONTACTS = "admin_contacts"
ACTIVE_SCAN_ADMIN_PRODUCTS = "admin_products"
ACTIVE_SCAN_PRODUCT_LABELS = "product_labels"

CONTACT_FILTER_ALL = "all"
CONTACT_FILTER_CHOICES = (
    (CONTACT_FILTER_ALL, "Tous"),
    (ContactType.ORGANIZATION, "Organisation"),
    (ContactType.PERSON, "Personne"),
)
CONTACT_FILTER_VALUES = {choice[0] for choice in CONTACT_FILTER_CHOICES}

PRODUCT_SELECTION_MODE_SELECTION = "selection"
PRODUCT_SELECTION_MODE_ALL_FILTERED = "all_filtered"
PRODUCT_SELECTION_MODE_VALUES = {
    PRODUCT_SELECTION_MODE_SELECTION,
    PRODUCT_SELECTION_MODE_ALL_FILTERED,
}


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


def _build_contacts_redirect(*, query, contact_filter, edit_id=None):
    params = {}
    if query:
        params["q"] = query
    if contact_filter != CONTACT_FILTER_ALL:
        params["contact_type"] = contact_filter
    if edit_id:
        params["edit"] = str(edit_id)
    url = reverse("scan:scan_admin_contacts")
    if params:
        url = f"{url}?{urlencode(params)}"
    return redirect(url)


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


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_admin_contacts(request):
    _require_superuser(request)
    query = (request.GET.get("q") or request.POST.get("q") or "").strip()
    cockpit_filters = parse_cockpit_filters(
        role=request.GET.get("role") or request.POST.get("role") or "",
        shipper_org_id=request.GET.get("shipper_org_id")
        or request.POST.get("shipper_org_id")
        or "",
    )
    contact_filter = _normalize_contact_filter(
        request.GET.get("contact_type") or request.POST.get("contact_type")
    )

    base_contacts_qs = _apply_contact_filter(
        Contact.objects.select_related("organization")
        .prefetch_related("tags", "destinations", "linked_shippers")
        .order_by("name", "id"),
        contact_filter,
    )
    contacts = _apply_contact_query(base_contacts_qs, query)

    correspondents = _apply_contact_filter(
        contacts_with_tags(TAG_CORRESPONDENT)
        .select_related("organization")
        .prefetch_related("tags", "destinations"),
        contact_filter,
    )
    correspondents = _apply_contact_query(correspondents, query)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == ACTION_ASSIGN_ROLE:
            ok, message = assign_role(
                organization_id=request.POST.get("organization_id") or "",
                role=request.POST.get("role") or "",
            )
            if ok:
                messages.success(request, message)
            else:
                messages.error(request, message)
            return _build_contacts_redirect(query=query, contact_filter=contact_filter)
        elif action == ACTION_UNASSIGN_ROLE:
            ok, message = unassign_role(
                organization_id=request.POST.get("organization_id") or "",
                role=request.POST.get("role") or "",
            )
            if ok:
                messages.success(request, message)
            else:
                messages.error(request, message)
            return _build_contacts_redirect(query=query, contact_filter=contact_filter)
        elif action == ACTION_UPSERT_ORG_CONTACT:
            ok, message = upsert_org_contact(data=request.POST)
            if ok:
                messages.success(request, message)
            else:
                messages.error(request, message)
            return _build_contacts_redirect(query=query, contact_filter=contact_filter)
        elif action == ACTION_LINK_ROLE_CONTACT:
            ok, message = link_role_contact(data=request.POST)
            if ok:
                messages.success(request, message)
            else:
                messages.error(request, message)
            return _build_contacts_redirect(query=query, contact_filter=contact_filter)
        elif action == ACTION_UNLINK_ROLE_CONTACT:
            ok, message = unlink_role_contact(data=request.POST)
            if ok:
                messages.success(request, message)
            else:
                messages.error(request, message)
            return _build_contacts_redirect(query=query, contact_filter=contact_filter)
        elif action == ACTION_SET_PRIMARY_ROLE_CONTACT:
            ok, message = set_primary_role_contact(data=request.POST)
            if ok:
                messages.success(request, message)
            else:
                messages.error(request, message)
            return _build_contacts_redirect(query=query, contact_filter=contact_filter)
        elif action == ACTION_UPSERT_SHIPPER_SCOPE:
            ok, message = upsert_shipper_scope(data=request.POST)
            if ok:
                messages.success(request, message)
            else:
                messages.error(request, message)
            return _build_contacts_redirect(query=query, contact_filter=contact_filter)
        elif action == ACTION_DISABLE_SHIPPER_SCOPE:
            ok, message = disable_shipper_scope(data=request.POST)
            if ok:
                messages.success(request, message)
            else:
                messages.error(request, message)
            return _build_contacts_redirect(query=query, contact_filter=contact_filter)
        elif action == ACTION_UPSERT_RECIPIENT_BINDING:
            ok, message = upsert_recipient_binding(data=request.POST)
            if ok:
                messages.success(request, message)
            else:
                messages.error(request, message)
            return _build_contacts_redirect(query=query, contact_filter=contact_filter)
        elif action == ACTION_CLOSE_RECIPIENT_BINDING:
            ok, message = close_recipient_binding(data=request.POST)
            if ok:
                messages.success(request, message)
            else:
                messages.error(request, message)
            return _build_contacts_redirect(query=query, contact_filter=contact_filter)
        elif action == ACTION_CREATE_GUIDED_CONTACT:
            ok, message = create_guided_contact(data=request.POST)
            if ok:
                messages.success(request, message)
            else:
                messages.error(request, message)
            return _build_contacts_redirect(query=query, contact_filter=contact_filter)
        else:
            messages.error(request, "Action de contact non reconnue.")

    cockpit_context = build_cockpit_context(query=query, filters=cockpit_filters)

    return render(
        request,
        TEMPLATE_SCAN_ADMIN_CONTACTS,
        {
            "active": ACTIVE_SCAN_ADMIN_CONTACTS,
            "query": query,
            "contact_filter": contact_filter,
            "contact_filter_choices": CONTACT_FILTER_CHOICES,
            "contacts": contacts,
            "correspondents": correspondents,
            "contacts_admin_url": reverse("admin:contacts_contact_changelist"),
            "contact_add_url": reverse("admin:contacts_contact_add"),
            "contact_tag_add_url": reverse("admin:contacts_contacttag_add"),
            "destination_admin_url": reverse("admin:wms_destination_changelist"),
            "destination_add_url": reverse("admin:wms_destination_add"),
            **cockpit_context,
        },
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
        messages.warning(request, "Aucun produit selectionne.")
        return _build_product_labels_redirect(query=query, selection_mode=selection_mode)
    return render_product_labels_response(request, products)


@scan_staff_required
@require_http_methods(["POST"])
def scan_product_labels_print_qr(request):
    _require_superuser(request)
    products, query, selection_mode = _resolve_product_labels_selection(request)
    if not products:
        messages.warning(request, "Aucun produit selectionne.")
        return _build_product_labels_redirect(query=query, selection_mode=selection_mode)
    return render_product_qr_labels_response(request, products)
