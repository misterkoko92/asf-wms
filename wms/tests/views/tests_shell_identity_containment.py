from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.urls import reverse

PROBE_PRODUCT = "WHITELABEL_PROBE_PRODUCT"
PROBE_BRAND = "WHITELABEL_PROBE_BRAND"


@override_settings(
    PRODUCT_DISPLAY_NAME=PROBE_PRODUCT,
    ORG_BRAND_NAME=PROBE_BRAND,
)
class ShellIdentityContainmentTests(TestCase):
    def assertProbeValuesAbsent(self, rendered):
        self.assertNotIn(PROBE_PRODUCT, rendered)
        self.assertNotIn(PROBE_BRAND, rendered)

    def test_probe_identity_values_do_not_leak_into_email_template(self):
        rendered = render_to_string(
            "emails/order_confirmation.txt",
            {
                "association_name": "Association Test",
                "order_reference": "ORD-001",
                "summary_url": "https://example.invalid/summary.pdf",
            },
        )

        self.assertProbeValuesAbsent(rendered)

    def test_probe_identity_values_do_not_leak_into_print_template(self):
        rendered = render_to_string(
            "print/partials/shipment_note_body.html",
            {
                "shipment_ref": "SHP-001",
                "destination_address": "Destination Test",
                "carton_count": 1,
                "shipper_info": {},
                "recipient_info": {},
                "correspondent_info": {},
            },
        )

        self.assertProbeValuesAbsent(rendered)

    def test_probe_identity_values_do_not_leak_into_scan_base_render(self):
        user = get_user_model().objects.create_user(
            username="scan-containment",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        self.assertProbeValuesAbsent(response.content.decode())
