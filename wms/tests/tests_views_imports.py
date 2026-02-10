import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import reverse


class ScanImportViewTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="import-superuser",
            email="import-superuser@example.com",
            password="pass1234",
        )
        self.staff_user = get_user_model().objects.create_user(
            username="import-staff",
            password="pass1234",
            is_staff=True,
        )
        self.url = reverse("scan:scan_import")

    def test_scan_import_requires_superuser(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_scan_import_get_renders_with_pending_import(self):
        self.client.force_login(self.superuser)
        session = self.client.session
        session["product_import_pending"] = {"token": "abc"}
        session.save()

        with mock.patch(
            "wms.views_imports.render_scan_import",
            return_value=HttpResponse("rendered"),
        ) as render_mock:
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "rendered")
        render_mock.assert_called_once()
        self.assertEqual(render_mock.call_args.args[1], {"token": "abc"})

    def test_scan_import_get_export_returns_handler_response(self):
        self.client.force_login(self.superuser)
        handler = mock.Mock(return_value=HttpResponse("export"))
        with mock.patch.dict(
            "wms.views_imports.EXPORT_HANDLERS",
            {"products": handler},
            clear=False,
        ):
            response = self.client.get(f"{self.url}?export=products")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "export")
        handler.assert_called_once()

    def test_scan_import_get_export_unknown_returns_404(self):
        self.client.force_login(self.superuser)
        response = self.client.get(f"{self.url}?export=missing")
        self.assertEqual(response.status_code, 404)

    @override_settings(IMPORT_DEFAULT_PASSWORD="TempPwd!")
    def test_scan_import_post_uses_handler_response(self):
        self.client.force_login(self.superuser)
        with mock.patch(
            "wms.views_imports.handle_scan_import_action",
            return_value=HttpResponse("handled"),
        ) as handler_mock:
            response = self.client.post(self.url, {"action": "x"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "handled")
        self.assertEqual(handler_mock.call_count, 1)
        self.assertEqual(handler_mock.call_args.kwargs["default_password"], "TempPwd!")
        self.assertTrue(callable(handler_mock.call_args.kwargs["clear_pending_import"]))

    def test_scan_import_post_falls_back_to_render_when_handler_returns_none(self):
        self.client.force_login(self.superuser)
        with mock.patch(
            "wms.views_imports.handle_scan_import_action",
            return_value=None,
        ) as handler_mock:
            with mock.patch(
                "wms.views_imports.render_scan_import",
                return_value=HttpResponse("fallback"),
            ) as render_mock:
                response = self.client.post(self.url, {"action": "x"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "fallback")
        handler_mock.assert_called_once()
        render_mock.assert_called_once()

    def test_scan_import_post_fallback_renders_latest_pending_state_after_clear(self):
        self.client.force_login(self.superuser)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp:
            temp.write(b"sku,name\nA,Produit A\n")
            temp_path = Path(temp.name)
        self.addCleanup(lambda: temp_path.unlink(missing_ok=True))

        session = self.client.session
        session["product_import_pending"] = {"token": "abc", "temp_path": str(temp_path)}
        session.save()

        def side_effect(request, *, default_password, clear_pending_import):
            del default_password
            clear_pending_import()
            return None

        with mock.patch(
            "wms.views_imports.handle_scan_import_action",
            side_effect=side_effect,
        ) as handler_mock:
            with mock.patch(
                "wms.views_imports.render_scan_import",
                return_value=HttpResponse("fallback"),
            ) as render_mock:
                response = self.client.post(self.url, {"action": "x"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "fallback")
        handler_mock.assert_called_once()
        render_mock.assert_called_once_with(mock.ANY, None)
        self.assertFalse(temp_path.exists())

    @override_settings(IMPORT_DEFAULT_PASSWORD="TempPwd!")
    def test_scan_import_clear_pending_callback_removes_temp_file(self):
        self.client.force_login(self.superuser)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp:
            temp.write(b"sku,name\nA,Produit A\n")
            temp_path = Path(temp.name)
        self.addCleanup(lambda: temp_path.unlink(missing_ok=True))

        session = self.client.session
        session["product_import_pending"] = {"temp_path": str(temp_path)}
        session.save()

        def side_effect(request, *, default_password, clear_pending_import):
            self.assertEqual(default_password, "TempPwd!")
            clear_pending_import()
            self.assertNotIn("product_import_pending", request.session)
            return HttpResponse("handled")

        with mock.patch(
            "wms.views_imports.handle_scan_import_action",
            side_effect=side_effect,
        ) as handler_mock:
            response = self.client.post(self.url, {"action": "x"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "handled")
        handler_mock.assert_called_once()
        self.assertFalse(temp_path.exists())
