import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from wms import scan_import_handlers


class ScanImportHandlersTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(
            username="import-tester",
            password="pass1234",
            is_staff=True,
            is_superuser=True,
        )
        self.scan_import_url = reverse("scan:scan_import")

    def _build_post_request(self, data):
        request = self.factory.post(self.scan_import_url, data=data)
        request.user = self.user
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        return request

    def _messages(self, request):
        return [message.message for message in get_messages(request)]

    def _clear_pending_import_callback(self, request, tracker):
        def clear_pending_import():
            tracker["called"] = True
            pending = request.session.pop("product_import_pending", None)
            if pending and pending.get("temp_path"):
                Path(pending["temp_path"]).unlink(missing_ok=True)

        return clear_pending_import

    def test_render_scan_import_builds_context(self):
        request = self.factory.get(self.scan_import_url)
        pending = {"token": "abc"}
        with mock.patch(
            "wms.scan_import_handlers.build_match_context",
            return_value={"rows": []},
        ) as build_context_mock:
            with mock.patch(
                "wms.scan_import_handlers.render",
                return_value=HttpResponse("ok"),
            ) as render_mock:
                response = scan_import_handlers.render_scan_import(request, pending)
        self.assertEqual(response.status_code, 200)
        build_context_mock.assert_called_once_with(pending)
        render_mock.assert_called_once()
        self.assertEqual(render_mock.call_args.args[1], scan_import_handlers.IMPORT_TEMPLATE)
        self.assertEqual(render_mock.call_args.args[2]["active"], "imports")
        self.assertEqual(
            render_mock.call_args.args[2]["product_match_pending"],
            {"rows": []},
        )

    def test_handle_scan_import_action_without_action_returns_none(self):
        request = self._build_post_request({})
        response = scan_import_handlers.handle_scan_import_action(
            request,
            default_password="TempPwd!",
            clear_pending_import=lambda: None,
        )
        self.assertIsNone(response)

    def test_product_confirm_rejects_invalid_token(self):
        request = self._build_post_request(
            {"action": "product_confirm", "pending_token": "invalid-token"}
        )
        request.session["product_import_pending"] = {"token": "valid-token", "matches": []}
        response = scan_import_handlers.handle_scan_import_action(
            request,
            default_password="TempPwd!",
            clear_pending_import=lambda: None,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.scan_import_url)
        self.assertIn("Import produit: confirmation invalide.", self._messages(request))

    def test_product_confirm_cancel_clears_pending_import(self):
        request = self._build_post_request(
            {
                "action": "product_confirm",
                "pending_token": "tok",
                "cancel": "1",
            }
        )
        request.session["product_import_pending"] = {"token": "tok", "matches": []}
        tracker = {"called": False}
        response = scan_import_handlers.handle_scan_import_action(
            request,
            default_password="TempPwd!",
            clear_pending_import=self._clear_pending_import_callback(request, tracker),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.scan_import_url)
        self.assertTrue(tracker["called"])
        self.assertNotIn("product_import_pending", request.session)
        self.assertIn("Import produit annule.", self._messages(request))

    def test_product_confirm_requires_match_selection_for_update(self):
        request = self._build_post_request(
            {"action": "product_confirm", "pending_token": "tok"}
        )
        request.session["product_import_pending"] = {
            "token": "tok",
            "matches": [{"row_index": 2, "match_ids": [10, 11]}],
        }
        response = scan_import_handlers.handle_scan_import_action(
            request,
            default_password="TempPwd!",
            clear_pending_import=lambda: None,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.scan_import_url)
        self.assertIn(
            "Import produit: sélection requise pour la mise à jour.",
            self._messages(request),
        )

    def test_product_confirm_rejects_invalid_target_product(self):
        request = self._build_post_request(
            {
                "action": "product_confirm",
                "pending_token": "tok",
                "match_id_2": "999",
            }
        )
        request.session["product_import_pending"] = {
            "token": "tok",
            "matches": [{"row_index": 2, "match_ids": [10, 11]}],
        }
        response = scan_import_handlers.handle_scan_import_action(
            request,
            default_password="TempPwd!",
            clear_pending_import=lambda: None,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.scan_import_url)
        self.assertIn(
            "Import produit: produit cible invalide.",
            self._messages(request),
        )

    def test_product_confirm_file_source_missing_temp_file(self):
        missing_path = Path(tempfile.gettempdir()) / "missing-import-products.csv"
        missing_path.unlink(missing_ok=True)
        request = self._build_post_request(
            {
                "action": "product_confirm",
                "pending_token": "tok",
                "match_id_2": "10",
            }
        )
        request.session["product_import_pending"] = {
            "token": "tok",
            "source": "file",
            "temp_path": str(missing_path),
            "extension": ".csv",
            "matches": [{"row_index": 2, "match_ids": [10]}],
        }
        tracker = {"called": False}
        response = scan_import_handlers.handle_scan_import_action(
            request,
            default_password="TempPwd!",
            clear_pending_import=self._clear_pending_import_callback(request, tracker),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.scan_import_url)
        self.assertTrue(tracker["called"])
        self.assertIn(
            "Import produit: fichier temporaire introuvable.",
            self._messages(request),
        )

    def test_product_confirm_file_source_imports_rows_and_reports(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp:
            temp.write(b"sku,name\nA,Produit A\n")
            temp_path = Path(temp.name)
        self.addCleanup(lambda: temp_path.unlink(missing_ok=True))

        request = self._build_post_request(
            {
                "action": "product_confirm",
                "pending_token": "tok",
                "decision_2": "create",
                "match_id_3": "20",
            }
        )
        request.session["product_import_pending"] = {
            "token": "tok",
            "source": "file",
            "temp_path": str(temp_path),
            "extension": ".csv",
            "start_index": 2,
            "default_action": "update",
            "quantity_mode": "overwrite",
            "matches": [
                {"row_index": 2, "match_ids": [10]},
                {"row_index": 3, "match_ids": [20]},
            ],
        }
        tracker = {"called": False}

        with mock.patch(
            "wms.scan_import_handlers.iter_import_rows",
            return_value=[{"sku": "A"}, {"sku": "B"}],
        ):
            with mock.patch(
                "wms.scan_import_handlers.import_products_rows",
                return_value=(
                    1,
                    1,
                    ["e1", "e2", "e3", "e4"],
                    ["w1", "w2", "w3", "w4"],
                    {"distinct_products": 1},
                ),
            ) as import_rows_mock:
                response = scan_import_handlers.handle_scan_import_action(
                    request,
                    default_password="TempPwd!",
                    clear_pending_import=self._clear_pending_import_callback(
                        request, tracker
                    ),
                )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.scan_import_url)
        self.assertTrue(tracker["called"])
        self.assertNotIn("product_import_pending", request.session)

        import_kwargs = import_rows_mock.call_args.kwargs
        self.assertEqual(
            import_kwargs["decisions"],
            {
                2: {"action": "create"},
                3: {"action": "update", "product_id": 20},
            },
        )
        self.assertEqual(import_kwargs["start_index"], 2)
        self.assertEqual(import_kwargs["base_dir"], temp_path.parent)
        self.assertEqual(import_kwargs["quantity_mode"], "overwrite")
        self.assertTrue(import_kwargs["collect_stats"])

        messages = self._messages(request)
        self.assertIn("Import produits: 4 erreur(s).", messages)
        self.assertIn("e1", messages)
        self.assertIn("Import produits: 4 alerte(s).", messages)
        self.assertIn("w1", messages)
        self.assertIn(
            "Import produits: 1 créé(s), 1 ligne(s) maj., 1 produit(s) distinct(s) impacté(s).",
            messages,
        )

    def test_product_confirm_single_match_uses_pending_match_id_when_missing_in_post(self):
        request = self._build_post_request(
            {
                "action": "product_confirm",
                "pending_token": "tok",
            }
        )
        request.session["product_import_pending"] = {
            "token": "tok",
            "source": "single",
            "rows": [{"sku": "A"}],
            "start_index": 1,
            "default_action": "update",
            "matches": [{"row_index": 1, "match_ids": [11]}],
        }
        tracker = {"called": False}
        with mock.patch(
            "wms.scan_import_handlers.import_products_rows",
            return_value=(0, 1, [], []),
        ) as import_rows_mock:
            response = scan_import_handlers.handle_scan_import_action(
                request,
                default_password="TempPwd!",
                clear_pending_import=self._clear_pending_import_callback(request, tracker),
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(tracker["called"])
        decisions = import_rows_mock.call_args.kwargs["decisions"]
        self.assertEqual(decisions, {1: {"action": "update", "product_id": 11}})

    def test_product_confirm_single_source_imports_rows(self):
        request = self._build_post_request(
            {
                "action": "product_confirm",
                "pending_token": "tok",
                "match_id_1": "11",
            }
        )
        request.session["product_import_pending"] = {
            "token": "tok",
            "source": "single",
            "rows": [{"sku": "A"}],
            "start_index": 1,
            "default_action": "update",
            "matches": [{"row_index": 1, "match_ids": [11]}],
        }
        tracker = {"called": False}
        with mock.patch(
            "wms.scan_import_handlers.import_products_rows",
            return_value=(0, 1, [], []),
        ) as import_rows_mock:
            response = scan_import_handlers.handle_scan_import_action(
                request,
                default_password="TempPwd!",
                clear_pending_import=self._clear_pending_import_callback(request, tracker),
            )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(tracker["called"])
        self.assertEqual(import_rows_mock.call_args.kwargs["base_dir"], None)
        self.assertEqual(import_rows_mock.call_args.kwargs["start_index"], 1)

    def test_product_single_with_matches_stores_pending_and_renders(self):
        request = self._build_post_request(
            {
                "action": "product_single",
                "sku": "SKU-1",
                "name": "Produit 1",
                "brand": "ASF",
            }
        )
        with mock.patch(
            "wms.scan_import_handlers.extract_product_identity",
            return_value=("SKU-1", "Produit 1", "ASF"),
        ):
            with mock.patch(
                "wms.scan_import_handlers.find_product_matches",
                return_value=([SimpleNamespace(id=42)], "sku"),
            ):
                with mock.patch(
                    "wms.scan_import_handlers.summarize_import_row",
                    return_value="SKU-1 | Produit 1",
                ):
                    with mock.patch(
                        "wms.scan_import_handlers.render_scan_import",
                        return_value=HttpResponse("pending"),
                    ) as render_import_mock:
                        response = scan_import_handlers.handle_scan_import_action(
                            request,
                            default_password="TempPwd!",
                            clear_pending_import=lambda: None,
                        )
        self.assertEqual(response.status_code, 200)
        render_import_mock.assert_called_once()
        pending = request.session.get("product_import_pending")
        self.assertIsNotNone(pending)
        self.assertEqual(pending["source"], "single")
        self.assertEqual(pending["default_action"], "update")
        self.assertEqual(pending["matches"][0]["match_ids"], [42])

    def test_product_single_without_matches_imports_immediately(self):
        request = self._build_post_request(
            {
                "action": "product_single",
                "sku": "SKU-2",
            }
        )
        with mock.patch(
            "wms.scan_import_handlers.extract_product_identity",
            return_value=("SKU-2", "Produit 2", "ASF"),
        ):
            with mock.patch(
                "wms.scan_import_handlers.find_product_matches",
                return_value=([], "none"),
            ):
                with mock.patch(
                    "wms.scan_import_handlers.import_products_rows",
                    return_value=(1, 0, [], ["w1", "w2"]),
                ):
                    response = scan_import_handlers.handle_scan_import_action(
                        request,
                        default_password="TempPwd!",
                        clear_pending_import=lambda: None,
                    )
        self.assertEqual(response.status_code, 302)
        messages = self._messages(request)
        self.assertIn("w1", messages)
        self.assertIn("Produit créé.", messages)

    def test_product_single_without_matches_reports_error(self):
        request = self._build_post_request(
            {
                "action": "product_single",
                "sku": "SKU-ERR",
            }
        )
        with mock.patch(
            "wms.scan_import_handlers.extract_product_identity",
            return_value=("SKU-ERR", "Produit Err", "ASF"),
        ), mock.patch(
            "wms.scan_import_handlers.find_product_matches",
            return_value=([], "none"),
        ), mock.patch(
            "wms.scan_import_handlers.import_products_rows",
            return_value=(0, 0, ["erreur prioritaire", "autre"], []),
        ):
            response = scan_import_handlers.handle_scan_import_action(
                request,
                default_password="TempPwd!",
                clear_pending_import=lambda: None,
            )

        self.assertEqual(response.status_code, 302)
        messages = self._messages(request)
        self.assertIn("erreur prioritaire", messages)
        self.assertNotIn("Produit créé.", messages)

    def test_product_file_requires_uploaded_file(self):
        request = self._build_post_request({"action": "product_file"})
        response = scan_import_handlers.handle_scan_import_action(
            request,
            default_password="TempPwd!",
            clear_pending_import=lambda: None,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "Fichier requis pour importer les produits.",
            self._messages(request),
        )

    def test_product_file_rejects_unsupported_extension(self):
        uploaded = SimpleUploadedFile("produits.txt", b"invalid")
        request = self._build_post_request(
            {"action": "product_file", "import_file": uploaded}
        )
        response = scan_import_handlers.handle_scan_import_action(
            request,
            default_password="TempPwd!",
            clear_pending_import=lambda: None,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "Format non supporte. Utilisez CSV/XLS/XLSX.",
            self._messages(request),
        )

    def test_product_file_with_matches_stores_pending_and_renders(self):
        uploaded = SimpleUploadedFile("produits.csv", b"sku,name\nA,Produit A\n")
        request = self._build_post_request(
            {"action": "product_file", "import_file": uploaded}
        )
        with mock.patch(
            "wms.scan_import_handlers.decode_text",
            return_value="sku,name\nA,Produit A\n",
        ):
            with mock.patch(
                "wms.scan_import_handlers.iter_import_rows",
                return_value=[{"sku": "A", "name": "Produit A"}],
            ):
                with mock.patch(
                    "wms.scan_import_handlers.row_is_empty",
                    return_value=False,
                ):
                    with mock.patch(
                        "wms.scan_import_handlers.extract_product_identity",
                        return_value=("SKU-1", "Produit 1", "ASF"),
                    ):
                        with mock.patch(
                            "wms.scan_import_handlers.find_product_matches",
                            return_value=([SimpleNamespace(id=99)], "sku"),
                        ):
                            with mock.patch(
                                "wms.scan_import_handlers.summarize_import_row",
                                return_value="SKU-1 | Produit 1",
                            ):
                                with mock.patch(
                                    "wms.scan_import_handlers.render_scan_import",
                                    return_value=HttpResponse("pending"),
                                ):
                                    response = (
                                        scan_import_handlers.handle_scan_import_action(
                                            request,
                                            default_password="TempPwd!",
                                            clear_pending_import=lambda: None,
                                        )
                                    )
        self.assertEqual(response.status_code, 200)
        pending = request.session.get("product_import_pending")
        self.assertIsNotNone(pending)
        self.assertEqual(pending["source"], "file")
        self.assertEqual(pending["default_action"], "create")
        self.assertEqual(pending["quantity_mode"], "movement")
        self.assertEqual(pending["matches"][0]["match_ids"], [99])
        Path(pending["temp_path"]).unlink(missing_ok=True)

    def test_product_file_with_matches_stores_overwrite_quantity_mode(self):
        uploaded = SimpleUploadedFile("produits.csv", b"sku,name\nA,Produit A\n")
        request = self._build_post_request(
            {"action": "product_file", "import_file": uploaded, "stock_mode": "overwrite"}
        )
        with mock.patch(
            "wms.scan_import_handlers.decode_text",
            return_value="sku,name\nA,Produit A\n",
        ), mock.patch(
            "wms.scan_import_handlers.iter_import_rows",
            return_value=[{"sku": "A", "name": "Produit A"}],
        ), mock.patch(
            "wms.scan_import_handlers.row_is_empty",
            return_value=False,
        ), mock.patch(
            "wms.scan_import_handlers.extract_product_identity",
            return_value=("SKU-1", "Produit 1", "ASF"),
        ), mock.patch(
            "wms.scan_import_handlers.find_product_matches",
            return_value=([SimpleNamespace(id=99)], "sku"),
        ), mock.patch(
            "wms.scan_import_handlers.summarize_import_row",
            return_value="SKU-1 | Produit 1",
        ), mock.patch(
            "wms.scan_import_handlers.render_scan_import",
            return_value=HttpResponse("pending"),
        ):
            response = scan_import_handlers.handle_scan_import_action(
                request,
                default_password="TempPwd!",
                clear_pending_import=lambda: None,
            )

        self.assertEqual(response.status_code, 200)
        pending = request.session.get("product_import_pending")
        self.assertEqual(pending["quantity_mode"], "overwrite")
        Path(pending["temp_path"]).unlink(missing_ok=True)

    def test_product_file_without_matches_imports_immediately(self):
        uploaded = SimpleUploadedFile("produits.csv", b"sku,name\nA,Produit A\n")
        request = self._build_post_request(
            {"action": "product_file", "import_file": uploaded, "stock_mode": "overwrite"}
        )
        with mock.patch(
            "wms.scan_import_handlers.decode_text",
            return_value="sku,name\nA,Produit A\n",
        ):
            with mock.patch(
                "wms.scan_import_handlers.iter_import_rows",
                return_value=[{"sku": "A", "name": "Produit A"}],
            ):
                with mock.patch(
                    "wms.scan_import_handlers.row_is_empty",
                    return_value=False,
                ):
                    with mock.patch(
                        "wms.scan_import_handlers.extract_product_identity",
                        return_value=("SKU-1", "Produit 1", "ASF"),
                    ):
                        with mock.patch(
                            "wms.scan_import_handlers.find_product_matches",
                            return_value=([], "none"),
                        ):
                            with mock.patch(
                                "wms.scan_import_handlers.import_products_rows",
                                return_value=(2, 0, ["e1"], ["w1"], {"distinct_products": 2}),
                            ) as import_rows_mock:
                                response = (
                                    scan_import_handlers.handle_scan_import_action(
                                        request,
                                        default_password="TempPwd!",
                                        clear_pending_import=lambda: None,
                                    )
                                )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            import_rows_mock.call_args.kwargs["quantity_mode"],
            "overwrite",
        )
        self.assertTrue(import_rows_mock.call_args.kwargs["collect_stats"])
        messages = self._messages(request)
        self.assertIn("Import produits: 1 erreur(s).", messages)
        self.assertIn("Import produits: 1 alerte(s).", messages)
        self.assertIn(
            "Import produits: 2 créé(s), 0 ligne(s) maj., 2 produit(s) distinct(s) impacté(s).",
            messages,
        )

    def test_product_file_skips_empty_rows_before_match_detection(self):
        uploaded = SimpleUploadedFile("produits.csv", b"sku,name\n,\nA,Produit A\n")
        request = self._build_post_request(
            {"action": "product_file", "import_file": uploaded}
        )
        rows = [{}, {"sku": "A", "name": "Produit A"}]
        with mock.patch(
            "wms.scan_import_handlers.decode_text",
            return_value="sku,name\n,\nA,Produit A\n",
        ), mock.patch(
            "wms.scan_import_handlers.iter_import_rows",
            return_value=rows,
        ), mock.patch(
            "wms.scan_import_handlers.row_is_empty",
            side_effect=[True, False],
        ), mock.patch(
            "wms.scan_import_handlers.extract_product_identity",
            return_value=("SKU-1", "Produit 1", "ASF"),
        ) as extract_identity_mock, mock.patch(
            "wms.scan_import_handlers.find_product_matches",
            return_value=([], "none"),
        ) as find_matches_mock, mock.patch(
            "wms.scan_import_handlers.import_products_rows",
            return_value=(1, 0, [], []),
        ):
            response = scan_import_handlers.handle_scan_import_action(
                request,
                default_password="TempPwd!",
                clear_pending_import=lambda: None,
            )

        self.assertEqual(response.status_code, 302)
        extract_identity_mock.assert_called_once_with(rows[1])
        find_matches_mock.assert_called_once()

    def test_file_action_user_file_passes_default_password(self):
        uploaded = SimpleUploadedFile("users.csv", b"email\nuser@example.com\n")
        request = self._build_post_request({"action": "user_file", "import_file": uploaded})
        importer = mock.Mock(return_value=(1, 2, [], []))
        with mock.patch.dict(
            scan_import_handlers.IMPORT_FILE_ACTIONS,
            {"user_file": ("utilisateurs", importer)},
            clear=False,
        ):
            with mock.patch(
                "wms.scan_import_handlers.iter_import_rows",
                return_value=[{"email": "user@example.com"}],
            ):
                with mock.patch(
                    "wms.scan_import_handlers.normalize_import_result",
                    return_value=(1, 2, ["e1"], ["w1"]),
                ):
                    response = scan_import_handlers.handle_scan_import_action(
                        request,
                        default_password="TempPwd!",
                        clear_pending_import=lambda: None,
                    )
        self.assertEqual(response.status_code, 302)
        importer.assert_called_once_with([{"email": "user@example.com"}], "TempPwd!")
        messages = self._messages(request)
        self.assertIn("Import utilisateurs: 1 erreur(s).", messages)
        self.assertIn("Import utilisateurs: 1 alerte(s).", messages)
        self.assertIn("Import utilisateurs: 1 créé(s), 2 maj.", messages)

    def test_file_action_requires_upload_for_non_user_action(self):
        request = self._build_post_request({"action": "location_file"})
        importer = mock.Mock(return_value=(0, 0, [], []))
        with mock.patch.dict(
            scan_import_handlers.IMPORT_FILE_ACTIONS,
            {"location_file": ("emplacements", importer)},
            clear=False,
        ):
            response = scan_import_handlers.handle_scan_import_action(
                request,
                default_password="TempPwd!",
                clear_pending_import=lambda: None,
            )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "Fichier requis pour importer les emplacements.",
            self._messages(request),
        )
        importer.assert_not_called()

    def test_file_action_non_user_file_calls_importer_without_password(self):
        uploaded = SimpleUploadedFile("locations.csv", b"name\nRack A\n")
        request = self._build_post_request(
            {"action": "location_file", "import_file": uploaded}
        )
        importer = mock.Mock(return_value=(1, 0, [], []))
        rows = [{"name": "Rack A"}]
        with mock.patch.dict(
            scan_import_handlers.IMPORT_FILE_ACTIONS,
            {"location_file": ("emplacements", importer)},
            clear=False,
        ), mock.patch(
            "wms.scan_import_handlers.iter_import_rows",
            return_value=rows,
        ), mock.patch(
            "wms.scan_import_handlers.normalize_import_result",
            return_value=(1, 0, [], []),
        ):
            response = scan_import_handlers.handle_scan_import_action(
                request,
                default_password="TempPwd!",
                clear_pending_import=lambda: None,
            )

        self.assertEqual(response.status_code, 302)
        importer.assert_called_once_with(rows)

    def test_file_action_reports_value_error(self):
        uploaded = SimpleUploadedFile("locations.csv", b"invalid")
        request = self._build_post_request(
            {"action": "location_file", "import_file": uploaded}
        )
        importer = mock.Mock()
        with mock.patch.dict(
            scan_import_handlers.IMPORT_FILE_ACTIONS,
            {"location_file": ("emplacements", importer)},
            clear=False,
        ):
            with mock.patch(
                "wms.scan_import_handlers.iter_import_rows",
                side_effect=ValueError("header invalide"),
            ):
                response = scan_import_handlers.handle_scan_import_action(
                    request,
                    default_password="TempPwd!",
                    clear_pending_import=lambda: None,
                )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "Import emplacements: header invalide",
            self._messages(request),
        )
        importer.assert_not_called()

    def test_single_action_user_single_passes_default_password(self):
        request = self._build_post_request(
            {"action": "user_single", "email": "user@example.com"}
        )
        importer = mock.Mock(return_value=(1, 0, [], []))
        with mock.patch.dict(
            scan_import_handlers.IMPORT_SINGLE_ACTIONS,
            {"user_single": ("utilisateur", importer)},
            clear=False,
        ):
            with mock.patch(
                "wms.scan_import_handlers.normalize_import_result",
                return_value=(1, 0, [], []),
            ):
                response = scan_import_handlers.handle_scan_import_action(
                    request,
                    default_password="TempPwd!",
                    clear_pending_import=lambda: None,
                )
        self.assertEqual(response.status_code, 302)
        importer.assert_called_once()
        importer_args = importer.call_args.args
        self.assertEqual(importer_args[1], "TempPwd!")
        self.assertIn("Utilisateur ajouté.", self._messages(request))

    def test_single_action_reports_value_error(self):
        request = self._build_post_request(
            {"action": "category_single", "name": "Sante"}
        )
        importer = mock.Mock(side_effect=ValueError("nom requis"))
        with mock.patch.dict(
            scan_import_handlers.IMPORT_SINGLE_ACTIONS,
            {"category_single": ("categorie", importer)},
            clear=False,
        ):
            response = scan_import_handlers.handle_scan_import_action(
                request,
                default_password="TempPwd!",
                clear_pending_import=lambda: None,
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn("Ajout categorie: nom requis", self._messages(request))

    def test_single_action_reports_first_error_and_warnings(self):
        request = self._build_post_request(
            {"action": "warehouse_single", "code": "WH1"}
        )
        importer = mock.Mock(return_value=(0, 0, [], []))
        with mock.patch.dict(
            scan_import_handlers.IMPORT_SINGLE_ACTIONS,
            {"warehouse_single": ("entrepot", importer)},
            clear=False,
        ):
            with mock.patch(
                "wms.scan_import_handlers.normalize_import_result",
                return_value=(0, 0, ["erreur unique"], []),
            ):
                response_error = scan_import_handlers.handle_scan_import_action(
                    request,
                    default_password="TempPwd!",
                    clear_pending_import=lambda: None,
                )
        self.assertEqual(response_error.status_code, 302)
        self.assertIn("erreur unique", self._messages(request))

        request_warn = self._build_post_request(
            {"action": "warehouse_single", "code": "WH2"}
        )
        with mock.patch.dict(
            scan_import_handlers.IMPORT_SINGLE_ACTIONS,
            {"warehouse_single": ("entrepot", importer)},
            clear=False,
        ):
            with mock.patch(
                "wms.scan_import_handlers.normalize_import_result",
                return_value=(0, 0, [], ["attention"]),
            ):
                response_warn = scan_import_handlers.handle_scan_import_action(
                    request_warn,
                    default_password="TempPwd!",
                    clear_pending_import=lambda: None,
                )
        self.assertEqual(response_warn.status_code, 302)
        self.assertIn("attention", self._messages(request_warn))

    def test_unknown_action_returns_none(self):
        request = self._build_post_request({"action": "unknown-action"})
        response = scan_import_handlers.handle_scan_import_action(
            request,
            default_password="TempPwd!",
            clear_pending_import=lambda: None,
        )
        self.assertIsNone(response)
