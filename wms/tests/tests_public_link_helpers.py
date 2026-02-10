from datetime import timedelta
from uuid import uuid4

from django.http import Http404
from django.test import TestCase
from django.utils import timezone

from wms.models import PublicOrderLink
from wms.public_link_helpers import get_active_public_order_link_or_404


class PublicLinkHelpersTests(TestCase):
    def test_get_active_public_order_link_or_404_returns_active_link(self):
        token = uuid4()
        link = PublicOrderLink.objects.create(
            token=token,
            label="Active",
            is_active=True,
            expires_at=timezone.now() + timedelta(days=1),
        )

        resolved = get_active_public_order_link_or_404(token)

        self.assertEqual(resolved.id, link.id)

    def test_get_active_public_order_link_or_404_raises_for_missing_link(self):
        with self.assertRaises(Http404):
            get_active_public_order_link_or_404(uuid4())

    def test_get_active_public_order_link_or_404_raises_for_expired_link(self):
        token = uuid4()
        PublicOrderLink.objects.create(
            token=token,
            label="Expired",
            is_active=True,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        with self.assertRaises(Http404):
            get_active_public_order_link_or_404(token)

    def test_get_active_public_order_link_or_404_raises_for_inactive_link(self):
        token = uuid4()
        PublicOrderLink.objects.create(
            token=token,
            label="Inactive",
            is_active=False,
            expires_at=timezone.now() + timedelta(days=1),
        )

        with self.assertRaises(Http404):
            get_active_public_order_link_or_404(token)
