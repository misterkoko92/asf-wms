from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from contacts.models import Contact, ContactType, RecipientLegalForm

from .country_choices import DEFAULT_COUNTRY, build_country_choices
from .forms_admin_contacts_destination import DUPLICATE_ACTION_CHOICES
from .models import Destination, ShipmentShipper

BUSINESS_TYPE_OPTIONS = (
    ("shipper", _("Expéditeur")),
    ("recipient", _("Destinataire")),
    ("correspondent", _("Correspondant")),
    ("donor", _("Donateur")),
    ("transporter", _("Transporteur")),
    ("partner", _("Partenaire")),
    ("other", _("Autre")),
    ("volunteer", _("Bénévole")),
)


def build_business_type_choices(*, allowed_business_types=None):
    allowed_values = None
    if allowed_business_types is not None:
        allowed_values = {
            str(value).strip() for value in allowed_business_types if str(value).strip()
        }
    options = BUSINESS_TYPE_OPTIONS
    if allowed_values is not None:
        options = tuple(choice for choice in BUSINESS_TYPE_OPTIONS if choice[0] in allowed_values)
    return (("", _("Choisir...")),) + tuple(
        sorted(options, key=lambda choice: str(choice[1]).casefold())
    )


ENTITY_TYPE_CHOICES = (
    ("", _("Choisir...")),
    (ContactType.ORGANIZATION, _("Structure")),
    (ContactType.PERSON, _("Personne")),
)

DUPLICATE_ROLE_CHOICES = (
    ("", _("Choisir...")),
    ("existing", _("Déjà présent")),
    ("new", _("Nouvel ajout")),
)


class ContactCrudForm(forms.Form):
    business_type = forms.ChoiceField(choices=build_business_type_choices(), label=_("Type métier"))
    entity_type = forms.ChoiceField(
        choices=ENTITY_TYPE_CHOICES,
        required=False,
        label=_("Nature"),
    )
    organization_name = forms.CharField(max_length=200, required=False, label=_("Structure"))
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
    country = forms.ChoiceField(
        choices=(),
        required=False,
        label=_("Pays"),
        initial=DEFAULT_COUNTRY,
    )
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
    duplicate_keep_choice = forms.ChoiceField(
        required=False,
        choices=DUPLICATE_ROLE_CHOICES,
        label=_("Contact à conserver"),
    )
    duplicate_delete_choice = forms.ChoiceField(
        required=False,
        choices=DUPLICATE_ROLE_CHOICES,
        label=_("Contact à supprimer"),
    )

    def __init__(self, *args, allowed_business_types=None, **kwargs):
        self.allowed_business_types = tuple(allowed_business_types or ())
        super().__init__(*args, **kwargs)
        self.fields["business_type"].choices = build_business_type_choices(
            allowed_business_types=self.allowed_business_types or None
        )
        current_country = self._current_country_value()
        self.fields["country"].choices = build_country_choices(
            current_country,
            include_blank=True,
        )
        if not self.is_bound and not self.initial.get("country"):
            self.initial["country"] = DEFAULT_COUNTRY
        self.fields["destination_id"].queryset = Destination.objects.filter(
            is_active=True
        ).order_by("city", "iata_code", "id")
        active_shipper_ids = ShipmentShipper.objects.filter(
            is_active=True,
            organization__contact_type=ContactType.ORGANIZATION,
            organization__is_active=True,
        ).values_list("organization_id", flat=True)
        self.fields["allowed_shipper_ids"].queryset = Contact.objects.filter(
            pk__in=active_shipper_ids,
        ).order_by("name", "id")
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.HiddenInput):
                continue
            elif isinstance(widget, forms.SelectMultiple):
                widget.attrs.setdefault("class", "form-select ui-select--xl")
                widget.attrs.setdefault("size", "6")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select ui-select--md")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "form-control")
                widget.attrs["rows"] = "2"
            else:
                widget.attrs.setdefault("class", "form-control")
        self.fields["destination_id"].widget.attrs["class"] = "form-select ui-select--lg"
        self.fields["allowed_shipper_ids"].widget.attrs["class"] = "form-select ui-select--xl"

    def _current_country_value(self):
        if self.is_bound:
            return (self.data.get(self.add_prefix("country")) or "").strip()
        return str(
            self.initial.get("country") or self.fields["country"].initial or DEFAULT_COUNTRY
        ).strip()

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
        duplicate_keep_choice = (cleaned_data.get("duplicate_keep_choice") or "").strip()
        duplicate_delete_choice = (cleaned_data.get("duplicate_delete_choice") or "").strip()

        if not business_type:
            self.add_error("business_type", _("Choisissez un type de contact."))
            return cleaned_data

        if business_type in {"shipper", "recipient", "correspondent"}:
            self._require_fields(cleaned_data, "organization_name", "first_name", "last_name")
        elif business_type == "volunteer":
            self._require_fields(cleaned_data, "first_name", "last_name")
            if entity_type == ContactType.ORGANIZATION:
                self.add_error("entity_type", _("Un bénévole doit être une personne."))
        elif business_type in {"donor", "transporter", "partner", "other"}:
            if not entity_type:
                self.add_error("entity_type", _("Choisissez une nature de contact."))
            elif entity_type == ContactType.PERSON:
                self._require_fields(cleaned_data, "first_name", "last_name")
            else:
                self._require_fields(cleaned_data, "organization_name")

        if business_type in {"recipient", "correspondent"}:
            self._require_fields(cleaned_data, "destination_id")
        if business_type == "recipient" and not cleaned_data.get("allowed_shipper_ids"):
            self.add_error("allowed_shipper_ids", _("Choisissez au moins un expéditeur autorisé."))
        if business_type == "recipient":
            self._require_fields(cleaned_data, "legal_form", "beneficiary_count")

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
        if duplicate_action in {"replace", "merge"} and not duplicate_keep_choice:
            self.add_error(
                "duplicate_keep_choice",
                _("Choisissez le contact à conserver."),
            )
        if duplicate_action in {"replace", "merge"} and not duplicate_delete_choice:
            self.add_error(
                "duplicate_delete_choice",
                _("Choisissez le contact à supprimer."),
            )
        if (
            duplicate_action in {"replace", "merge"}
            and duplicate_keep_choice
            and duplicate_delete_choice
            and duplicate_keep_choice == duplicate_delete_choice
        ):
            self.add_error(
                "duplicate_delete_choice",
                _("Le contact supprimé doit être différent du contact conservé."),
            )
        return cleaned_data
