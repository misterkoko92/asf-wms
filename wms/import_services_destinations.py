import re

from django.db.models import Q

from contacts.models import Contact, ContactTag, ContactType

from .contact_filters import TAG_CORRESPONDENT
from .models import Destination

DESTINATION_LABEL_RE = re.compile(
    r"^(?P<city>.+?)\s*\((?P<iata>[^)]+)\)\s*(?:-\s*(?P<country>.+))?$"
)
DESTINATION_IATA_FALLBACK = "DEST"
DEFAULT_DESTINATION_COUNTRY = "France"
DEFAULT_CORRESPONDENT_NAME = "Correspondant par defaut"
DEFAULT_CORRESPONDENT_NOTES = "cree a l'import destination"


def _normalize_label_value(value):
    if value is None:
        return ""
    return str(value).strip()


def _parse_destination_label(value):
    text = _normalize_label_value(value)
    if not text:
        return None, None, None
    match = DESTINATION_LABEL_RE.match(text)
    if match:
        city = (match.group("city") or "").strip()
        iata = (match.group("iata") or "").strip()
        country = (match.group("country") or "").strip()
        return city or None, iata or None, country or None
    if " - " in text:
        parts = [part.strip() for part in text.split(" - ") if part.strip()]
        if len(parts) >= 2:
            return parts[0], None, parts[1]
    if re.fullmatch(r"[A-Za-z0-9]{2,10}", text):
        return None, text, None
    return text, None, None


def _generate_destination_code(base):
    cleaned = re.sub(r"[^A-Za-z0-9]", "", base or "").upper()
    cleaned = cleaned[:10]
    if not cleaned:
        cleaned = DESTINATION_IATA_FALLBACK
    candidate = cleaned
    suffix = 1
    while Destination.objects.filter(iata_code__iexact=candidate).exists():
        suffix += 1
        trimmed = cleaned[: max(1, 10 - len(str(suffix)))]
        candidate = f"{trimmed}{suffix}"
    return candidate


def _tags_include_correspondent(tags):
    if not tags:
        return False
    tag_names = {tag.name.strip().lower() for tag in tags if tag.name}
    return any(name in tag_names for name in TAG_CORRESPONDENT)


def _select_default_correspondent():
    tag_query = Q()
    for name in TAG_CORRESPONDENT:
        tag_query |= Q(tags__name__iexact=name)
    correspondent = (
        Contact.objects.filter(is_active=True).filter(tag_query).distinct().first()
    )
    if correspondent:
        return correspondent
    tag, _ = ContactTag.objects.get_or_create(name=TAG_CORRESPONDENT[0])
    correspondent, _ = Contact.objects.get_or_create(
        name=DEFAULT_CORRESPONDENT_NAME,
        contact_type=ContactType.ORGANIZATION,
        defaults={"notes": DEFAULT_CORRESPONDENT_NOTES},
    )
    correspondent.tags.add(tag)
    return correspondent


def _find_destination_by_iata(iata_code):
    if not iata_code:
        return None
    return Destination.objects.filter(iata_code__iexact=iata_code).first()


def _find_destination_by_city(*, city, country=None):
    if not city:
        return None
    query = Destination.objects.filter(city__iexact=city)
    if country:
        return query.filter(country__iexact=country).first()
    if query.count() == 1:
        return query.first()
    return None


def _find_existing_destination(*, city, country):
    return Destination.objects.filter(
        city__iexact=city,
        country__iexact=country,
    ).first()


def _resolve_destination_correspondent(*, contact, tags):
    if contact and _tags_include_correspondent(tags or contact.tags.all()):
        return contact
    return _select_default_correspondent()


def _get_or_create_destination(
    raw_value,
    *,
    contact=None,
    tags=None,
    fallback_city=None,
    fallback_country=None,
):
    if not raw_value:
        return None
    city, iata_code, country = _parse_destination_label(raw_value)
    destination = _find_destination_by_iata(iata_code)
    if destination is None:
        destination = _find_destination_by_city(
            city=city,
            country=country or fallback_country,
        )
    if destination:
        return destination
    resolved_city = city or fallback_city or _normalize_label_value(raw_value)
    resolved_country = country or fallback_country or DEFAULT_DESTINATION_COUNTRY
    existing = _find_existing_destination(city=resolved_city, country=resolved_country)
    if existing:
        return existing
    resolved_iata = iata_code or _generate_destination_code(resolved_city)
    correspondent = _resolve_destination_correspondent(contact=contact, tags=tags)
    return Destination.objects.create(
        city=resolved_city,
        iata_code=resolved_iata,
        country=resolved_country,
        correspondent_contact=correspondent,
    )
