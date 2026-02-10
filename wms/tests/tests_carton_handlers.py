from django.test import RequestFactory, TestCase

from wms.carton_handlers import handle_carton_status_update
from wms.models import Carton, CartonStatus


class CartonHandlersTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_handle_carton_status_update_returns_none_for_non_post_or_other_action(self):
        get_request = self.factory.get("/scan/cartons-ready")
        post_request = self.factory.post(
            "/scan/cartons-ready",
            {"action": "other_action"},
        )

        self.assertIsNone(handle_carton_status_update(get_request))
        self.assertIsNone(handle_carton_status_update(post_request))

    def test_handle_carton_status_update_updates_allowed_unassigned_carton(self):
        carton = Carton.objects.create(code="CT-HANDLER-1", status=CartonStatus.PICKING)
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "action": "update_carton_status",
                "carton_id": str(carton.id),
                "status": CartonStatus.PACKED,
            },
        )

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        carton.refresh_from_db()
        self.assertEqual(carton.status, CartonStatus.PACKED)
