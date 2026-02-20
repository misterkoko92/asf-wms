from unittest import mock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from contacts.models import Contact
from wms.emailing import process_email_queue
from wms.models import (
    AssociationProfile,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    Order,
    PublicOrderLink,
)
from wms.order_notifications import send_portal_order_notifications
from wms.public_order_handlers import send_public_order_notifications


class EmailFlowsEndToEndTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_superuser(
            username="mail-admin",
            email="admin@example.com",
            password="pass1234",
        )
        self.factory = RequestFactory()

    def _email_events_queryset(self):
        return IntegrationEvent.objects.filter(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
        )

    def test_public_order_notifications_end_to_end(self):
        request = self.factory.get("/scan/public-order/")
        link = PublicOrderLink.objects.create(label="Public E2E")
        contact = Contact.objects.create(
            name="Association Public E2E",
            email="public-e2e@example.com",
            phone="+33123456789",
        )
        order = Order.objects.create(
            public_link=link,
            recipient_contact=contact,
            shipper_name="Aviation Sans Frontieres",
            recipient_name=contact.name,
            destination_address="10 Rue Test\n75000 Paris\nFrance",
            destination_country="France",
        )
        form_data = {
            "association_name": contact.name,
            "association_email": contact.email,
            "association_phone": contact.phone,
        }

        send_public_order_notifications(
            request=request,
            token=link.token,
            order=order,
            form_data=form_data,
            contact=contact,
        )
        self.assertEqual(
            self._email_events_queryset().filter(status=IntegrationStatus.PENDING).count(),
            2,
        )

        with mock.patch("wms.emailing.send_email_safe", return_value=True):
            result = process_email_queue(limit=10)

        self.assertEqual(result["selected"], 2)
        self.assertEqual(result["processed"], 2)
        self.assertEqual(
            self._email_events_queryset().filter(status=IntegrationStatus.PROCESSED).count(),
            2,
        )

    def test_portal_order_notifications_end_to_end(self):
        user = get_user_model().objects.create_user(
            username="portal-e2e",
            email="portal-e2e@example.com",
            password="pass1234",
        )
        contact = Contact.objects.create(
            name="Association Portal E2E",
            email="portal-contact@example.com",
            phone="+33999999999",
        )
        profile = AssociationProfile.objects.create(
            user=user,
            contact=contact,
            notification_emails="n1@example.com, n2@example.com",
        )
        order = Order.objects.create(
            association_contact=contact,
            shipper_name="Aviation Sans Frontieres",
            recipient_name=contact.name,
            destination_address="10 Rue Test\n75000 Paris\nFrance",
            destination_country="France",
        )
        request = self.factory.get("/portal/orders/new/")
        request.user = user

        send_portal_order_notifications(
            request=request,
            profile=profile,
            order=order,
        )
        self.assertEqual(
            self._email_events_queryset().filter(status=IntegrationStatus.PENDING).count(),
            2,
        )

        with mock.patch("wms.emailing.send_email_safe", return_value=True):
            result = process_email_queue(limit=10)

        self.assertEqual(result["selected"], 2)
        self.assertEqual(result["processed"], 2)
        self.assertEqual(
            self._email_events_queryset().filter(status=IntegrationStatus.PROCESSED).count(),
            2,
        )

    @override_settings(ACCOUNT_REQUEST_THROTTLE_SECONDS=0)
    def test_account_request_flow_end_to_end(self):
        payload = {
            "association_name": "Association Account E2E",
            "email": "account-e2e@example.com",
            "phone": "0102030405",
            "line1": "1 Rue Test",
            "line2": "",
            "postal_code": "75001",
            "city": "Paris",
            "country": "France",
            "notes": "Demande E2E",
            "contact_id": "",
        }

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("portal:portal_account_request"), payload)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self._email_events_queryset().filter(status=IntegrationStatus.PENDING).count(),
            2,
        )

        with mock.patch("wms.emailing.send_email_safe", return_value=True):
            result = process_email_queue(limit=10)

        self.assertEqual(result["selected"], 2)
        self.assertEqual(result["processed"], 2)
        self.assertEqual(
            self._email_events_queryset().filter(status=IntegrationStatus.PROCESSED).count(),
            2,
        )
