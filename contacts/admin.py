from django import forms
from django.contrib import admin

from .models import Contact, ContactAddress, ContactTag, ContactType


class ContactAddressInline(admin.TabularInline):
    model = ContactAddress
    extra = 0
    fields = (
        "label",
        "address_line1",
        "address_line2",
        "postal_code",
        "city",
        "region",
        "country",
        "phone",
        "email",
        "is_default",
    )


class ContactAdminForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["use_organization_address"].help_text = (
            "Utilise l'adresse par defaut de la societe et se met a jour automatiquement."
        )

    def clean(self):
        cleaned_data = super().clean()
        contact_type = cleaned_data.get("contact_type")
        tags = cleaned_data.get("tags")
        organization = cleaned_data.get("organization")
        use_org_address = cleaned_data.get("use_organization_address")

        if contact_type == ContactType.ORGANIZATION and not tags:
            self.add_error("tags", "Au moins un tag est requis pour une societe.")
        if contact_type == ContactType.PERSON and use_org_address and not organization:
            self.add_error(
                "organization", "Selectionnez une societe pour utiliser son adresse."
            )
        return cleaned_data


class ContactTagAdminForm(forms.ModelForm):
    class Meta:
        model = ContactTag
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asf_prefix"].help_text = (
            "Prefix ASF (EXP, DEST, CORR, DON, TRA, PART)."
        )

    def clean_asf_prefix(self):
        prefix = (self.cleaned_data.get("asf_prefix") or "").strip()
        if not prefix:
            return None
        return prefix.upper()


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    form = ContactAdminForm
    list_display = ("name", "contact_type", "organization", "email", "phone", "asf_id", "is_active")
    list_filter = ("contact_type", "is_active", "tags")
    search_fields = (
        "name",
        "first_name",
        "last_name",
        "organization__name",
        "email",
        "email2",
        "phone",
        "phone2",
        "siret",
        "asf_id",
    )
    filter_horizontal = ("tags",)
    inlines = [ContactAddressInline]
    readonly_fields = ("asf_id",)
    fieldsets = (
        (
            "Identite",
            {
                "fields": (
                    "contact_type",
                    "title",
                    "first_name",
                    "last_name",
                    "name",
                )
            },
        ),
        (
            "Societe",
            {
                "fields": (
                    "organization",
                    "role",
                    "siret",
                    "vat_number",
                    "legal_registration_number",
                    "asf_id",
                    "tags",
                )
            },
        ),
        (
            "Coordonnees",
            {
                "fields": (
                    "email",
                    "email2",
                    "phone",
                    "phone2",
                    "use_organization_address",
                )
            },
        ),
        ("Statut", {"fields": ("is_active", "notes")}),
    )

    class Media:
        css = {"all": ("scan/address_autocomplete.css",)}
        js = ("scan/address_autocomplete.js",)


@admin.register(ContactTag)
class ContactTagAdmin(admin.ModelAdmin):
    form = ContactTagAdminForm
    search_fields = ("name", "asf_prefix")
    list_display = ("name", "asf_prefix")
    readonly_fields = ("asf_last_number",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "asf_prefix",
                    "asf_last_number",
                )
            },
        ),
    )

# Register your models here.
