from django import forms
from django.utils import timezone

from contacts.models import Contact, ContactType
from .contact_filters import (
    TAG_CORRESPONDENT,
    TAG_DONOR,
    TAG_RECIPIENT,
    TAG_SHIPPER,
    TAG_TRANSPORTER,
    contacts_with_tags,
    filter_contacts_for_destination,
    filter_recipients_for_shipper,
)
from .contact_labels import build_contact_select_label
from .scan_helpers import resolve_product
from .models import (
    Carton,
    CartonStatus,
    Destination,
    Location,
    Product,
    ProductLot,
    ProductLotStatus,
    Receipt,
    ReceiptType,
    Order,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingStatus,
    Warehouse,
)


def _contact_label(contact):
    return contact.organization.name if contact.organization else contact.name


def _sorted_choices(choices):
    return sorted(choices, key=lambda choice: str(choice[1] or "").lower())


class ReceiveStockForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True).order_by("name")
    )
    lot_code = forms.CharField(required=False)
    quantity = forms.IntegerField(min_value=1)
    location = forms.ModelChoiceField(
        queryset=Location.objects.all().order_by("warehouse__name", "zone", "aisle", "shelf"),
        required=False,
        help_text="Laissez vide pour utiliser l'emplacement par défaut.",
    )
    received_on = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        initial=timezone.localdate,
    )
    expires_on = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    status = forms.ChoiceField(
        choices=[("", "Auto")] + _sorted_choices(ProductLotStatus.choices),
        required=False,
    )
    storage_conditions = forms.CharField(required=False)


class AdjustStockForm(forms.Form):
    product_lot = forms.ModelChoiceField(
        queryset=ProductLot.objects.all().order_by("product__name", "lot_code", "expires_on")
    )
    quantity_delta = forms.IntegerField()
    reason_code = forms.CharField(required=False)
    reason_notes = forms.CharField(widget=forms.Textarea, required=False)

    def clean_quantity_delta(self):
        value = self.cleaned_data["quantity_delta"]
        if value == 0:
            raise forms.ValidationError("La quantité doit être non nulle.")
        return value


class TransferStockForm(forms.Form):
    product_lot = forms.ModelChoiceField(
        queryset=ProductLot.objects.all().order_by("product__name", "lot_code", "expires_on")
    )
    to_location = forms.ModelChoiceField(
        queryset=Location.objects.all().order_by("warehouse__name", "zone", "aisle", "shelf")
    )


class PackCartonForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True).order_by("name")
    )
    quantity = forms.IntegerField(min_value=1)
    carton = forms.ModelChoiceField(queryset=Carton.objects.all().order_by("code"), required=False)
    carton_code = forms.CharField(required=False)
    shipment = forms.ModelChoiceField(
        queryset=Shipment.objects.all().order_by("reference"),
        required=False,
    )
    current_location = forms.ModelChoiceField(
        queryset=Location.objects.all().order_by("warehouse__name", "zone", "aisle", "shelf"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["carton"].queryset = (
            Carton.objects.exclude(status=CartonStatus.SHIPPED).order_by("code")
        )
        self.fields["shipment"].queryset = (
            Shipment.objects.filter(archived_at__isnull=True)
            .exclude(
                status__in=[
                    ShipmentStatus.PLANNED,
                    ShipmentStatus.SHIPPED,
                    ShipmentStatus.RECEIVED_CORRESPONDENT,
                    ShipmentStatus.DELIVERED,
                ]
            )
            .order_by("reference")
        )

    def clean(self):
        cleaned = super().clean()
        carton = cleaned.get("carton")
        carton_code = cleaned.get("carton_code")
        if carton and carton_code:
            raise forms.ValidationError(
                "Sélectionnez un carton existant ou indiquez un code, pas les deux."
            )
        return cleaned


class ScanReceiptSelectForm(forms.Form):
    receipt = forms.ModelChoiceField(
        queryset=Receipt.objects.none(),
        label="Réception existante",
    )

    def __init__(self, *args, receipts_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = receipts_qs if receipts_qs is not None else Receipt.objects.all()
        if not queryset.query.is_sliced:
            queryset = queryset.order_by("reference", "id")
        field = self.fields["receipt"]
        field.queryset = queryset
        field.label_from_instance = (
            lambda obj: f"{obj.reference or f'Réception {obj.id}'}"
            f" - {obj.get_receipt_type_display()} ({obj.get_status_display()})"
            f" - {obj.received_on:%d/%m/%Y}"
        )


class ScanReceiptCreateForm(forms.Form):
    receipt_type = forms.ChoiceField(
        label="Type réception",
        choices=_sorted_choices(ReceiptType.choices),
        required=False,
        initial=ReceiptType.DONATION,
    )
    source_contact = forms.ModelChoiceField(
        label="Provenance",
        queryset=Contact.objects.filter(is_active=True).order_by("name"),
        required=False,
    )
    carrier_contact = forms.ModelChoiceField(
        label="Transporteur",
        queryset=Contact.objects.filter(is_active=True).order_by("name"),
        required=False,
    )
    origin_reference = forms.CharField(label="Référence provenance", required=False)
    carrier_reference = forms.CharField(label="Référence transport", required=False)
    received_on = forms.DateField(
        label="Date réception",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        initial=timezone.localdate,
    )
    warehouse = forms.ModelChoiceField(
        label="Entrepôt",
        queryset=Warehouse.objects.all().order_by("name"),
        required=False,
    )
    notes = forms.CharField(label="Notes", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("receipt_type"):
            self.add_error("receipt_type", "Type de réception requis.")
        receipt_type = cleaned.get("receipt_type")
        if receipt_type in {ReceiptType.PALLET, ReceiptType.ASSOCIATION}:
            if not cleaned.get("source_contact"):
                self.add_error("source_contact", "Provenance requise.")
        if receipt_type == ReceiptType.PALLET and not cleaned.get("carrier_contact"):
            self.add_error("carrier_contact", "Transporteur requis.")
        if not cleaned.get("warehouse"):
            self.add_error("warehouse", "Entrepôt requis.")
        if not cleaned.get("received_on"):
            cleaned["received_on"] = timezone.localdate()
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source_contact"].label_from_instance = _contact_label
        self.fields["carrier_contact"].label_from_instance = _contact_label


class ScanReceiptPalletForm(forms.Form):
    received_on = forms.DateField(
        label="Date réception",
        required=True,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        initial=timezone.localdate,
    )
    pallet_count = forms.IntegerField(
        label="Nombre de palettes",
        min_value=1,
        widget=forms.NumberInput(attrs={"min": 1}),
    )
    source_contact = forms.ModelChoiceField(
        label="Donateur",
        queryset=Contact.objects.filter(is_active=True).order_by("name"),
        required=True,
    )
    carrier_contact = forms.ModelChoiceField(
        label="Transporteur",
        queryset=Contact.objects.filter(is_active=True).order_by("name"),
        required=True,
    )
    transport_request_date = forms.DateField(
        label="Date demande transport",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source_contact"].queryset = contacts_with_tags(TAG_DONOR)
        self.fields["carrier_contact"].queryset = contacts_with_tags(TAG_TRANSPORTER)
        self.fields["source_contact"].label_from_instance = _contact_label
        self.fields["carrier_contact"].label_from_instance = _contact_label
        _select_single_choice(self.fields["source_contact"])
        _select_single_choice(self.fields["carrier_contact"])


class ScanReceiptAssociationForm(forms.Form):
    received_on = forms.DateField(
        label="Date réception",
        required=True,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        initial=timezone.localdate,
    )
    carton_count = forms.IntegerField(
        label="Nombre de cartons",
        min_value=1,
        widget=forms.NumberInput(attrs={"min": 1}),
    )
    hors_format_count = forms.IntegerField(
        label="Nombre de hors format",
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={"min": 0}),
    )
    source_contact = forms.ModelChoiceField(
        label="Association",
        queryset=Contact.objects.filter(is_active=True).order_by("name"),
        required=True,
    )
    carrier_contact = forms.ModelChoiceField(
        label="Transporteur",
        queryset=Contact.objects.filter(is_active=True).order_by("name"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source_contact"].queryset = contacts_with_tags(TAG_SHIPPER)
        self.fields["carrier_contact"].queryset = contacts_with_tags(TAG_TRANSPORTER)
        self.fields["source_contact"].label_from_instance = _contact_label
        self.fields["carrier_contact"].label_from_instance = _contact_label
        _select_single_choice(self.fields["source_contact"])
        _select_single_choice(self.fields["carrier_contact"])


class ScanStockUpdateForm(forms.Form):
    product_code = forms.CharField(
        label="Nom du produit",
        required=True,
        widget=forms.TextInput(attrs={"list": "product-options", "autocomplete": "off"}),
    )
    quantity = forms.IntegerField(label="Quantité", min_value=1)
    expires_on = forms.DateField(
        label="Date péremption",
        required=True,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    lot_code = forms.CharField(label="Numéro de lot", required=False)
    donor_contact = forms.ModelChoiceField(
        label="Donateur",
        queryset=Contact.objects.none(),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["donor_contact"].queryset = (
            contacts_with_tags(TAG_DONOR)
            .filter(contact_type=ContactType.ORGANIZATION)
            .order_by("name")
        )
        self.fields["donor_contact"].label_from_instance = _contact_label
        _select_single_choice(self.fields["donor_contact"])

    def clean_product_code(self):
        code = self.cleaned_data["product_code"]
        product = resolve_product(code)
        if not product:
            raise forms.ValidationError("Produit introuvable.")
        self.product = product
        return code


class ScanReceiptLineForm(forms.Form):
    receipt_id = forms.IntegerField(widget=forms.HiddenInput, required=False)
    product_code = forms.CharField(
        label="Code produit",
        widget=forms.TextInput(attrs={"list": "product-options", "autocomplete": "off"}),
    )
    quantity = forms.IntegerField(label="Quantité", min_value=1)
    lot_code = forms.CharField(label="Lot", required=False)
    expires_on = forms.DateField(
        label="Date péremption",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    lot_status = forms.ChoiceField(
        label="Statut lot",
        choices=[("", "Auto")] + _sorted_choices(ProductLotStatus.choices),
        required=False,
    )
    location = forms.ModelChoiceField(
        label="Emplacement",
        queryset=Location.objects.all().order_by("warehouse__name", "zone", "aisle", "shelf"),
        required=False,
    )
    storage_conditions = forms.CharField(label="Conditions stockage", required=False)
    receive_now = forms.BooleanField(label="Réceptionner maintenant", required=False)


class ScanPackForm(forms.Form):
    shipment_reference = forms.CharField(label="Référence expédition", required=False)
    current_location = forms.ModelChoiceField(
        label="Emplacement",
        queryset=Location.objects.all().order_by("warehouse__name", "zone", "aisle", "shelf"),
        required=False,
    )


class ScanOutForm(forms.Form):
    product_code = forms.CharField(
        label="Code produit",
        widget=forms.TextInput(attrs={"list": "product-options", "autocomplete": "off"}),
    )
    quantity = forms.IntegerField(label="Quantité", min_value=1)
    shipment_reference = forms.CharField(label="Référence expédition", required=False)
    reason_code = forms.CharField(label="Motif", required=False)
    reason_notes = forms.CharField(
        label="Notes", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )


class ScanShipmentForm(forms.Form):
    destination = forms.ModelChoiceField(
        label="Destination",
        queryset=Destination.objects.none(),
    )
    shipper_contact = forms.ModelChoiceField(
        label="Expéditeur",
        queryset=Contact.objects.none(),
    )
    recipient_contact = forms.ModelChoiceField(
        label="Destinataire",
        queryset=Contact.objects.none(),
    )
    correspondent_contact = forms.ModelChoiceField(
        label="Correspondant",
        queryset=Contact.objects.none(),
    )
    carton_count = forms.IntegerField(
        label="Nombre de colis",
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={"min": 1}),
    )

    def __init__(self, *args, destination_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        destinations = Destination.objects.filter(is_active=True).select_related(
            "correspondent_contact"
        ).order_by("city")
        self.fields["destination"].queryset = destinations

        selected_destination = self._resolve_selected_destination(
            destinations=destinations,
            destination_id=destination_id,
        )
        shipper_contacts = contacts_with_tags(TAG_SHIPPER)
        if selected_destination:
            shipper_contacts = filter_contacts_for_destination(
                shipper_contacts,
                selected_destination,
            )
        else:
            shipper_contacts = shipper_contacts.none()
        self.fields["shipper_contact"].queryset = shipper_contacts.order_by("name")
        self.fields["shipper_contact"].label_from_instance = build_contact_select_label
        selected_shipper = self._resolve_selected_shipper()

        recipients = contacts_with_tags(TAG_RECIPIENT)
        correspondents = contacts_with_tags(TAG_CORRESPONDENT)

        if selected_shipper:
            recipients = filter_recipients_for_shipper(recipients, selected_shipper)
        else:
            recipients = recipients.none()

        if selected_destination:
            correspondents = filter_contacts_for_destination(
                correspondents, selected_destination
            )
            if selected_destination.correspondent_contact_id:
                correspondents = correspondents.filter(
                    pk=selected_destination.correspondent_contact_id
                )
            else:
                correspondents = correspondents.none()
        else:
            correspondents = correspondents.none()

        self.fields["recipient_contact"].queryset = recipients.distinct().order_by("name")
        self.fields["correspondent_contact"].queryset = correspondents.distinct().order_by("name")
        self.fields["recipient_contact"].label_from_instance = build_contact_select_label

    def _selected_value(self, field_name, *, explicit_value=None):
        if explicit_value:
            return explicit_value
        if self.is_bound:
            value = self.data.get(field_name)
            if value:
                return value
        initial_value = self.initial.get(field_name)
        if initial_value:
            return initial_value
        field_initial = self.fields[field_name].initial
        if field_initial:
            return field_initial
        return None

    def _resolve_selected_destination(self, *, destinations, destination_id=None):
        destination_value = self._selected_value(
            "destination",
            explicit_value=destination_id,
        )
        if not destination_value:
            return None
        return destinations.filter(pk=destination_value).first()

    def _resolve_selected_shipper(self):
        shipper_value = self._selected_value("shipper_contact")
        if not shipper_value:
            return None
        return self.fields["shipper_contact"].queryset.filter(pk=shipper_value).first()

    def clean(self):
        cleaned = super().clean()
        destination = cleaned.get("destination")
        shipper = cleaned.get("shipper_contact")
        recipient = cleaned.get("recipient_contact")
        correspondent = cleaned.get("correspondent_contact")
        if destination and shipper and not filter_contacts_for_destination(
            Contact.objects.filter(pk=shipper.pk),
            destination,
        ).exists():
            self.add_error(
                "shipper_contact",
                "Contact non disponible pour cette destination.",
            )
        if shipper and recipient and not filter_recipients_for_shipper(
            Contact.objects.filter(pk=recipient.pk),
            shipper,
        ).exists():
            self.add_error(
                "recipient_contact",
                "Destinataire non disponible pour cet expéditeur.",
            )
        if destination and correspondent and not filter_contacts_for_destination(
            Contact.objects.filter(pk=correspondent.pk),
            destination,
        ).exists():
            self.add_error(
                "correspondent_contact",
                "Contact non disponible pour cette destination.",
            )
        if destination and destination.correspondent_contact_id:
            if correspondent and correspondent.id != destination.correspondent_contact_id:
                self.add_error(
                    "correspondent_contact",
                    "Correspondant non lie a la destination.",
                )
        return cleaned


class ShipmentTrackingForm(forms.Form):
    status = forms.ChoiceField(
        label="Etape",
        choices=[],
    )
    actor_name = forms.CharField(label="Nom", max_length=120)
    actor_structure = forms.CharField(label="Structure", max_length=120)
    comments = forms.CharField(
        label="Commentaires",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        initial_status = kwargs.pop("initial_status", None)
        super().__init__(*args, **kwargs)
        choices = list(ShipmentTrackingStatus.choices)
        self.fields["status"].choices = choices
        if initial_status and any(choice[0] == initial_status for choice in choices):
            self.fields["status"].initial = initial_status
        elif choices:
            self.fields["status"].initial = choices[0][0]


def _select_single_choice(field: forms.ModelChoiceField) -> None:
    queryset = field.queryset
    if queryset is None:
        return
    items = list(queryset[:2])
    if len(items) == 1:
        field.initial = items[0].pk
        field.empty_label = None


class ScanOrderSelectForm(forms.Form):
    order = forms.ModelChoiceField(
        queryset=Order.objects.none(),
        label="Commande existante",
    )

    def __init__(self, *args, orders_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = orders_qs if orders_qs is not None else Order.objects.none()
        if queryset and not queryset.query.is_sliced:
            queryset = queryset.order_by("reference", "id")
        field = self.fields["order"]
        field.queryset = queryset
        field.label_from_instance = (
            lambda obj: f"{obj.reference or f'Commande {obj.id}'}"
            f" - {obj.get_status_display()} - {obj.created_at:%d/%m/%Y}"
        )


class ScanOrderCreateForm(forms.Form):
    shipper_name = forms.CharField(label="Expediteur")
    recipient_name = forms.CharField(label="Destinataire")
    correspondent_name = forms.CharField(label="Correspondant", required=False)
    shipper_contact = forms.ModelChoiceField(
        label="Expediteur (contact)",
        queryset=Contact.objects.filter(is_active=True).order_by("name"),
        required=False,
    )
    recipient_contact = forms.ModelChoiceField(
        label="Destinataire (contact)",
        queryset=Contact.objects.filter(is_active=True).order_by("name"),
        required=False,
    )
    correspondent_contact = forms.ModelChoiceField(
        label="Correspondant (contact)",
        queryset=Contact.objects.filter(is_active=True).order_by("name"),
        required=False,
    )
    destination_address = forms.CharField(
        label="Adresse destination", widget=forms.Textarea(attrs={"rows": 3})
    )
    destination_city = forms.CharField(label="Ville destination", required=False)
    destination_country = forms.CharField(label="Pays destination", initial="France")
    requested_delivery_date = forms.DateField(
        label="Date souhaitée",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    notes = forms.CharField(label="Notes", required=False, widget=forms.Textarea(attrs={"rows": 3}))


class ScanOrderLineForm(forms.Form):
    order_id = forms.IntegerField(widget=forms.HiddenInput, required=False)
    product_code = forms.CharField(
        label="Code produit",
        widget=forms.TextInput(attrs={"list": "product-options", "autocomplete": "off"}),
    )
    quantity = forms.IntegerField(label="Quantité", min_value=1)
