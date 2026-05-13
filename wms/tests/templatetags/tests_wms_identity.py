from types import SimpleNamespace
from unittest import mock

from django.template import Context, Template
from django.test import SimpleTestCase


class WmsIdentityTemplateTagTests(SimpleTestCase):
    def test_identity_tags_return_configured_shell_identity_values(self):
        installation = SimpleNamespace(
            identity=SimpleNamespace(
                product_display_name="Client Operations",
                organization_brand_name="ClientOrg",
            )
        )

        with mock.patch(
            "wms.templatetags.wms_identity.get_installation_config",
            return_value=installation,
        ) as config_mock:
            rendered = Template(
                "{% load wms_identity %}" "{% product_display_name %}|{% organization_brand_name %}"
            ).render(Context())

        self.assertEqual(rendered, "Client Operations|ClientOrg")
        self.assertEqual(config_mock.call_count, 2)
