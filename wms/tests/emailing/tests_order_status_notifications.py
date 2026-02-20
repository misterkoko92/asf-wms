from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact
from wms.models import (
    AssociationProfile,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    Order,
    OrderReviewStatus,
    OrderStatus,
)


class OrderStatusSignalEmailQueueTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_superuser(
            username="order-status-admin",
            email="admin@example.com",
            password="pass1234",
        )
        self.association_contact = Contact.objects.create(
            name="Association Commande",
            email="association@example.com",
        )
        self.order = Order.objects.create(
            association_contact=self.association_contact,
            shipper_name="Association Commande",
            recipient_name="Destinataire",
            destination_address="10 Rue Test\n75000 Paris\nFrance",
            destination_country="France",
        )

    def test_review_status_change_queues_notification_to_admin_and_association(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.order.review_status = OrderReviewStatus.APPROVED
            self.order.save(update_fields=["review_status"])

        event = IntegrationEvent.objects.filter(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.PENDING,
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(
            set(event.payload.get("recipient", [])),
            {"admin@example.com", "association@example.com"},
        )
        self.assertIn("validation/statut mis à jour", event.payload.get("subject", ""))

    def test_order_status_change_queues_notification_to_admin_and_association(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.order.status = OrderStatus.RESERVED
            self.order.save(update_fields=["status"])

        event = IntegrationEvent.objects.filter(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.PENDING,
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(
            set(event.payload.get("recipient", [])),
            {"admin@example.com", "association@example.com"},
        )
        self.assertIn("validation/statut mis à jour", event.payload.get("subject", ""))

    def test_order_status_change_includes_association_profile_emails(self):
        profile_user = get_user_model().objects.create_user(
            username="association-portal-user",
            email="portal-user@example.com",
            password="pass1234",
        )
        AssociationProfile.objects.create(
            user=profile_user,
            contact=self.association_contact,
            notification_emails="notify-1@example.com,notify-2@example.com",
        )

        with self.captureOnCommitCallbacks(execute=True):
            self.order.status = OrderStatus.RESERVED
            self.order.save(update_fields=["status"])

        event = IntegrationEvent.objects.filter(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.PENDING,
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(
            set(event.payload.get("recipient", [])),
            {
                "admin@example.com",
                "association@example.com",
                "portal-user@example.com",
                "notify-1@example.com",
                "notify-2@example.com",
            },
        )
