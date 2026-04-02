from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.application.portal.dashboard_queries import build_portal_dashboard_payload
from wms.models import AssociationProfile, Order, OrderReviewStatus


class PortalDashboardQueriesTests(TestCase):
    def test_build_portal_dashboard_payload_exposes_rows_and_kpis(self):
        user = get_user_model().objects.create(username="portal-dashboard-query-user")
        contact = Contact.objects.create(
            name="Association Query",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        profile = AssociationProfile.objects.create(user=user, contact=contact)
        Order.objects.create(
            association_contact=contact,
            review_status=OrderReviewStatus.PENDING,
            shipper_name="ASF",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )

        payload = build_portal_dashboard_payload(profile=profile)

        self.assertIn("dashboard_kpis", payload)
        self.assertIn("orders", payload)
        self.assertIn("order_rows", payload)
