from django.test import TestCase
from django.urls import reverse

from wms.models import VolunteerAccountRequest, VolunteerAccountRequestStatus


class VolunteerAccountRequestViewTests(TestCase):
    def test_public_request_creates_pending_request(self):
        response = self.client.post(
            reverse("volunteer:request_account"),
            {
                "first_name": "Lou",
                "last_name": "Durand",
                "email": "lou@example.com",
                "phone": "+33601020304",
                "address_line1": "10 rue Test",
                "postal_code": "75001",
                "city": "Paris",
                "country": "France",
            },
        )

        self.assertRedirects(response, reverse("volunteer:request_account_done"))
        account_request = VolunteerAccountRequest.objects.get()
        self.assertEqual(account_request.status, VolunteerAccountRequestStatus.PENDING)
        self.assertEqual(account_request.first_name, "Lou")
        self.assertEqual(account_request.city, "Paris")

    def test_request_account_done_page_renders(self):
        response = self.client.get(reverse("volunteer:request_account_done"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Demande envoyee")
