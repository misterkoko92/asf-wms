from django import forms
from django.utils import timezone

from contacts.models import Contact
from .scan_helpers import resolve_product
from .models import (
    Carton,
    CartonStatus,
    Location,
    Product,
    ProductLot,
    ProductLotStatus,
    Receipt,
    ReceiptType,
    Order,
    Shipment,
    ShipmentStatus,
    Warehouse,
)


class ReceiveStockForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_active=True))
    lot_code = forms.CharField(required=False)
    quantity = forms.IntegerField(min_value=1)
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        help_text="Laissez vide pour utiliser l'emplacement par defaut.",
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
        choices=[("", "Auto")] + list(ProductLotStatus.choices), required=False
    )
    storage_conditions = forms.CharField(required=False)


class AdjustStockForm(forms.Form):
    product_lot = forms.ModelChoiceField(queryset=ProductLot.objects.all())
    quantity_delta = forms.IntegerField()
    reason_code = forms.CharField(required=False)
    reason_notes = forms.CharField(widget=forms.Textarea, required=False)

    def clean_quantity_delta(self):
        value = self.cleaned_data["quantity_delta"]
        if value == 0:
            raise forms.ValidationError("La quantite doit etre non nulle.")
        return value


class TransferStockForm(forms.Form):
    product_lot = forms.ModelChoiceField(queryset=ProductLot.objects.all())
    to_location = forms.ModelChoiceField(queryset=Location.objects.all())


class PackCartonForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_active=True))
    quantity = forms.IntegerField(min_value=1)
    carton = forms.ModelChoiceField(queryset=Carton.objects.all(), required=False)
    carton_code = forms.CharField(required=False)
    shipment = forms.ModelChoiceField(queryset=Shipment.objects.all(), required=False)
    current_location = forms.ModelChoiceField(
        queryset=Location.objects.all(), required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["carton"].queryset = Carton.objects.exclude(
            status=CartonStatus.SHIPPED
        )
        self.fields["shipment"].queryset = Shipment.objects.exclude(
            status__in=[ShipmentStatus.SHIPPED, ShipmentStatus.DELIVERED]
        )

    def clean(self):
        cleaned = super().clean()
        carton = cleaned.get("carton")
        carton_code = cleaned.get("carton_code")
        if carton and carton_code:
            raise forms.ValidationError(
                "Selectionnez un carton existant ou indiquez un code, pas les deux."
            )
        return cleaned


class ScanReceiptSelectForm(forms.Form):
    receipt = forms.ModelChoiceField(
        queryset=Receipt.objects.none(),
        label="Reception existante",
    )

    def __init__(self, *args, receipts_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = receipts_qs if receipts_qs is not None else Receipt.objects.all()
        field = self.fields["receipt"]
        field.queryset = queryset
        field.label_from_instance = (
            lambda obj: f"{obj.reference or f'Reception {obj.id}'}"
            f" - {obj.get_receipt_type_display()} ({obj.get_status_display()})"
            f" - {obj.received_on:%d/%m/%Y}"
        )


class ScanReceiptCreateForm(forms.Form):
    receipt_type = forms.ChoiceField(
        label="Type reception",
        choices=ReceiptType.choices,
        required=False,
        initial=ReceiptType.DONATION,
    )
    source_contact = forms.ModelChoiceField(
        label="Provenance",
        queryset=Contact.objects.filter(is_active=True),
        required=False,
    )
    carrier_contact = forms.ModelChoiceField(
        label="Transporteur",
        queryset=Contact.objects.filter(is_active=True),
        required=False,
    )
    origin_reference = forms.CharField(label="Reference provenance", required=False)
    carrier_reference = forms.CharField(label="Reference transport", required=False)
    received_on = forms.DateField(
        label="Date reception",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        initial=timezone.localdate,
    )
    warehouse = forms.ModelChoiceField(
        label="Entrepot",
        queryset=Warehouse.objects.all(),
        required=False,
    )
    notes = forms.CharField(label="Notes", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("receipt_type"):
            self.add_error("receipt_type", "Type de reception requis.")
        receipt_type = cleaned.get("receipt_type")
        if receipt_type in {ReceiptType.PALLET, ReceiptType.ASSOCIATION}:
            if not cleaned.get("source_contact"):
                self.add_error("source_contact", "Provenance requise.")
        if receipt_type == ReceiptType.PALLET and not cleaned.get("carrier_contact"):
            self.add_error("carrier_contact", "Transporteur requis.")
        if not cleaned.get("warehouse"):
            self.add_error("warehouse", "Entrepot requis.")
        if not cleaned.get("received_on"):
            cleaned["received_on"] = timezone.localdate()
        return cleaned


class ScanReceiptPalletForm(forms.Form):
    received_on = forms.DateField(
        label="Date reception",
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
        queryset=Contact.objects.filter(is_active=True),
        required=True,
    )
    carrier_contact = forms.ModelChoiceField(
        label="Transporteur",
        queryset=Contact.objects.filter(is_active=True),
        required=True,
    )
    transport_request_date = forms.DateField(
        label="Date demande transport",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )


class ScanReceiptAssociationForm(forms.Form):
    received_on = forms.DateField(
        label="Date reception",
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
        queryset=Contact.objects.filter(is_active=True),
        required=True,
    )
    carrier_contact = forms.ModelChoiceField(
        label="Transporteur",
        queryset=Contact.objects.filter(is_active=True),
        required=False,
    )


class ScanStockUpdateForm(forms.Form):
    product_code = forms.CharField(
        label="Nom du produit",
        required=True,
        widget=forms.TextInput(attrs={"list": "product-options", "autocomplete": "off"}),
    )
    quantity = forms.IntegerField(label="Quantite", min_value=1)
    expires_on = forms.DateField(
        label="Date peremption",
        required=True,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    lot_code = forms.CharField(label="Numero de lot", required=False)
    donor_receipt = forms.ModelChoiceField(
        label="Donateur",
        queryset=Receipt.objects.none(),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["donor_receipt"].queryset = (
            Receipt.objects.filter(receipt_type=ReceiptType.PALLET)
            .order_by("-received_on", "-created_at")
        )
        self.fields["donor_receipt"].label_from_instance = (
            lambda obj: obj.reference or f"Reception {obj.id}"
        )

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
    quantity = forms.IntegerField(label="Quantite", min_value=1)
    lot_code = forms.CharField(label="Lot", required=False)
    expires_on = forms.DateField(
        label="Date peremption",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    lot_status = forms.ChoiceField(
        label="Statut lot",
        choices=[("", "Auto")] + list(ProductLotStatus.choices),
        required=False,
    )
    location = forms.ModelChoiceField(
        label="Emplacement", queryset=Location.objects.all(), required=False
    )
    storage_conditions = forms.CharField(label="Conditions stockage", required=False)
    receive_now = forms.BooleanField(label="Receptionner maintenant", required=False)


class ScanPackForm(forms.Form):
    shipment_reference = forms.CharField(label="Reference expedition", required=False)
    current_location = forms.ModelChoiceField(
        label="Emplacement", queryset=Location.objects.all(), required=False
    )


class ScanOutForm(forms.Form):
    product_code = forms.CharField(label="Code produit")
    quantity = forms.IntegerField(label="Quantite", min_value=1)
    shipment_reference = forms.CharField(label="Reference expedition", required=False)
    reason_code = forms.CharField(label="Motif", required=False)
    reason_notes = forms.CharField(
        label="Notes", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )


class ScanShipmentForm(forms.Form):
    shipper_name = forms.CharField(label="Expediteur")
    recipient_name = forms.CharField(label="Destinataire")
    correspondent_name = forms.CharField(label="Correspondant")
    destination_address = forms.CharField(
        label="Destination", widget=forms.Textarea(attrs={"rows": 3})
    )
    carton_count = forms.IntegerField(
        label="Nombre de colis",
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={"min": 1}),
    )


class ScanOrderSelectForm(forms.Form):
    order = forms.ModelChoiceField(
        queryset=Order.objects.none(),
        label="Commande existante",
    )

    def __init__(self, *args, orders_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = orders_qs if orders_qs is not None else Order.objects.none()
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
        queryset=Contact.objects.filter(is_active=True),
        required=False,
    )
    recipient_contact = forms.ModelChoiceField(
        label="Destinataire (contact)",
        queryset=Contact.objects.filter(is_active=True),
        required=False,
    )
    correspondent_contact = forms.ModelChoiceField(
        label="Correspondant (contact)",
        queryset=Contact.objects.filter(is_active=True),
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
    quantity = forms.IntegerField(label="Quantite", min_value=1)
