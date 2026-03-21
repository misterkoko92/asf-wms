from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from contacts.models import Contact, ContactType

from .forms_admin_contacts_destination import DUPLICATE_ACTION_CHOICES
from .models import Destination

BUSINESS_TYPE_CHOICES = (
    ("", _("Choisir...")),
    ("shipper", _("Expéditeur")),
    ("recipient", _("Destinataire")),
    ("correspondent", _("Correspondant")),
    ("donor", _("Donateur")),
    ("transporter", _("Transporteur")),
    ("volunteer", _("Bénévole")),
)

ENTITY_TYPE_CHOICES = (
    ("", _("Choisir...")),
    (ContactType.ORGANIZATION, _("Structure")),
    (ContactType.PERSON, _("Personne")),
)


class ContactCrudForm(forms.Form):
    business_type = forms.ChoiceField(choices=BUSINESS_TYPE_CHOICES, label=_("Type métier"))
    entity_type = forms.ChoiceField(
        choices=ENTITY_TYPE_CHOICES,
        required=False,
        label=_("Nature"),
    )
    organization_name = forms.CharField(max_length=200, required=False, label=_("Structure"))
    title = forms.CharField(max_length=40, required=False, label=_("Titre"))
    first_name = forms.CharField(max_length=120, required=False, label=_("Prénom"))
    last_name = forms.CharField(max_length=120, required=False, label=_("Nom"))
    asf_id = forms.CharField(max_length=20, required=False, label=_("ASF ID"))
    email = forms.EmailField(required=False, label="Email")
    email2 = forms.EmailField(required=False, label="Email 2")
    phone = forms.CharField(max_length=40, required=False, label=_("Téléphone"))
    phone2 = forms.CharField(max_length=40, required=False, label=_("Téléphone 2"))
    role = forms.CharField(max_length=120, required=False, label=_("Fonction"))
    siret = forms.CharField(max_length=30, required=False, label=_("SIRET"))
    vat_number = forms.CharField(max_length=40, required=False, label=_("TVA"))
    legal_registration_number = forms.CharField(
        max_length=80,
        required=False,
        label=_("Numéro légal"),
    )
    address_line1 = forms.CharField(max_length=200, required=False, label=_("Adresse"))
    address_line2 = forms.CharField(max_length=200, required=False, label=_("Complément"))
    postal_code = forms.CharField(max_length=20, required=False, label=_("Code postal"))
    city = forms.CharField(max_length=120, required=False, label=_("Ville"))
    region = forms.CharField(max_length=120, required=False, label=_("Région"))
    country = forms.CharField(max_length=80, required=False, label=_("Pays"))
    notes = forms.CharField(required=False, widget=forms.Textarea, label=_("Notes"))
    destination_id = forms.ModelChoiceField(
        queryset=Destination.objects.none(),
        required=False,
        label=_("Destination"),
    )
    allowed_shipper_ids = forms.ModelMultipleChoiceField(
        queryset=Contact.objects.none(),
        required=False,
        label=_("Expéditeurs autorisés"),
    )
    can_send_to_all = forms.BooleanField(required=False, label=_("Peut expédier partout"))
    use_organization_address = forms.BooleanField(
        required=False,
        label=_("Utiliser l'adresse de la structure"),
    )
    is_active = forms.BooleanField(required=False, initial=True, label=_("Actif"))
    duplicate_candidates_count = forms.IntegerField(
        required=False,
        initial=0,
        widget=forms.HiddenInput,
    )
    duplicate_action = forms.ChoiceField(
        required=False,
        choices=DUPLICATE_ACTION_CHOICES,
        label=_("Décision doublon"),
    )
    duplicate_target_id = forms.IntegerField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destination_id"].queryset = Destination.objects.filter(
            is_active=True
        ).order_by("city", "iata_code", "id")
        self.fields["allowed_shipper_ids"].queryset = Contact.objects.filter(
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        ).order_by("name", "id")
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.HiddenInput):
                continue
            elif isinstance(widget, forms.SelectMultiple):
                widget.attrs.setdefault("class", "form-select")
                widget.attrs.setdefault("size", "6")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "form-control")
                widget.attrs.setdefault("rows", "3")
            else:
                widget.attrs.setdefault("class", "form-control")

    def _require_fields(self, cleaned_data, *field_names):
        for field_name in field_names:
            value = cleaned_data.get(field_name)
            if value in (None, "", []):
                self.add_error(field_name, _("Ce champ est obligatoire."))

    def clean(self):
        cleaned_data = super().clean()
        business_type = (cleaned_data.get("business_type") or "").strip()
        entity_type = (cleaned_data.get("entity_type") or "").strip()
        duplicate_candidates_count = cleaned_data.get("duplicate_candidates_count") or 0
        duplicate_action = (cleaned_data.get("duplicate_action") or "").strip()
        duplicate_target_id = cleaned_data.get("duplicate_target_id")

        if not business_type:
            self.add_error("business_type", _("Choisissez un type de contact."))
            return cleaned_data

        if business_type in {"shipper", "recipient", "correspondent"}:
            self._require_fields(cleaned_data, "organization_name", "first_name", "last_name")
        elif business_type == "volunteer":
            self._require_fields(cleaned_data, "first_name", "last_name")
            if entity_type == ContactType.ORGANIZATION:
                self.add_error("entity_type", _("Un bénévole doit être une personne."))
        elif business_type in {"donor", "transporter"}:
            if entity_type == ContactType.PERSON:
                self._require_fields(cleaned_data, "first_name", "last_name")
            else:
                self._require_fields(cleaned_data, "organization_name")

        if business_type in {"recipient", "correspondent"}:
            self._require_fields(cleaned_data, "destination_id")
        if business_type == "recipient" and not cleaned_data.get("allowed_shipper_ids"):
            self.add_error("allowed_shipper_ids", _("Choisissez au moins un expéditeur autorisé."))

        if duplicate_candidates_count > 0 and not duplicate_action:
            self.add_error(
                "duplicate_action",
                _("Choisissez comment traiter le doublon proposé."),
            )
        if duplicate_action in {"replace", "merge"} and not duplicate_target_id:
            self.add_error(
                "duplicate_target_id",
                _("Choisissez une fiche cible pour la résolution du doublon."),
            )
        return cleaned_data
