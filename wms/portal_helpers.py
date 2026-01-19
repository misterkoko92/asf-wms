from django.conf import settings

from .models import AssociationProfile, CartonFormat


def build_destination_address(*, line1, line2, postal_code, city, country):
    parts = [line1, line2]
    city_line = " ".join(part for part in [postal_code, city] if part)
    if city_line:
        parts.append(city_line)
    if country:
        parts.append(country)
    return "\n".join(part for part in parts if part)


def get_contact_address(contact):
    if not contact:
        return None
    if hasattr(contact, "get_effective_address"):
        return contact.get_effective_address()
    return contact.addresses.filter(is_default=True).first() or contact.addresses.first()


def get_association_profile(user):
    if not user or not user.is_authenticated:
        return None
    return (
        AssociationProfile.objects.select_related("contact")
        .filter(user=user)
        .first()
    )


def get_default_carton_format():
    return (
        CartonFormat.objects.filter(is_default=True).first()
        or CartonFormat.objects.order_by("name").first()
    )


def build_public_base_url(request):
    base = settings.SITE_BASE_URL
    if base:
        return base.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")
