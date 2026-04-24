from django import forms

from .models import Location, Product, ProductCategory, ProductTag


class ScanAdminProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "brand",
            "color",
            "photo",
            "category",
            "tags",
            "barcode",
            "ean",
            "pu_ht",
            "tva",
            "default_location",
            "length_cm",
            "width_cm",
            "height_cm",
            "weight_g",
            "volume_cm3",
            "storage_conditions",
            "perishable",
            "quarantine_default",
            "is_active",
            "notes",
        ]
        widgets = {
            "tags": forms.SelectMultiple(attrs={"size": 6}),
            "pu_ht": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "tva": forms.NumberInput(attrs={"min": 0, "step": "0.0001"}),
            "length_cm": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "width_cm": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "height_cm": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "weight_g": forms.NumberInput(attrs={"min": 0, "step": 1}),
            "volume_cm3": forms.NumberInput(attrs={"min": 0, "step": 1}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "pu_ht": "PU HT",
            "tva": "TVA",
            "ean": "EAN",
            "default_location": "Emplacement par defaut",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = ProductCategory.objects.select_related(
            "parent"
        ).order_by("name", "id")
        self.fields["category"].label_from_instance = lambda category: str(category)
        self.fields["default_location"].queryset = Location.objects.select_related(
            "warehouse"
        ).order_by("warehouse__name", "zone", "aisle", "shelf")
        self.fields["default_location"].label_from_instance = lambda location: str(location)
        self.fields["tags"].queryset = ProductTag.objects.order_by("name")
        if self.instance.pk:
            self.fields["sku"].disabled = True

    def clean_sku(self):
        value = (self.cleaned_data.get("sku") or "").strip().upper()
        if self.instance.pk:
            return self.instance.sku
        if value and Product.objects.filter(sku=value).exists():
            raise forms.ValidationError("Ce SKU existe deja.")
        return value

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ScanAdminKitItemForm(forms.Form):
    component = forms.ModelChoiceField(
        queryset=Product.objects.none(),
        label="Composant",
    )
    quantity = forms.IntegerField(label="Quantite", min_value=1)

    def __init__(self, *args, kit=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Product.objects.filter(is_active=True).order_by("name", "id")
        if kit is not None and kit.pk:
            queryset = queryset.exclude(pk=kit.pk)
        self.fields["component"].queryset = queryset
        self.fields["component"].label_from_instance = lambda product: (
            f"{product.name} ({product.sku})"
        )
