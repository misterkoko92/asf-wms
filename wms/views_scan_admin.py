from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from contacts.models import Contact, ContactAddress, ContactTag, ContactType
from contacts.querysets import contacts_with_tags
from contacts.rules import (
    ensure_default_shipper_for_recipient,
    validate_recipient_links_for_creation,
)
from contacts.tagging import TAG_CORRESPONDENT, TAG_SHIPPER

from .kit_components import KitCycleError, get_unit_component_quantities
from .models import Destination, Product
from .view_permissions import require_superuser as _require_superuser
from .view_permissions import scan_staff_required

TEMPLATE_SCAN_ADMIN_CONTACTS = "scan/admin_contacts.html"
TEMPLATE_SCAN_ADMIN_PRODUCTS = "scan/admin_products.html"
ACTIVE_SCAN_ADMIN_CONTACTS = "admin_contacts"
ACTIVE_SCAN_ADMIN_PRODUCTS = "admin_products"

CONTACT_FILTER_ALL = "all"
CONTACT_FILTER_CHOICES = (
    (CONTACT_FILTER_ALL, "Tous"),
    (ContactType.ORGANIZATION, "Organisation"),
    (ContactType.PERSON, "Personne"),
)
CONTACT_FILTER_VALUES = {choice[0] for choice in CONTACT_FILTER_CHOICES}

ACTION_CREATE_CONTACT = "create_contact"
ACTION_UPDATE_CONTACT = "update_contact"
ACTION_DELETE_CONTACT = "delete_contact"


class ScanAdminContactForm(forms.ModelForm):
    tag_ids = forms.ModelMultipleChoiceField(
        label="Tags",
        queryset=ContactTag.objects.none(),
        required=False,
    )
    destination_ids = forms.ModelMultipleChoiceField(
        label="Destinations",
        queryset=Destination.objects.none(),
        required=False,
    )
    linked_shipper_ids = forms.ModelMultipleChoiceField(
        label="Expéditeurs liés",
        queryset=Contact.objects.none(),
        required=False,
    )
    address_label = forms.CharField(label="Libellé adresse", required=False)
    address_line1 = forms.CharField(label="Adresse ligne 1", required=False)
    address_line2 = forms.CharField(label="Adresse ligne 2", required=False)
    address_postal_code = forms.CharField(label="Code postal", required=False)
    address_city = forms.CharField(label="Ville", required=False)
    address_region = forms.CharField(label="Région", required=False)
    address_country = forms.CharField(label="Pays", required=False, initial="France")
    address_phone = forms.CharField(label="Téléphone adresse", required=False)
    address_email = forms.EmailField(label="Email adresse", required=False)
    remove_default_address = forms.BooleanField(
        label="Supprimer l'adresse principale",
        required=False,
    )

    class Meta:
        model = Contact
        fields = [
            "contact_type",
            "name",
            "title",
            "first_name",
            "last_name",
            "organization",
            "role",
            "email",
            "email2",
            "phone",
            "phone2",
            "siret",
            "vat_number",
            "legal_registration_number",
            "use_organization_address",
            "notes",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organization"].required = False
        self.fields["organization"].queryset = Contact.objects.filter(
            is_active=True,
            contact_type=ContactType.ORGANIZATION,
        ).order_by("name")
        self.fields["tag_ids"].queryset = ContactTag.objects.order_by("name")
        self.fields["destination_ids"].queryset = Destination.objects.filter(
            is_active=True
        ).order_by("city", "iata_code")
        linked_shipper_queryset = contacts_with_tags(TAG_SHIPPER)
        if self.instance.pk:
            linked_shipper_queryset = linked_shipper_queryset.exclude(pk=self.instance.pk)
        self.fields["linked_shipper_ids"].queryset = linked_shipper_queryset

        select_fields = [
            "contact_type",
            "organization",
            "tag_ids",
            "destination_ids",
            "linked_shipper_ids",
        ]
        for field_name in select_fields:
            self.fields[field_name].widget.attrs["class"] = "form-select"
        self.fields["tag_ids"].widget.attrs["size"] = 6
        self.fields["destination_ids"].widget.attrs["size"] = 6
        self.fields["linked_shipper_ids"].widget.attrs["size"] = 6

        text_input_fields = [
            "name",
            "title",
            "first_name",
            "last_name",
            "role",
            "email",
            "email2",
            "phone",
            "phone2",
            "siret",
            "vat_number",
            "legal_registration_number",
            "address_label",
            "address_line1",
            "address_line2",
            "address_postal_code",
            "address_city",
            "address_region",
            "address_country",
            "address_phone",
            "address_email",
        ]
        for field_name in text_input_fields:
            self.fields[field_name].widget.attrs["class"] = "form-control"
        self.fields["notes"].widget.attrs["class"] = "form-control"
        self.fields["notes"].widget.attrs.setdefault("rows", 3)
        self.fields["use_organization_address"].widget.attrs["class"] = "form-check-input"
        self.fields["is_active"].widget.attrs["class"] = "form-check-input"
        self.fields["remove_default_address"].widget.attrs["class"] = "form-check-input"

        if self.instance.pk and not self.is_bound:
            self.initial["tag_ids"] = self.instance.tags.values_list("id", flat=True)
            self.initial["destination_ids"] = self.instance.destinations.values_list(
                "id", flat=True
            )
            self.initial["linked_shipper_ids"] = self.instance.linked_shippers.values_list(
                "id", flat=True
            )
            address = self._resolve_default_address(self.instance)
            if address:
                self.initial["address_label"] = address.label
                self.initial["address_line1"] = address.address_line1
                self.initial["address_line2"] = address.address_line2
                self.initial["address_postal_code"] = address.postal_code
                self.initial["address_city"] = address.city
                self.initial["address_region"] = address.region
                self.initial["address_country"] = address.country
                self.initial["address_phone"] = address.phone
                self.initial["address_email"] = address.email
        elif not self.is_bound:
            self.initial.setdefault("is_active", True)

    def clean(self):
        cleaned = super().clean()
        contact_type = cleaned.get("contact_type") or ContactType.ORGANIZATION
        name = (cleaned.get("name") or "").strip()
        first_name = (cleaned.get("first_name") or "").strip()
        last_name = (cleaned.get("last_name") or "").strip()

        if contact_type == ContactType.PERSON:
            if not name and not (first_name or last_name):
                self.add_error(
                    "name",
                    "Nom requis (ou renseignez prénom/nom pour une personne).",
                )
        elif not name:
            self.add_error("name", "Nom requis.")

        if contact_type == ContactType.ORGANIZATION:
            cleaned["organization"] = None
            cleaned["use_organization_address"] = False

        if cleaned.get("use_organization_address") and not cleaned.get("organization"):
            self.add_error(
                "organization",
                "Sélectionnez une organisation pour partager son adresse.",
            )

        recipient_links_error = validate_recipient_links_for_creation(
            is_creation=not bool(self.instance and self.instance.pk),
            tags=cleaned.get("tag_ids"),
            linked_shippers=cleaned.get("linked_shipper_ids"),
        )
        if recipient_links_error:
            self.add_error("linked_shipper_ids", recipient_links_error)

        address_line1 = (cleaned.get("address_line1") or "").strip()
        has_secondary_address_data = any(
            (cleaned.get(field_name) or "").strip()
            for field_name in [
                "address_label",
                "address_line2",
                "address_postal_code",
                "address_city",
                "address_region",
                "address_country",
                "address_phone",
                "address_email",
            ]
        )
        if (
            has_secondary_address_data
            and not address_line1
            and not cleaned.get("remove_default_address")
        ):
            self.add_error(
                "address_line1",
                "Adresse ligne 1 requise quand une adresse est renseignée.",
            )
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        if not commit:
            raise ValueError("ScanAdminContactForm requires commit=True.")
        contact = super().save(commit=True)
        tags = self.cleaned_data.get("tag_ids") or ContactTag.objects.none()
        destinations = self.cleaned_data.get("destination_ids") or Destination.objects.none()
        linked_shippers = self.cleaned_data.get("linked_shipper_ids") or Contact.objects.none()
        if contact.pk:
            linked_shippers = linked_shippers.exclude(pk=contact.pk)

        contact.tags.set(tags)
        contact.destinations.set(destinations)
        contact.linked_shippers.set(linked_shippers)
        ensure_default_shipper_for_recipient(contact, tags=tags)
        self._save_default_address(contact)
        return contact

    @staticmethod
    def _resolve_default_address(contact):
        return (
            contact.addresses.filter(is_default=True).first()
            or contact.addresses.order_by("id").first()
        )

    def _save_default_address(self, contact):
        address = self._resolve_default_address(contact)
        if self.cleaned_data.get("remove_default_address"):
            if address:
                address.delete()
            return

        address_values = {
            "label": (self.cleaned_data.get("address_label") or "").strip(),
            "address_line1": (self.cleaned_data.get("address_line1") or "").strip(),
            "address_line2": (self.cleaned_data.get("address_line2") or "").strip(),
            "postal_code": (self.cleaned_data.get("address_postal_code") or "").strip(),
            "city": (self.cleaned_data.get("address_city") or "").strip(),
            "region": (self.cleaned_data.get("address_region") or "").strip(),
            "country": (self.cleaned_data.get("address_country") or "").strip() or "France",
            "phone": (self.cleaned_data.get("address_phone") or "").strip(),
            "email": (self.cleaned_data.get("address_email") or "").strip(),
        }
        has_address_data = any(address_values.values())
        if not has_address_data:
            return
        if not address_values["address_line1"]:
            return
        if address is None:
            address = ContactAddress(contact=contact, is_default=True)
        for key, value in address_values.items():
            setattr(address, key, value)
        address.is_default = True
        address.save()


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


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_admin_contacts(request):
    _require_superuser(request)
    query = (request.GET.get("q") or request.POST.get("q") or "").strip()
    contact_filter = _normalize_contact_filter(
        request.GET.get("contact_type") or request.POST.get("contact_type")
    )
    edit_param = request.GET.get("edit") or ""
    edit_contact = None

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

    create_form = ScanAdminContactForm(prefix="create")
    edit_form = None
    if edit_param.isdigit():
        edit_contact = Contact.objects.filter(pk=int(edit_param)).first()
        if edit_contact:
            edit_form = ScanAdminContactForm(instance=edit_contact, prefix="edit")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == ACTION_CREATE_CONTACT:
            create_form = ScanAdminContactForm(request.POST, prefix="create")
            if create_form.is_valid():
                contact = create_form.save()
                messages.success(request, "Contact créé.")
                return _build_contacts_redirect(
                    query=query,
                    contact_filter=contact_filter,
                    edit_id=contact.id,
                )
            messages.error(request, "Le formulaire de création contient des erreurs.")
        elif action == ACTION_UPDATE_CONTACT:
            contact_id = (request.POST.get("contact_id") or "").strip()
            edit_contact = get_object_or_404(Contact, pk=contact_id)
            edit_form = ScanAdminContactForm(
                request.POST,
                instance=edit_contact,
                prefix="edit",
            )
            if edit_form.is_valid():
                contact = edit_form.save()
                messages.success(request, "Contact mis à jour.")
                return _build_contacts_redirect(
                    query=query,
                    contact_filter=contact_filter,
                    edit_id=contact.id,
                )
            messages.error(request, "Le formulaire de modification contient des erreurs.")
        elif action == ACTION_DELETE_CONTACT:
            contact_id = (request.POST.get("contact_id") or "").strip()
            contact = get_object_or_404(Contact, pk=contact_id)
            try:
                contact.delete()
            except ProtectedError:
                messages.error(
                    request,
                    "Suppression impossible: ce contact est utilisé dans des opérations WMS.",
                )
                return _build_contacts_redirect(
                    query=query,
                    contact_filter=contact_filter,
                    edit_id=contact_id,
                )
            messages.success(request, "Contact supprimé.")
            return _build_contacts_redirect(query=query, contact_filter=contact_filter)
        else:
            messages.error(request, "Action de contact non reconnue.")

    if edit_contact is None and contacts:
        edit_contact = contacts[0]
        edit_form = ScanAdminContactForm(instance=edit_contact, prefix="edit")

    return render(
        request,
        TEMPLATE_SCAN_ADMIN_CONTACTS,
        {
            "active": ACTIVE_SCAN_ADMIN_CONTACTS,
            "query": query,
            "contact_filter": contact_filter,
            "contact_filter_choices": CONTACT_FILTER_CHOICES,
            "create_form": create_form,
            "edit_form": edit_form,
            "edit_contact": edit_contact,
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
