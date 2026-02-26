from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from contacts.models import Contact
from contacts.querysets import contacts_with_tags
from contacts.tagging import TAG_CORRESPONDENT

from .kit_components import KitCycleError, get_unit_component_quantities
from .models import Product
from .view_permissions import require_superuser as _require_superuser
from .view_permissions import scan_staff_required

TEMPLATE_SCAN_ADMIN_CONTACTS = "scan/admin_contacts.html"
TEMPLATE_SCAN_ADMIN_PRODUCTS = "scan/admin_products.html"
ACTIVE_SCAN_ADMIN_CONTACTS = "admin_contacts"
ACTIVE_SCAN_ADMIN_PRODUCTS = "admin_products"


def _apply_contact_query(queryset, query):
    if not query:
        return queryset
    return queryset.filter(
        Q(name__icontains=query)
        | Q(asf_id__icontains=query)
        | Q(email__icontains=query)
        | Q(phone__icontains=query)
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_admin_contacts(request):
    _require_superuser(request)
    query = (request.GET.get("q") or "").strip()
    contacts = _apply_contact_query(
        Contact.objects.select_related("organization")
        .prefetch_related("tags", "destinations")
        .order_by("name", "id"),
        query,
    )
    correspondents = _apply_contact_query(
        contacts_with_tags(TAG_CORRESPONDENT)
        .select_related("organization")
        .prefetch_related("tags", "destinations"),
        query,
    )
    return render(
        request,
        TEMPLATE_SCAN_ADMIN_CONTACTS,
        {
            "active": ACTIVE_SCAN_ADMIN_CONTACTS,
            "query": query,
            "contacts": contacts,
            "correspondents": correspondents,
            "contacts_admin_url": reverse("admin:contacts_contact_changelist"),
            "contact_add_url": reverse("admin:contacts_contact_add"),
            "contact_tag_add_url": reverse("admin:contacts_contacttag_add"),
            "destination_admin_url": reverse("admin:wms_destination_changelist"),
            "destination_add_url": reverse("admin:wms_destination_add"),
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
