from django import template

from wms.config import get_installation_config

register = template.Library()


@register.simple_tag
def product_display_name():
    return get_installation_config().identity.product_display_name


@register.simple_tag
def organization_brand_name():
    return get_installation_config().identity.organization_brand_name
