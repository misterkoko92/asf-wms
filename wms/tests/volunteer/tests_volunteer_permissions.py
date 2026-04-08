from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import NoReverseMatch

from wms.models import VolunteerProfile
from wms.view_permissions import volunteer_required


class VolunteerPermissionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, user):
        request = self.factory.get("/benevole/")
        request.user = user
        return request

    def test_volunteer_required_rejects_user_without_profile(self):
        user = get_user_model().objects.create_user(
            username="plain@example.com",
            email="plain@example.com",
            password="pass1234",  # pragma: allowlist secret
        )

        @volunteer_required
        def sample_view(request):
            return HttpResponse("ok")

        with self.assertRaises(PermissionDenied):
            sample_view(self._request(user))

    def test_volunteer_required_rejects_inactive_profile(self):
        user = get_user_model().objects.create_user(
            username="inactive@example.com",
            email="inactive@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        VolunteerProfile.objects.create(user=user, is_active=False)

        @volunteer_required
        def sample_view(request):
            return HttpResponse("ok")

        with self.assertRaises(PermissionDenied):
            sample_view(self._request(user))

    def test_volunteer_required_allows_active_profile(self):
        user = get_user_model().objects.create_user(
            username="active@example.com",
            email="active@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        profile = VolunteerProfile.objects.create(user=user, is_active=True)

        @volunteer_required
        def sample_view(request):
            return HttpResponse("ok")

        request = self._request(user)
        response = sample_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.volunteer_profile, profile)

    def test_volunteer_required_redirects_to_password_change_when_needed(self):
        user = get_user_model().objects.create_user(
            username="change-password@example.com",
            email="change-password@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        VolunteerProfile.objects.create(
            user=user,
            is_active=True,
            must_change_password=True,
        )

        @volunteer_required
        def sample_view(request):
            return HttpResponse("ok")

        response = sample_view(self._request(user))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/benevole/change-password/")

    def test_volunteer_required_allows_request_when_password_change_route_is_missing(self):
        user = get_user_model().objects.create_user(
            username="missing-route@example.com",
            email="missing-route@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        profile = VolunteerProfile.objects.create(
            user=user,
            is_active=True,
            must_change_password=True,
        )

        @volunteer_required
        def sample_view(request):
            return HttpResponse("ok")

        with mock.patch("wms.view_permissions.reverse", side_effect=NoReverseMatch):
            request = self._request(user)
            response = sample_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.volunteer_profile, profile)
