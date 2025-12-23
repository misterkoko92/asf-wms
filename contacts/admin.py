from django.contrib import admin

from .models import Contact, ContactAddress, ContactTag


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


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_type", "email", "phone", "is_active")
    list_filter = ("contact_type", "is_active", "tags")
    search_fields = ("name", "email", "phone")
    filter_horizontal = ("tags",)
    inlines = [ContactAddressInline]


@admin.register(ContactTag)
class ContactTagAdmin(admin.ModelAdmin):
    search_fields = ("name",)

# Register your models here.
