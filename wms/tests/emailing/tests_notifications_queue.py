from unittest import mock

from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from contacts.models import Contact
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


class PublicOrderNotificationsQueueTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_superuser(
            username="queue-admin",
            email="admin@example.com",
            password="pass1234",
        )
        self.factory = RequestFactory()

    def test_send_public_order_notifications_queues_admin_and_confirmation(self):
        request = self.factory.get("/scan/public-order/")
        link = PublicOrderLink.objects.create(label="Test link")
        contact = Contact.objects.create(
            name="Association Dest",
            email="association@example.com",
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

        with mock.patch("wms.public_order_handlers.send_email_safe", return_value=False):
            send_public_order_notifications(
                request=request,
                token=link.token,
                order=order,
                form_data=form_data,
                contact=contact,
            )

        events = list(
            IntegrationEvent.objects.filter(
                direction=IntegrationDirection.OUTBOUND,
                source="wms.email",
                event_type="send_email",
                status=IntegrationStatus.PENDING,
            ).order_by("created_at")
        )
        self.assertEqual(len(events), 2)
        recipients = {tuple(event.payload.get("recipient", [])) for event in events}
        self.assertIn(("admin@example.com",), recipients)
        self.assertIn((contact.email,), recipients)

    def test_send_public_order_notifications_uses_public_admin_template(self):
        request = self.factory.get("/scan/public-order/")
        link = PublicOrderLink.objects.create(label="Template link")
        contact = Contact.objects.create(
            name="Association Template",
            email="template@example.com",
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

        with mock.patch(
            "wms.public_order_handlers.render_to_string",
            side_effect=["confirmation-body", "admin-body"],
        ) as render_mock:
            with mock.patch("wms.public_order_handlers.send_email_safe", return_value=False):
                with mock.patch(
                    "wms.public_order_handlers.enqueue_email_safe",
                    return_value=True,
                ):
                    send_public_order_notifications(
                        request=request,
                        token=link.token,
                        order=order,
                        form_data=form_data,
                        contact=contact,
                    )

        self.assertEqual(
            render_mock.call_args_list[0].args[0],
            "emails/order_confirmation.txt",
        )
        self.assertEqual(
            render_mock.call_args_list[1].args[0],
            "emails/order_admin_notification_public.txt",
        )

    def test_send_public_order_notifications_logs_when_admin_queue_fails(self):
        request = self.factory.get("/scan/public-order/")
        link = PublicOrderLink.objects.create(label="Failure link")
        contact = Contact.objects.create(
            name="Association Failure",
            email="failure@example.com",
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

        with mock.patch(
            "wms.public_order_handlers.render_to_string",
            side_effect=["confirmation-body", "admin-body"],
        ):
            with mock.patch("wms.public_order_handlers.send_email_safe", return_value=False):
                with mock.patch(
                    "wms.public_order_handlers.enqueue_email_safe",
                    side_effect=[False, True],
                ):
                    with mock.patch(
                        "wms.public_order_handlers.LOGGER.warning"
                    ) as warning_mock:
                        send_public_order_notifications(
                            request=request,
                            token=link.token,
                            order=order,
                            form_data=form_data,
                            contact=contact,
                        )

        warning_mock.assert_called_once()

    def test_send_public_order_notifications_includes_mail_order_group_recipients(self):
        grouped_staff = get_user_model().objects.create_user(
            username="public-order-group-staff",
            email="public-order-group@example.com",
            password="pass1234",
            is_staff=True,
        )
        Group.objects.get_or_create(name="Mail_Order_Staff")[0].user_set.add(grouped_staff)

        request = self.factory.get("/scan/public-order/")
        link = PublicOrderLink.objects.create(label="Group link")
        contact = Contact.objects.create(
            name="Association Group",
            email="association-group@example.com",
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

        with mock.patch("wms.public_order_handlers.send_email_safe", return_value=False):
            send_public_order_notifications(
                request=request,
                token=link.token,
                order=order,
                form_data=form_data,
                contact=contact,
            )

        admin_event = IntegrationEvent.objects.filter(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.PENDING,
            payload__subject="ASF WMS - Nouvelle commande publique",
        ).first()
        self.assertIsNotNone(admin_event)
        self.assertEqual(
            set(admin_event.payload.get("recipient", [])),
            {"admin@example.com", "public-order-group@example.com"},
        )

    def test_send_public_order_notifications_sends_direct_without_queue(self):
        request = self.factory.get("/scan/public-order/")
        link = PublicOrderLink.objects.create(label="Direct link")
        contact = Contact.objects.create(
            name="Association Direct",
            email="association-direct@example.com",
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

        with mock.patch("wms.public_order_handlers.send_email_safe", return_value=True):
            with mock.patch("wms.public_order_handlers.enqueue_email_safe") as enqueue_mock:
                send_public_order_notifications(
                    request=request,
                    token=link.token,
                    order=order,
                    form_data=form_data,
                    contact=contact,
                )

        self.assertEqual(
            IntegrationEvent.objects.filter(
                direction=IntegrationDirection.OUTBOUND,
                source="wms.email",
                event_type="send_email",
            ).count(),
            0,
        )
        enqueue_mock.assert_not_called()


class PortalOrderNotificationsQueueTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_superuser(
            username="portal-admin",
            email="admin@example.com",
            password="pass1234",
        )
        self.user = get_user_model().objects.create_user(
            username="portal-user",
            email="portal-user@example.com",
            password="pass1234",
        )
        self.contact = Contact.objects.create(
            name="Association Portal",
            email="association-portal@example.com",
            phone="+33999999999",
        )
        self.profile = AssociationProfile.objects.create(
            user=self.user,
            contact=self.contact,
            notification_emails="n1@example.com, n2@example.com",
        )
        self.order = Order.objects.create(
            association_contact=self.contact,
            shipper_name="Aviation Sans Frontieres",
            recipient_name="Association Portal",
            destination_address="10 Rue Test\n75000 Paris\nFrance",
            destination_country="France",
        )
        self.factory = RequestFactory()

    def test_send_portal_order_notifications_queues_admin_and_recipients(self):
        request = self.factory.get("/portal/orders/new/")
        request.user = self.user

        with mock.patch("wms.order_notifications.send_email_safe", return_value=False):
            send_portal_order_notifications(
                request=request,
                profile=self.profile,
                order=self.order,
            )

        events = list(
            IntegrationEvent.objects.filter(
                direction=IntegrationDirection.OUTBOUND,
                source="wms.email",
                event_type="send_email",
                status=IntegrationStatus.PENDING,
            ).order_by("created_at")
        )
        self.assertEqual(len(events), 2)

        payload_by_subject = {
            event.payload.get("subject"): event.payload for event in events
        }
        admin_payload = payload_by_subject.get("ASF WMS - Nouvelle commande")
        self.assertIsNotNone(admin_payload)
        self.assertEqual(admin_payload.get("recipient"), ["admin@example.com"])

        confirmation_payload = payload_by_subject.get("ASF WMS - Commande reçue")
        self.assertIsNotNone(confirmation_payload)
        self.assertEqual(
            confirmation_payload.get("recipient"),
            ["association-portal@example.com", "n1@example.com", "n2@example.com"],
        )

    def test_send_portal_order_notifications_falls_back_to_user_email_when_contact_missing(self):
        self.contact.email = ""
        self.contact.save(update_fields=["email"])

        request = self.factory.get("/portal/orders/new/")
        request.user = self.user

        with mock.patch("wms.order_notifications.send_email_safe", return_value=False):
            send_portal_order_notifications(
                request=request,
                profile=self.profile,
                order=self.order,
            )

        confirmation_event = IntegrationEvent.objects.filter(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.PENDING,
            payload__subject="ASF WMS - Commande reçue",
        ).first()

        self.assertIsNotNone(confirmation_event)
        self.assertEqual(
            confirmation_event.payload.get("recipient"),
            ["portal-user@example.com", "n1@example.com", "n2@example.com"],
        )

    def test_send_portal_order_notifications_uses_portal_admin_template(self):
        request = self.factory.get("/portal/orders/new/")
        request.user = self.user

        with mock.patch(
            "wms.order_notifications.render_to_string",
            side_effect=["admin-body", "confirmation-body"],
        ) as render_mock:
            with mock.patch("wms.order_notifications.send_email_safe", return_value=False):
                with mock.patch(
                    "wms.order_notifications.enqueue_email_safe",
                    return_value=True,
                ):
                    send_portal_order_notifications(
                        request=request,
                        profile=self.profile,
                        order=self.order,
                    )

        self.assertEqual(
            render_mock.call_args_list[0].args[0],
            "emails/order_admin_notification_portal.txt",
        )
        self.assertEqual(
            render_mock.call_args_list[1].args[0],
            "emails/order_confirmation.txt",
        )

    def test_send_portal_order_notifications_logs_when_queueing_fails(self):
        request = self.factory.get("/portal/orders/new/")
        request.user = self.user

        with mock.patch(
            "wms.order_notifications.render_to_string",
            side_effect=["admin-body", "confirmation-body"],
        ):
            with mock.patch("wms.order_notifications.send_email_safe", return_value=False):
                with mock.patch(
                    "wms.order_notifications.enqueue_email_safe",
                    side_effect=[False, False],
                ):
                    with mock.patch(
                        "wms.order_notifications.LOGGER.warning"
                    ) as warning_mock:
                        send_portal_order_notifications(
                            request=request,
                            profile=self.profile,
                            order=self.order,
                        )

        self.assertEqual(warning_mock.call_count, 2)

    def test_send_portal_order_notifications_includes_mail_order_group_recipients(self):
        grouped_staff = get_user_model().objects.create_user(
            username="portal-order-group-staff",
            email="portal-order-group@example.com",
            password="pass1234",
            is_staff=True,
        )
        Group.objects.get_or_create(name="Mail_Order_Staff")[0].user_set.add(grouped_staff)

        request = self.factory.get("/portal/orders/new/")
        request.user = self.user

        with mock.patch("wms.order_notifications.send_email_safe", return_value=False):
            send_portal_order_notifications(
                request=request,
                profile=self.profile,
                order=self.order,
            )

        admin_event = IntegrationEvent.objects.filter(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.PENDING,
            payload__subject="ASF WMS - Nouvelle commande",
        ).first()
        self.assertIsNotNone(admin_event)
        self.assertEqual(
            set(admin_event.payload.get("recipient", [])),
            {"admin@example.com", "portal-order-group@example.com"},
        )

    def test_send_portal_order_notifications_sends_direct_without_queue(self):
        request = self.factory.get("/portal/orders/new/")
        request.user = self.user

        with mock.patch("wms.order_notifications.send_email_safe", return_value=True):
            with mock.patch("wms.order_notifications.enqueue_email_safe") as enqueue_mock:
                send_portal_order_notifications(
                    request=request,
                    profile=self.profile,
                    order=self.order,
                )

        self.assertEqual(
            IntegrationEvent.objects.filter(
                direction=IntegrationDirection.OUTBOUND,
                source="wms.email",
                event_type="send_email",
            ).count(),
            0,
        )
        enqueue_mock.assert_not_called()
