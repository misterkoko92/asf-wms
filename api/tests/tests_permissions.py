from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIClient

from api.v1.permissions import has_integration_key


@override_settings(INTEGRATION_API_KEY="test-key")
class IntegrationPermissionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(
            username="integration-user",
            password="pass1234",
        )
        self.staff_user = get_user_model().objects.create_user(
            username="integration-staff",
            password="pass1234",
            is_staff=True,
        )

    def test_has_integration_key_trims_header_and_handles_empty_setting(self):
        request = self.factory.get(
            "/",
            HTTP_X_ASF_INTEGRATION_KEY=" test-key ",
        )
        self.assertTrue(has_integration_key(request))

        with override_settings(INTEGRATION_API_KEY="  "):
            self.assertFalse(has_integration_key(request))

    def test_product_endpoint_requires_auth_or_key(self):
        client = APIClient()
        response = client.get("/api/v1/products/")
        self.assertEqual(response.status_code, 403)

    def test_product_endpoint_allows_integration_key_without_auth(self):
        client = APIClient()
        response = client.get(
            "/api/v1/products/",
            HTTP_X_ASF_INTEGRATION_KEY="test-key",
        )
        self.assertEqual(response.status_code, 200)

    def test_product_endpoint_allows_authenticated_user_without_key(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get("/api/v1/products/")
        self.assertEqual(response.status_code, 200)

    def test_integration_endpoint_requires_staff_without_key(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get("/api/v1/integrations/shipments/")
        self.assertEqual(response.status_code, 403)

    def test_integration_endpoint_allows_staff_without_key(self):
        client = APIClient()
        client.force_authenticate(self.staff_user)
        response = client.get("/api/v1/integrations/shipments/")
        self.assertEqual(response.status_code, 200)

    def test_integration_endpoint_allows_integration_key_without_auth(self):
        client = APIClient()
        response = client.get(
            "/api/v1/integrations/shipments/",
            HTTP_X_ASF_INTEGRATION_KEY="test-key",
        )
        self.assertEqual(response.status_code, 200)
