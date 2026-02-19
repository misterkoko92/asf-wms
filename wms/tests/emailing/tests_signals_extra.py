from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from wms.signals import (
    _build_site_url,
    _notify_shipment_status_change,
    _notify_tracking_event,
)


class SignalsExtraTests(SimpleTestCase):
    @override_settings(SITE_BASE_URL="example.org/base/")
    def test_build_site_url_adds_https_prefix_when_missing_scheme(self):
        self.assertEqual(_build_site_url("/admin/shipment/1"), "https://example.org/base/admin/shipment/1")

    def test_notify_shipment_status_change_falls_back_for_unknown_status_codes(self):
        instance = SimpleNamespace(
            _previous_status="legacy_old",
            status="legacy_new",
            reference="SHP-001",
            id=1,
            destination=None,
            destination_address="1 Rue Test",
            get_tracking_url=lambda: "/track/SHP-001",
        )

        with mock.patch("wms.signals.get_admin_emails", return_value=["admin@example.com"]):
            with mock.patch("wms.signals.reverse", return_value="/admin/url/"):
                with mock.patch("wms.signals.render_to_string", return_value="body") as render_mock:
                    with mock.patch("wms.signals.enqueue_email_safe") as enqueue_mock:
                        with mock.patch(
                            "wms.signals.transaction.on_commit",
                            side_effect=lambda callback: callback(),
                        ):
                            _notify_shipment_status_change(None, instance, created=False)

        enqueue_mock.assert_called_once()
        context = render_mock.call_args.args[1]
        self.assertEqual(context["old_status"], "legacy_old")
        self.assertEqual(context["new_status"], "legacy_new")

    def test_notify_shipment_status_change_returns_when_previous_status_missing(self):
        instance = SimpleNamespace(_previous_status=None, status="draft")
        with mock.patch("wms.signals.get_admin_emails") as emails_mock:
            _notify_shipment_status_change(None, instance, created=False)
        emails_mock.assert_not_called()

    def test_notify_shipment_status_change_returns_when_no_recipients(self):
        instance = SimpleNamespace(
            _previous_status="draft",
            status="packed",
            id=1,
            reference="SHP-002",
            destination=None,
            destination_address="1 Rue Test",
            get_tracking_url=lambda: "/track/SHP-002",
        )
        with mock.patch("wms.signals.get_admin_emails", return_value=[]):
            with mock.patch("wms.signals.render_to_string") as render_mock:
                _notify_shipment_status_change(None, instance, created=False)
        render_mock.assert_not_called()

    def test_notify_shipment_status_change_emits_structured_log(self):
        instance = SimpleNamespace(
            _previous_status="draft",
            status="packed",
            reference="SHP-003",
            id=3,
            destination=None,
            destination_address="1 Rue Test",
            get_tracking_url=lambda: "/track/SHP-003",
        )
        with mock.patch("wms.signals.log_shipment_status_transition") as log_mock:
            with mock.patch("wms.signals.get_admin_emails", return_value=[]):
                _notify_shipment_status_change(None, instance, created=False)
        log_mock.assert_called_once_with(
            shipment=instance,
            previous_status="draft",
            new_status="packed",
            source="shipment_post_save_signal",
        )

    def test_notify_tracking_event_ignorés_non_created_events(self):
        with mock.patch("wms.signals.get_admin_emails") as emails_mock:
            _notify_tracking_event(None, SimpleNamespace(), created=False)
        emails_mock.assert_not_called()

    def test_notify_tracking_event_returns_when_no_recipients(self):
        fake_event = SimpleNamespace(shipment=SimpleNamespace(id=1))
        with mock.patch("wms.signals.get_admin_emails", return_value=[]):
            with mock.patch("wms.signals.render_to_string") as render_mock:
                _notify_tracking_event(None, fake_event, created=True)
        render_mock.assert_not_called()

    def test_notify_tracking_event_emits_structured_log(self):
        fake_event = SimpleNamespace(
            shipment=SimpleNamespace(id=1),
            created_by=None,
        )
        with mock.patch("wms.signals.log_shipment_tracking_event") as log_mock:
            with mock.patch("wms.signals.get_admin_emails", return_value=[]):
                _notify_tracking_event(None, fake_event, created=True)
        log_mock.assert_called_once_with(
            tracking_event=fake_event,
            user=None,
        )
