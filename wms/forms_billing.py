from django import forms
from django.utils.text import slugify

from .models import (
    AssociationProfile,
    BillingAssociationPriceOverride,
    BillingComputationProfile,
    BillingServiceCatalogItem,
    ProductCategory,
    ReceiptShipmentAllocation,
    Shipment,
    ShipmentStatus,
    ShipmentUnitEquivalenceRule,
)


def _coerce_nullable_boolean(value):
    if value in {True, "True", "true", "1", 1}:
        return True
    if value in {False, "False", "false", "0", 0}:
        return False
    return None


def _build_unique_computation_code(*, label, current_instance=None):
    base_code = slugify(label) or "billing-profile"
    candidate = base_code
    suffix = 2

    queryset = BillingComputationProfile.objects.all()
    if current_instance and current_instance.pk:
        queryset = queryset.exclude(pk=current_instance.pk)
    while queryset.filter(code=candidate).exists():
        candidate = f"{base_code}-{suffix}"
        suffix += 1
    return candidate


class BillingComputationProfileForm(forms.ModelForm):
    applies_when_receipts_linked = forms.TypedChoiceField(
        choices=(
            ("", "Toujours"),
            ("True", "Seulement si receptions liees"),
            ("False", "Seulement sans reception liee"),
        ),
        coerce=_coerce_nullable_boolean,
        empty_value=None,
        required=False,
        label="Contexte de calcul",
    )

    class Meta:
        model = BillingComputationProfile
        fields = (
            "label",
            "applies_when_receipts_linked",
            "base_unit_source",
            "base_step_size",
            "base_step_price",
            "extra_unit_mode",
            "extra_unit_price",
            "allow_manual_override",
            "is_default_for_shipment_only",
            "is_default_for_receipt_linked",
            "is_active",
        )
        labels = {
            "label": "Libelle",
            "base_unit_source": "Base unites",
            "base_step_size": "Taille tranche de base",
            "base_step_price": "Prix tranche de base",
            "extra_unit_mode": "Mode surplus",
            "extra_unit_price": "Prix unitaire surplus",
            "allow_manual_override": "Autoriser surcharge manuelle",
            "is_default_for_shipment_only": "Profil par defaut sans reception",
            "is_default_for_receipt_linked": "Profil par defaut avec reception",
            "is_active": "Actif",
        }
        help_texts = {
            "base_step_size": "Exemple: 10 unites par tranche.",
            "base_step_price": "Exemple: 75 EUR par tranche.",
            "extra_unit_price": "Exemple: 10 EUR par unite supplementaire.",
        }
        widgets = {
            "base_step_size": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "base_step_price": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "extra_unit_price": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("is_default_for_shipment_only") and cleaned_data.get(
            "is_default_for_receipt_linked"
        ):
            self.add_error(
                None,
                "Un profil ne peut pas etre par defaut pour les deux contextes.",
            )
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not (instance.code or "").strip():
            instance.code = _build_unique_computation_code(
                label=instance.label,
                current_instance=self.instance,
            )
        if commit:
            instance.save()
        return instance


class BillingServiceCatalogItemForm(forms.ModelForm):
    class Meta:
        model = BillingServiceCatalogItem
        fields = (
            "label",
            "description",
            "service_type",
            "default_unit_price",
            "default_currency",
            "is_discount",
            "is_active",
            "display_order",
        )
        labels = {
            "label": "Libelle",
            "description": "Description",
            "service_type": "Type service",
            "default_unit_price": "Prix unitaire",
            "default_currency": "Devise",
            "is_discount": "Ligne de remise",
            "is_active": "Actif",
            "display_order": "Ordre affichage",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "default_unit_price": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "display_order": forms.NumberInput(attrs={"min": 0, "step": 1}),
        }

    def clean_default_currency(self):
        return (self.cleaned_data.get("default_currency") or "EUR").upper()


class BillingAssociationPriceOverrideForm(forms.ModelForm):
    association_profile = forms.ModelChoiceField(
        queryset=AssociationProfile.objects.select_related("contact", "user").order_by(
            "contact__name",
            "id",
        ),
        label="Association",
    )

    class Meta:
        model = BillingAssociationPriceOverride
        fields = (
            "association_profile",
            "service_catalog_item",
            "computation_profile",
            "overridden_amount",
            "currency",
            "effective_from",
            "effective_to",
            "notes",
        )
        labels = {
            "service_catalog_item": "Service catalogue",
            "computation_profile": "Profil calcul",
            "overridden_amount": "Montant surcharge",
            "currency": "Devise",
            "effective_from": "Date debut",
            "effective_to": "Date fin",
            "notes": "Notes",
        }
        widgets = {
            "overridden_amount": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "effective_from": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "effective_to": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["association_profile"].label_from_instance = lambda association_profile: (
            association_profile.contact.name
        )
        if self.instance.pk and self.instance.association_billing_profile_id:
            self.fields[
                "association_profile"
            ].initial = self.instance.association_billing_profile.association_profile_id

    def clean_currency(self):
        return (self.cleaned_data.get("currency") or "EUR").upper()

    def clean(self):
        cleaned_data = super().clean()
        service_catalog_item = cleaned_data.get("service_catalog_item")
        computation_profile = cleaned_data.get("computation_profile")
        if bool(service_catalog_item) == bool(computation_profile):
            self.add_error(
                None,
                "Selectionnez soit un service, soit un profil de calcul.",
            )
        effective_from = cleaned_data.get("effective_from")
        effective_to = cleaned_data.get("effective_to")
        if effective_from and effective_to and effective_to < effective_from:
            self.add_error(
                "effective_to", "La date de fin doit etre posterieure a la date de debut."
            )
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        association_profile = self.cleaned_data["association_profile"]
        instance.association_billing_profile = association_profile.billing_profile
        if commit:
            instance.save()
        return instance


class ShipmentUnitEquivalenceRuleForm(forms.ModelForm):
    class Meta:
        model = ShipmentUnitEquivalenceRule
        fields = (
            "label",
            "category",
            "applies_to_hors_format",
            "units_per_item",
            "priority",
            "is_active",
            "notes",
        )
        labels = {
            "label": "Libelle",
            "category": "Categorie",
            "applies_to_hors_format": "Appliquer aux hors format",
            "units_per_item": "Unites par article",
            "priority": "Priorite",
            "is_active": "Actif",
            "notes": "Notes",
        }
        widgets = {
            "units_per_item": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "priority": forms.NumberInput(attrs={"min": 0, "step": 1}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = ProductCategory.objects.select_related(
            "parent"
        ).order_by(
            "name",
            "id",
        )
        self.fields["category"].label_from_instance = lambda category: str(category)


NON_ALLOCATABLE_SHIPMENT_STATUSES = {
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
}


class ReceiptShipmentAllocationForm(forms.ModelForm):
    class Meta:
        model = ReceiptShipmentAllocation
        fields = ("shipment", "allocated_received_units", "note")
        labels = {
            "shipment": "Expedition",
            "allocated_received_units": "Unites allouees",
            "note": "Note",
        }
        widgets = {
            "allocated_received_units": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "note": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, receipt=None, **kwargs):
        super().__init__(*args, **kwargs)
        shipment_queryset = Shipment.objects.filter(archived_at__isnull=True).exclude(
            status__in=NON_ALLOCATABLE_SHIPMENT_STATUSES
        )
        if receipt is not None and receipt.source_contact_id:
            shipment_queryset = shipment_queryset.filter(shipper_contact_ref=receipt.source_contact)
        else:
            shipment_queryset = shipment_queryset.none()
        self.fields["shipment"].queryset = shipment_queryset.order_by("-created_at", "reference")
        self.fields["shipment"].label_from_instance = lambda shipment: (
            shipment.reference or f"Expedition {shipment.id}"
        )
