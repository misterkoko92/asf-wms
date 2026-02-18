from django import forms
from django.contrib import admin

from wms.models import Destination

from .models import Contact, ContactAddress, ContactTag, ContactType
from .querysets import contacts_with_tags
from .rules import (
    ensure_default_shipper_for_recipient,
    get_default_recipient_shipper,
    validate_recipient_links_for_creation,
)
from .tagging import TAG_SHIPPER


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
            "Utilise l'adresse par défaut de la société et se met à jour automatiquement."
        )
        self.fields["destinations"].help_text = (
            "Sélection multiple. Vide = toutes les destinations."
        )
        self.fields["linked_shippers"].queryset = contacts_with_tags(TAG_SHIPPER)
        self.fields["linked_shippers"].help_text = (
            "Sélection multiple pour les destinataires. Obligatoire à la création."
        )
        if not self.instance.pk and not self.is_bound:
            default_shipper = get_default_recipient_shipper()
            if default_shipper:
                self.fields["linked_shippers"].initial = [default_shipper.pk]

    def clean(self):
        cleaned_data = super().clean()
        contact_type = cleaned_data.get("contact_type")
        tags = cleaned_data.get("tags")
        organization = cleaned_data.get("organization")
        use_org_address = cleaned_data.get("use_organization_address")
        linked_shippers = cleaned_data.get("linked_shippers")

        if contact_type == ContactType.ORGANIZATION and not tags:
            self.add_error("tags", "Au moins un tag est requis pour une société.")
        if contact_type == ContactType.PERSON and use_org_address and not organization:
            self.add_error(
                "organization", "Sélectionnez une société pour utiliser son adresse."
            )
        recipient_links_error = validate_recipient_links_for_creation(
            is_creation=not self.instance.pk,
            tags=tags,
            linked_shippers=linked_shippers,
        )
        if recipient_links_error:
            self.add_error("linked_shippers", recipient_links_error)
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            self._ensure_default_shipper_for_recipient(instance)
        else:
            base_save_m2m = self.save_m2m

            def save_m2m_with_default():
                base_save_m2m()
                self._ensure_default_shipper_for_recipient(self.instance)

            self.save_m2m = save_m2m_with_default
        return instance

    def _ensure_default_shipper_for_recipient(self, instance):
        if not hasattr(self, "cleaned_data"):
            return
        ensure_default_shipper_for_recipient(
            instance,
            tags=self.cleaned_data.get("tags"),
        )


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
    exclude = ("destination",)
    list_display = (
        "name",
        "contact_type",
        "organization",
        "destinations_display",
        "email",
        "phone",
        "asf_id",
        "is_active",
    )
    list_filter = ("contact_type", "is_active", "tags", "destinations")
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
    filter_horizontal = ("tags", "destinations", "linked_shippers")
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
                    "destinations",
                    "siret",
                    "vat_number",
                    "legal_registration_number",
                    "asf_id",
                    "tags",
                    "linked_shippers",
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

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "destination":
            kwargs["queryset"] = Destination.objects.filter(is_active=True)
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "destination":
            field.widget.can_add_related = False
            field.widget.can_change_related = False
            field.widget.can_delete_related = False
        return field

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "destinations":
            kwargs["queryset"] = Destination.objects.filter(is_active=True).order_by("city")
        if db_field.name == "linked_shippers":
            kwargs["queryset"] = contacts_with_tags(TAG_SHIPPER)
        field = super().formfield_for_manytomany(db_field, request, **kwargs)
        if db_field.name in {"destinations", "linked_shippers"}:
            field.widget.can_add_related = False
            field.widget.can_change_related = False
            field.widget.can_delete_related = False
        return field

    @admin.display(description="Destinations")
    def destinations_display(self, obj):
        names = list(obj.destinations.values_list("city", flat=True)[:3])
        if not names:
            return "Global"
        suffix = "…" if obj.destinations.count() > 3 else ""
        return ", ".join(names) + suffix

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
