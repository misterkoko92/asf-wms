from django import forms
from django.contrib import admin

from .models import Contact, ContactAddress, ContactType


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
        fields = (
            "contact_type",
            "title",
            "first_name",
            "last_name",
            "name",
            "organization",
            "role",
            "siret",
            "vat_number",
            "legal_registration_number",
            "email",
            "email2",
            "phone",
            "phone2",
            "use_organization_address",
            "notes",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[
            "use_organization_address"
        ].help_text = "Utilise l'adresse par défaut de la société et se met à jour automatiquement."

    def clean(self):
        cleaned_data = super().clean()
        contact_type = cleaned_data.get("contact_type")
        organization = cleaned_data.get("organization")
        use_org_address = cleaned_data.get("use_organization_address")

        if contact_type == ContactType.PERSON and use_org_address and not organization:
            self.add_error("organization", "Sélectionnez une société pour utiliser son adresse.")
        return cleaned_data

    def save(self, commit=True):
        return super().save(commit=commit)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    form = ContactAdminForm
    list_display = (
        "name",
        "contact_type",
        "organization",
        "email",
        "phone",
        "asf_id",
        "is_active",
    )
    list_filter = ("contact_type", "is_active")
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
