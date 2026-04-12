from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from contacts.models import Contact, ContactType, RecipientLegalForm

from .models import Destination, PublicAccountRequestType, ShipmentShipper

STRUCTURE_ACCOUNT_TYPES = {
    PublicAccountRequestType.SHIPPER,
    PublicAccountRequestType.RECIPIENT,
}


def _normalized_structure_account_type(value):
    normalized_value = (value or "").strip()
    if normalized_value == PublicAccountRequestType.ASSOCIATION:
        return PublicAccountRequestType.SHIPPER
    return normalized_value


class ScanAccountValidationReviewForm(forms.Form):
    final_account_type = forms.ChoiceField(label=_("Type final"))
    organization_name = forms.CharField(
        required=False,
        max_length=200,
        label=_("Structure"),
    )
    first_name = forms.CharField(required=False, max_length=120, label=_("Prénom référent"))
    last_name = forms.CharField(required=False, max_length=120, label=_("Nom référent"))
    email = forms.EmailField(required=False, label="Email")
    phone = forms.CharField(required=False, max_length=40, label=_("Téléphone"))
    destination_id = forms.ModelChoiceField(
        queryset=Destination.objects.none(),
        required=False,
        label=_("Escale"),
    )
    allowed_shipper_ids = forms.ModelMultipleChoiceField(
        queryset=Contact.objects.none(),
        required=False,
        label=_("Expéditeurs autorisés"),
    )
    legal_form = forms.ChoiceField(
        choices=(("", _("Choisir...")),) + tuple(RecipientLegalForm.choices),
        required=False,
        label=_("Forme juridique"),
    )
    beneficiary_count = forms.IntegerField(
        required=False,
        min_value=0,
        label=_("Nombre de bénéficiaires"),
    )
    address_line1 = forms.CharField(required=False, max_length=200, label=_("Adresse"))
    address_line2 = forms.CharField(required=False, max_length=200, label=_("Complément"))
    postal_code = forms.CharField(required=False, max_length=20, label=_("Code postal"))
    city = forms.CharField(required=False, max_length=120, label=_("Ville"))
    country = forms.CharField(required=False, max_length=80, label=_("Pays"))

    def __init__(self, *args, account_request, **kwargs):
        self.account_request = account_request
        initial = dict(kwargs.pop("initial", {}))
        initial.update(self._build_initial_data(account_request))
        kwargs["initial"] = initial
        super().__init__(*args, **kwargs)

        self.fields["destination_id"].queryset = Destination.objects.filter(
            is_active=True
        ).order_by("city", "iata_code", "id")
        active_shipper_ids = ShipmentShipper.objects.filter(
            is_active=True,
            organization__is_active=True,
            organization__contact_type=ContactType.ORGANIZATION,
        ).values_list("organization_id", flat=True)
        self.fields["allowed_shipper_ids"].queryset = Contact.objects.filter(
            pk__in=active_shipper_ids,
        ).order_by("name", "id")

        if account_request.account_type == PublicAccountRequestType.USER:
            self.fields["final_account_type"].choices = [
                (PublicAccountRequestType.USER, PublicAccountRequestType.USER.label)
            ]
        else:
            self.fields["final_account_type"].choices = [
                (choice.value, choice.label)
                for choice in PublicAccountRequestType
                if choice.value in STRUCTURE_ACCOUNT_TYPES
            ]

        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.SelectMultiple):
                widget.attrs.setdefault("class", "form-select ui-select--xl")
                widget.attrs.setdefault("size", "6")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select ui-select--lg")
            else:
                widget.attrs.setdefault("class", "form-control")

    def _build_initial_data(self, account_request):
        snapshot = account_request.review_snapshot or {}
        organization = account_request.contact
        referent = None
        if organization is not None:
            referent = (
                organization.members.filter(
                    contact_type=ContactType.PERSON,
                    is_active=True,
                )
                .order_by("id")
                .first()
            )

        return {
            "final_account_type": snapshot.get("final_account_type")
            and _normalized_structure_account_type(snapshot.get("final_account_type"))
            or _normalized_structure_account_type(account_request.account_type),
            "organization_name": snapshot.get("organization_name")
            or account_request.association_name
            or getattr(organization, "name", ""),
            "first_name": snapshot.get("first_name") or getattr(referent, "first_name", ""),
            "last_name": snapshot.get("last_name") or getattr(referent, "last_name", ""),
            "email": snapshot.get("email") or account_request.email,
            "phone": snapshot.get("phone") or account_request.phone,
            "destination_id": snapshot.get("destination_id") or account_request.destination_id,
            "allowed_shipper_ids": snapshot.get("allowed_shipper_ids") or [],
            "legal_form": snapshot.get("legal_form") or getattr(organization, "legal_form", ""),
            "beneficiary_count": snapshot.get("beneficiary_count")
            if snapshot.get("beneficiary_count") is not None
            else getattr(organization, "beneficiary_count", ""),
            "address_line1": snapshot.get("address_line1") or account_request.address_line1,
            "address_line2": snapshot.get("address_line2") or account_request.address_line2,
            "postal_code": snapshot.get("postal_code") or account_request.postal_code,
            "city": snapshot.get("city") or account_request.city,
            "country": snapshot.get("country") or account_request.country or "France",
        }

    def _require_fields(self, cleaned_data, *field_names):
        for field_name in field_names:
            value = cleaned_data.get(field_name)
            if value in (None, "", []):
                self.add_error(field_name, _("Ce champ est obligatoire."))

    def clean(self):
        cleaned_data = super().clean()
        final_account_type = _normalized_structure_account_type(
            cleaned_data.get("final_account_type")
        )
        if final_account_type != cleaned_data.get("final_account_type"):
            cleaned_data["final_account_type"] = final_account_type

        if final_account_type == PublicAccountRequestType.USER:
            return cleaned_data

        if final_account_type not in STRUCTURE_ACCOUNT_TYPES:
            self.add_error("final_account_type", _("Type final invalide."))
            return cleaned_data

        self._require_fields(
            cleaned_data,
            "organization_name",
            "email",
            "address_line1",
        )

        if final_account_type == PublicAccountRequestType.RECIPIENT:
            self._require_fields(
                cleaned_data,
                "destination_id",
                "legal_form",
                "beneficiary_count",
                "first_name",
                "last_name",
            )
        return cleaned_data

    def build_review_overrides(self):
        if not self.is_valid():
            raise ValueError("build_review_overrides requires a valid form")
        cleaned_data = self.cleaned_data
        destination = cleaned_data.get("destination_id")
        return {
            "final_account_type": cleaned_data.get("final_account_type"),
            "organization_name": cleaned_data.get("organization_name", ""),
            "first_name": cleaned_data.get("first_name", ""),
            "last_name": cleaned_data.get("last_name", ""),
            "email": cleaned_data.get("email", ""),
            "phone": cleaned_data.get("phone", ""),
            "destination_id": destination.id if destination is not None else None,
            "allowed_shipper_ids": [
                contact.id for contact in cleaned_data.get("allowed_shipper_ids", [])
            ],
            "legal_form": cleaned_data.get("legal_form", ""),
            "beneficiary_count": cleaned_data.get("beneficiary_count"),
            "address_line1": cleaned_data.get("address_line1", ""),
            "address_line2": cleaned_data.get("address_line2", ""),
            "postal_code": cleaned_data.get("postal_code", ""),
            "city": cleaned_data.get("city", ""),
            "country": cleaned_data.get("country", ""),
        }
