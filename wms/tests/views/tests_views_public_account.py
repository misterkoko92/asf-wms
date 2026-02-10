from datetime import timedelta
from unittest import mock
from uuid import uuid4

from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from wms.models import PublicOrderLink


class PublicAccountRequestViewTests(TestCase):
    def test_scan_public_account_request_delegates_for_active_link(self):
        link = PublicOrderLink.objects.create(
            label="Active",
            is_active=True,
            expires_at=timezone.now() + timedelta(days=1),
        )
        url = reverse("scan:scan_public_account_request", args=[link.token])
        with mock.patch(
            "wms.views_public_account.handle_account_request_form",
            return_value=HttpResponse("ok"),
        ) as handler_mock:
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "ok")
        handler_mock.assert_called_once_with(
            mock.ANY,
            link=link,
            redirect_url=url,
        )

    def test_scan_public_account_request_returns_404_for_expired_link(self):
        link = PublicOrderLink.objects.create(
            label="Expired",
            is_active=True,
            expires_at=timezone.now() - timedelta(days=1),
        )

        response = self.client.get(
            reverse("scan:scan_public_account_request", args=[link.token])
        )

        self.assertEqual(response.status_code, 404)

    def test_scan_public_account_request_returns_404_for_missing_link(self):
        response = self.client.get(
            reverse("scan:scan_public_account_request", args=[uuid4()])
        )
        self.assertEqual(response.status_code, 404)

    def test_scan_public_account_request_returns_404_for_inactive_link(self):
        link = PublicOrderLink.objects.create(
            label="Inactive",
            is_active=False,
        )

        response = self.client.get(
            reverse("scan:scan_public_account_request", args=[link.token])
        )

        self.assertEqual(response.status_code, 404)
