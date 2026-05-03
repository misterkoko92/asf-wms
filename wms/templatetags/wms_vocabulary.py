from django import template

from wms.config import get_installation_config

register = template.Library()


@register.simple_tag
def portal_partner_label():
    return get_installation_config().vocabulary.portal_partner_label
