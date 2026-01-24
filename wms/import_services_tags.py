from contacts.models import ContactTag

from .import_utils import parse_tokens
from .models import ProductTag

def build_product_tags(raw_value):
    names = parse_tokens(raw_value)
    tags = []
    for name in names:
        tag, _ = ProductTag.objects.get_or_create(name=name)
        tags.append(tag)
    return tags


def build_contact_tags(raw_value):
    names = parse_tokens(raw_value)
    tags = []
    for name in names:
        tag, _ = ContactTag.objects.get_or_create(name=name)
        tags.append(tag)
    return tags
