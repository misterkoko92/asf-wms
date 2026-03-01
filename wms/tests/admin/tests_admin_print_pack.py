from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class PrintPackAdminTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="admin-print-pack",
            email="admin-print-pack@example.com",
            password="pass1234",
        )
        self.client.force_login(self.superuser)

    def test_print_pack_admin_changelist_is_available(self):
        response = self.client.get(reverse("admin:wms_printpack_changelist"))
        self.assertEqual(response.status_code, 200)
