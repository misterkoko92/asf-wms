from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from contacts.models import Contact
from wms.helper_install import build_helper_install_context
from wms.models import (
    Carton,
    CartonStatus,
    Destination,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
)


class ScanShipmentsViewsTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-shipments-staff",
            password="pass1234",
            is_staff=True,
        )
        self.factory = RequestFactory()
        self.client.force_login(self.staff_user)

    def _render_stub(self, _request, template_name, context):
        response = HttpResponse(template_name)
        response.context_data = context
        return response

    def _activate_english(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

    def _create_shipment(self, *, status=ShipmentStatus.DRAFT):
        return Shipment.objects.create(
            status=status,
            shipper_name="Aviation Sans Frontieres",
            recipient_name="Association Dest",
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.staff_user,
        )

    def _create_preparateur_user(self):
        user = get_user_model().objects.create_user(
            username="scan-preparateur-ui",
            password="pass1234",
            is_staff=True,
        )
        group, _ = Group.objects.get_or_create(name="Preparateur")
        user.groups.add(group)
        return user

    def test_scan_cartons_ready_short_circuits_when_handler_returns_response(self):
        with mock.patch(
            "wms.views_scan_shipments.handle_carton_status_update",
            return_value=HttpResponse("handled"),
        ):
            with mock.patch("wms.views_scan_shipments.get_carton_capacity_cm3") as capacity_mock:
                response = self.client.get(reverse("scan:scan_cartons_ready"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "handled")
        capacity_mock.assert_not_called()

    def test_scan_cartons_ready_renders_rows_context(self):
        with mock.patch(
            "wms.views_scan_shipments.handle_carton_status_update",
            return_value=None,
        ):
            helper_install = {"available": True, "install_url": "/scan/helper/install/"}
            with mock.patch(
                "wms.views_scan_shipments.build_helper_install_context",
                return_value=helper_install,
            ):
                with mock.patch(
                    "wms.views_scan_shipments.get_carton_capacity_cm3",
                    return_value=12345,
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.build_cartons_ready_rows",
                        return_value=[{"id": 1, "code": "C-001"}],
                    ) as rows_mock:
                        with mock.patch(
                            "wms.views_scan_shipments.render",
                            side_effect=self._render_stub,
                        ):
                            response = self.client.get(reverse("scan:scan_cartons_ready"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/cartons_ready.html")
        self.assertEqual(response.context_data["active"], "cartons_ready")
        self.assertEqual(response.context_data["cartons"], [{"id": 1, "code": "C-001"}])
        self.assertEqual(response.context_data["helper_install"], helper_install)
        self.assertEqual(rows_mock.call_args.kwargs["carton_capacity_cm3"], 12345)

    def test_scan_kits_view_renders_rows_context(self):
        with mock.patch(
            "wms.views_scan_shipments.build_kits_view_rows",
            return_value=[{"id": 1, "name": "Kit Test"}],
        ):
            with mock.patch(
                "wms.views_scan_shipments.render",
                side_effect=self._render_stub,
            ):
                response = self.client.get(reverse("scan:scan_kits_view"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/kits_view.html")
        self.assertEqual(response.context_data["active"], "kits_view")
        self.assertEqual(
            response.context_data["kits"],
            [{"id": 1, "name": "Kit Test"}],
        )

    def test_scan_prepare_kits_get_renders_rows_context(self):
        fake_form = object()
        helper_install = {"available": True, "install_url": "/scan/helper/install/"}
        with mock.patch(
            "wms.views_scan_shipments.ScanPrepareKitsForm",
            return_value=fake_form,
        ):
            with mock.patch(
                "wms.views_scan_shipments.build_prepare_kits_page_context",
                return_value={
                    "kit_options": [{"id": 1, "name": "Kit Test"}],
                    "selected_kit": {"id": 1, "name": "Kit Test"},
                    "prepare_result": None,
                },
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_helper_install_context",
                    return_value=helper_install,
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.render",
                        side_effect=self._render_stub,
                    ):
                        response = self.client.get(
                            reverse("scan:scan_prepare_kits"),
                            {"kit_id": "1"},
                        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/prepare_kits.html")
        self.assertEqual(response.context_data["active"], "prepare_kits")
        self.assertEqual(response.context_data["form"], fake_form)
        self.assertEqual(response.context_data["helper_install"], helper_install)
        self.assertEqual(
            response.context_data["selected_kit"]["name"],
            "Kit Test",
        )

    def test_scan_shipments_ready_renders_rows_context(self):
        helper_install = {"available": True, "install_url": "/scan/helper/install/"}
        with mock.patch(
            "wms.views_scan_shipments.build_shipments_ready_rows",
            return_value=[{"id": 1, "reference": "S-001"}],
        ):
            with mock.patch(
                "wms.views_scan_shipments.build_helper_install_context",
                return_value=helper_install,
            ):
                with mock.patch(
                    "wms.views_scan_shipments.render",
                    side_effect=self._render_stub,
                ):
                    response = self.client.get(reverse("scan:scan_shipments_ready"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/shipments_ready.html")
        self.assertEqual(response.context_data["active"], "shipments_ready")
        self.assertEqual(
            response.context_data["shipments"],
            [{"id": 1, "reference": "S-001"}],
        )
        self.assertEqual(response.context_data["helper_install"], helper_install)

    def test_scan_local_document_helper_installer_delegates_to_helper_install_response(self):
        with mock.patch(
            "wms.views_scan_shipments.build_helper_installer_response",
            return_value=HttpResponse("installer"),
        ) as response_mock:
            response = self.client.get(reverse("scan:scan_local_document_helper_installer"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "installer")
        response_mock.assert_called_once_with(
            request=mock.ANY,
            app_label="asf-wms",
        )

    def test_scan_local_document_helper_installer_requires_login_without_signed_token(self):
        self.client.logout()

        response = self.client.get(reverse("scan:scan_local_document_helper_installer"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    @mock.patch("wms.helper_install._helper_bundle_base64", return_value="QUJD")
    def test_scan_local_document_helper_installer_allows_signed_anonymous_request(
        self,
        _bundle_mock,
    ):
        request = self.factory.get(
            "/scan/shipments-ready/",
            HTTP_USER_AGENT=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
            ),
        )
        context = build_helper_install_context(
            install_url=reverse("scan:scan_local_document_helper_installer"),
            app_label="asf-wms",
            system="Linux",
            request=request,
        )

        self.client.logout()
        response = self.client.get(context["install_url"])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="install-asf-wms-helper.command"',
        )
        self.assertIn("#!/bin/zsh", response.content.decode())

    def test_scan_shipments_ready_exposes_helper_version_metadata(self):
        response = self.client.get(reverse("scan:scan_shipments_ready"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-local-document-helper-minimum-version="0.1.2"')
        self.assertContains(response, 'data-local-document-helper-latest-version="0.1.2"')

    def test_scan_shipments_ready_uses_updated_headers_and_status_markup(self):
        with mock.patch(
            "wms.views_scan_shipments.build_shipments_ready_rows",
            return_value=[
                {
                    "id": 1,
                    "reference": "S-001",
                    "tracking_token": "11111111-1111-1111-1111-111111111111",
                    "carton_count": 4,
                    "equivalent_carton_count": 10,
                    "destination_iata": "CDG",
                    "shipper_name": "ASF",
                    "recipient_name": "Dest",
                    "created_at": None,
                    "ready_at": None,
                    "status_label": "Planifié",
                    "status_tone": "progress",
                    "status_variant": "planned",
                    "can_edit": True,
                }
            ],
        ):
            response = self.client.get(reverse("scan:scan_shipments_ready"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-shipment-reference-col")
        self.assertContains(response, "Nb Colis Equivalent")
        self.assertContains(response, "scan-shipment-ready-col")
        self.assertContains(
            response,
            'class="ui-comp-status-pill scan-shipment-status-pill scan-shipment-status--planned is-progress"',
        )

    @mock.patch("wms.helper_install.platform.system", return_value="Linux")
    def test_scan_shipments_ready_detects_macos_client_on_linux_server(self, _platform_mock):
        response = self.client.get(
            reverse("scan:scan_shipments_ready"),
            HTTP_USER_AGENT=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-local-document-helper-install-available="1"')
        self.assertContains(
            response, 'data-local-document-helper-install-label="Installer le helper (macOS)"'
        )

    def test_scan_cartons_ready_exposes_helper_version_metadata(self):
        response = self.client.get(reverse("scan:scan_cartons_ready"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-local-document-helper-minimum-version="0.1.2"')
        self.assertContains(response, 'data-local-document-helper-latest-version="0.1.2"')

    def test_scan_cartons_ready_uses_available_label_and_updated_status_controls(self):
        with mock.patch(
            "wms.views_scan_shipments.build_cartons_ready_rows",
            return_value=[
                {
                    "id": 1,
                    "code": "C-READY",
                    "created_at": None,
                    "status_value": CartonStatus.PACKED,
                    "status_tone": "ready",
                    "can_toggle": True,
                    "can_mark_labeled": False,
                    "can_mark_assigned": False,
                    "shipment_reference": "",
                    "location": "",
                    "packing_list": [],
                    "packing_list_url": "",
                    "picking_url": "",
                    "weight_kg": None,
                    "volume_percent": None,
                },
                {
                    "id": 2,
                    "code": "C-ASSIGNED",
                    "created_at": None,
                    "status_label": "Affecté",
                    "status_value": CartonStatus.ASSIGNED,
                    "status_tone": "progress",
                    "can_toggle": False,
                    "can_mark_labeled": True,
                    "can_mark_assigned": False,
                    "shipment_reference": "S-001",
                    "location": "",
                    "packing_list": [],
                    "packing_list_url": "",
                    "picking_url": "",
                    "weight_kg": None,
                    "volume_percent": None,
                },
            ],
        ):
            response = self.client.get(reverse("scan:scan_cartons_ready"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-carton-status-cell")
        self.assertContains(response, "scan-carton-status-select-wrap")
        self.assertContains(response, "Disponible")
        self.assertContains(response, "scan-carton-status-display")
        self.assertContains(
            response,
            'class="ui-comp-status-pill scan-carton-status-pill is-progress"',
        )
        self.assertContains(
            response,
            'class="scan-scan-btn btn btn-sm btn-tertiary"',
        )

    def test_scan_shipments_tracking_renders_rows_context(self):
        with mock.patch(
            "wms.views_scan_shipments.build_shipments_tracking_rows",
            return_value=[{"id": 1, "reference": "S-TRACK-001"}],
        ):
            with mock.patch(
                "wms.views_scan_shipments.render",
                side_effect=self._render_stub,
            ):
                response = self.client.get(reverse("scan:scan_shipments_tracking"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/shipments_tracking.html")
        self.assertEqual(response.context_data["active"], "shipments_tracking")
        self.assertEqual(
            response.context_data["shipments"],
            [{"id": 1, "reference": "S-TRACK-001"}],
        )

    def test_scan_pack_hides_top_reference_scan_button(self):
        response = self.client.get(reverse("scan:scan_pack"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-scan-target="id_shipment_reference"')

    def test_scan_pack_shows_dual_prepare_buttons_and_hides_location_admin_action(self):
        response = self.client.get(reverse("scan:scan_pack"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-pack-add-line-btn")
        self.assertContains(response, "Préparer sans conditionner")
        self.assertContains(response, "Préparer et mettre en disponible")
        self.assertContains(response, "ui-comp-actions")
        self.assertNotContains(response, "Ajouter emplacement")

    def test_scan_pack_uses_shared_action_wrapper_for_generated_result_links(self):
        session = self.client.session
        session["pack_results"] = [10]
        session.save()

        with mock.patch(
            "wms.views_scan_shipments.build_packing_result",
            return_value={
                "cartons": [
                    {
                        "code": "MM-20260322-01",
                        "packing_list_url": "/docs/packing-list.pdf",
                        "picking_url": "/docs/picking.pdf",
                        "items": [],
                    }
                ],
                "aggregate": [],
                "show_success_modal": False,
            },
        ):
            response = self.client.get(reverse("scan:scan_pack"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="scan-inline-actions ui-comp-actions"')

    def test_scan_pack_missing_defaults_warning_uses_shared_alert_contract(self):
        pack_state = {
            "carton_format_id": "custom",
            "carton_custom": {"length_cm": 30},
            "line_count": 1,
            "line_values": [{"line": 1}],
            "line_errors": {},
            "missing_defaults": ["SKU-001"],
            "confirm_defaults": True,
        }

        with mock.patch(
            "wms.views_scan_shipments.handle_pack_post",
            return_value=(None, pack_state),
        ):
            response = self.client.post(reverse("scan:scan_pack"), {})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SKU-001")
        self.assertContains(response, "ui-comp-alert")
        self.assertContains(
            response,
            'class="form-check form-switch scan-inline-switch scan-inline-switch-wide"',
        )

    def test_scan_pack_preparateur_hides_non_essential_controls_and_reduces_navigation(self):
        preparateur = self._create_preparateur_user()
        self.client.force_login(preparateur)

        response = self.client.get(reverse("scan:scan_pack"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Référence expédition (optionnel)")
        self.assertNotContains(response, "Choisir un emplacement de rangement du colis prêt")
        self.assertNotContains(response, "Ajouter emplacement")
        self.assertContains(response, 'data-preparateur-pack-mode="1"')
        self.assertContains(response, "Préparer des colis")
        self.assertNotContains(response, "Tableau De Bord")
        self.assertNotContains(response, "Vue Stock")
        self.assertNotContains(response, "Admin Django")

    def test_scan_pack_preparateur_renders_success_modal_with_distinct_carton_numbers(self):
        preparateur = self._create_preparateur_user()
        self.client.force_login(preparateur)
        session = self.client.session
        session["pack_results"] = [
            {"carton_id": 10, "zone_label": "Colis Prets MM", "family": "MM"},
            {"carton_id": 11, "zone_label": "Colis Prets CN", "family": "CN"},
        ]
        session.save()

        with mock.patch(
            "wms.views_scan_shipments.build_packing_result",
            return_value={
                "cartons": [
                    {
                        "code": "MM-20260316-12",
                        "zone_label": "Colis Prets MM",
                        "family": "MM",
                        "items": [],
                    },
                    {
                        "code": "CN-20260316-04",
                        "zone_label": "Colis Prets CN",
                        "family": "CN",
                        "items": [],
                    },
                ],
                "aggregate": [],
                "show_success_modal": True,
            },
        ):
            response = self.client.get(reverse("scan:scan_pack"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Colis créés avec succès")
        self.assertContains(response, "Ranger le colis dans la zone Colis Prets MM")
        self.assertContains(response, "Écrire le numéro MM-20260316-12")
        self.assertContains(response, "Ranger le colis dans la zone Colis Prets CN")
        self.assertContains(response, "Écrire le numéro CN-20260316-04")
        self.assertContains(response, 'id="pack-success-modal"')

    def test_scan_shipment_create_renders_secondary_draft_button_near_submit(self):
        response = self.client.get(reverse("scan:scan_shipment_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="action" value="save_draft"', count=2)

    def test_scan_shipment_create_renders_single_correspondent_display_markers(self):
        response = self.client.get(reverse("scan:scan_shipment_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shipment-correspondent-select-wrap"')
        self.assertContains(response, 'id="shipment-correspondent-single"')

    def test_scan_prepare_kits_groups_top_controls_in_single_panel(self):
        response = self.client.get(reverse("scan:scan_prepare_kits"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-prepare-kits-top-panel", count=1)
        self.assertContains(response, "scan-prepare-kits-top-group", count=2)

    def test_scan_shipments_tracking_uses_primary_follow_up_and_secondary_close_buttons(self):
        shipment = Shipment.objects.create(
            status=ShipmentStatus.DELIVERED,
            shipper_name="Aviation Sans Frontieres",
            recipient_name="Association Dest",
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.staff_user,
        )
        for status in (
            ShipmentTrackingStatus.PLANNED,
            ShipmentTrackingStatus.BOARDING_OK,
            ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            ShipmentTrackingStatus.RECEIVED_RECIPIENT,
        ):
            ShipmentTrackingEvent.objects.create(
                shipment=shipment,
                status=status,
                actor_name="Ops",
                actor_structure="ASF",
                comments="step",
                created_by=self.staff_user,
            )

        response = self.client.get(reverse("scan:scan_shipments_tracking"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(
            f'class="scan-scan-btn btn btn-primary" href="{reverse("scan:scan_shipment_track", args=[shipment.tracking_token])}?return_to=shipments_tracking"',
            content,
        )
        self.assertIn(
            'class="scan-scan-btn btn btn-secondary scan-shipment-close-btn is-ready"',
            content,
        )
        self.assertIn('<option value="exclude" selected>', content)

    def test_scan_shipments_tracking_post_closes_ready_shipment(self):
        shipment = self._create_shipment(status=ShipmentStatus.DELIVERED)
        for step in [
            ShipmentTrackingStatus.PLANNED,
            ShipmentTrackingStatus.BOARDING_OK,
            ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            ShipmentTrackingStatus.RECEIVED_RECIPIENT,
        ]:
            ShipmentTrackingEvent.objects.create(
                shipment=shipment,
                status=step,
                actor_name="Agent",
                actor_structure="ASF",
                comments="ok",
                created_by=self.staff_user,
            )

        with mock.patch("wms.views_scan_shipments.log_shipment_case_closed") as log_mock:
            response = self.client.post(
                reverse("scan:scan_shipments_tracking"),
                {"action": "close_shipment_case", "shipment_id": shipment.id},
            )

        self.assertEqual(response.status_code, 302)
        shipment.refresh_from_db()
        self.assertIsNotNone(shipment.closed_at)
        self.assertEqual(shipment.closed_by, self.staff_user)
        log_mock.assert_called_once_with(
            shipment=shipment,
            user=self.staff_user,
        )

    def test_scan_shipments_tracking_post_does_not_close_incomplete_shipment(self):
        shipment = self._create_shipment(status=ShipmentStatus.DELIVERED)
        ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=ShipmentTrackingStatus.RECEIVED_RECIPIENT,
            actor_name="Agent",
            actor_structure="ASF",
            comments="partial",
            created_by=self.staff_user,
        )

        response = self.client.post(
            reverse("scan:scan_shipments_tracking"),
            {"action": "close_shipment_case", "shipment_id": shipment.id},
        )

        self.assertEqual(response.status_code, 302)
        shipment.refresh_from_db()
        self.assertIsNone(shipment.closed_at)
        self.assertIsNone(shipment.closed_by)

    def test_scan_shipment_pages_render_native_english(self):
        shipment = self._create_shipment()
        packed_shipment = self._create_shipment(status=ShipmentStatus.PACKED)
        Carton.objects.create(
            shipment=packed_shipment,
            code="CRT-I18N-READY",
            status=CartonStatus.LABELED,
        )
        self._activate_english()

        shipments_ready_response = self.client.get(reverse("scan:scan_shipments_ready"))
        self.assertContains(shipments_ready_response, "Shipments view")
        self.assertContains(shipments_ready_response, "Available")
        self.assertNotContains(shipments_ready_response, "Ready")
        self.assertNotContains(shipments_ready_response, "Vue Exp&eacute;ditions")

        shipments_tracking_response = self.client.get(reverse("scan:scan_shipments_tracking"))
        self.assertContains(shipments_tracking_response, "Shipment tracking")
        self.assertContains(shipments_tracking_response, "Planned week")
        self.assertNotContains(shipments_tracking_response, "Suivi des exp&eacute;ditions")

        shipment_create_response = self.client.get(reverse("scan:scan_shipment_create"))
        self.assertContains(shipment_create_response, "Create shipment")
        self.assertContains(shipment_create_response, "Save draft")
        self.assertNotContains(shipment_create_response, "Cr&eacute;er une exp&eacute;dition")

        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            tracking_response = self.client.get(
                reverse("scan:scan_shipment_track", args=[shipment.tracking_token])
            )
        self.assertContains(tracking_response, "Shipment tracking")
        self.assertContains(tracking_response, "Current status")
        self.assertNotContains(tracking_response, "Suivi exp&eacute;dition")

    def test_scan_pack_get_uses_session_pack_results_and_defaults(self):
        session = self.client.session
        session["pack_results"] = [10, 20]
        session.save()

        fake_form = object()
        helper_install = {"available": True, "install_url": "/scan/helper/install/"}
        with mock.patch(
            "wms.views_scan_shipments.ScanPackForm",
            return_value=fake_form,
        ):
            with mock.patch(
                "wms.views_scan_shipments.build_product_options",
                return_value=[{"id": 1}],
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_carton_formats",
                    return_value=([{"id": 1, "name": "Std"}], "default-format"),
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.build_packing_result",
                        return_value={"packed_count": 2},
                    ) as packing_result_mock:
                        with mock.patch(
                            "wms.views_scan_shipments.build_pack_defaults",
                            return_value=(
                                "1",
                                {"length_cm": 40},
                                2,
                                [{"line": 1}, {"line": 2}],
                            ),
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.build_helper_install_context",
                                return_value=helper_install,
                            ):
                                with mock.patch(
                                    "wms.views_scan_shipments.render",
                                    side_effect=self._render_stub,
                                ):
                                    response = self.client.get(reverse("scan:scan_pack"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/pack.html")
        self.assertEqual(response.context_data["packing_result"], {"packed_count": 2})
        self.assertEqual(response.context_data["helper_install"], helper_install)
        self.assertEqual(response.context_data["line_count"], 2)
        self.assertEqual(response.context_data["line_values"], [{"line": 1}, {"line": 2}])
        self.assertEqual(response.context_data["missing_defaults"], [])
        self.assertFalse(response.context_data["confirm_defaults"])
        packing_result_mock.assert_called_once_with([10, 20])

    def test_scan_pack_post_returns_handler_response_when_available(self):
        fake_form = object()
        pack_state = {
            "carton_format_id": "custom",
            "carton_custom": {"length_cm": 30},
            "line_count": 1,
            "line_values": [{"line": 1}],
            "line_errors": {},
        }
        with mock.patch(
            "wms.views_scan_shipments.ScanPackForm",
            return_value=fake_form,
        ):
            with mock.patch(
                "wms.views_scan_shipments.build_product_options",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_carton_formats",
                    return_value=([], None),
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.handle_pack_post",
                        return_value=(HttpResponse("pack-post"), pack_state),
                    ):
                        response = self.client.post(reverse("scan:scan_pack"), {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "pack-post")

    def test_scan_pack_post_renders_context_when_handler_has_no_response(self):
        fake_form = object()
        helper_install = {"available": True, "install_url": "/scan/helper/install/"}
        pack_state = {
            "carton_format_id": "1",
            "carton_custom": {"length_cm": 40},
            "line_count": 3,
            "line_values": [{"line": 1}],
            "line_errors": {"1": "invalid"},
            "missing_defaults": ["SKU-001"],
            "confirm_defaults": True,
        }
        with mock.patch(
            "wms.views_scan_shipments.ScanPackForm",
            return_value=fake_form,
        ):
            with mock.patch(
                "wms.views_scan_shipments.build_product_options",
                return_value=[{"id": 1}],
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_carton_formats",
                    return_value=([{"id": 1}], "default"),
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.handle_pack_post",
                        return_value=(None, pack_state),
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.build_helper_install_context",
                            return_value=helper_install,
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.render",
                                side_effect=self._render_stub,
                            ):
                                response = self.client.post(reverse("scan:scan_pack"), {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/pack.html")
        self.assertEqual(response.context_data["helper_install"], helper_install)
        self.assertEqual(response.context_data["line_count"], 3)
        self.assertEqual(response.context_data["line_errors"], {"1": "invalid"})
        self.assertEqual(response.context_data["missing_defaults"], ["SKU-001"])
        self.assertTrue(response.context_data["confirm_defaults"])

    def test_scan_shipment_create_get_builds_initial_line_values(self):
        fake_form = SimpleNamespace(initial={"carton_count": 2})
        helper_install = {"available": True, "install_url": "/scan/helper/install/"}
        with mock.patch(
            "wms.views_scan_shipments.ScanShipmentForm",
            return_value=fake_form,
        ):
            with mock.patch(
                "wms.views_scan_shipments.build_shipment_form_payload",
                return_value=([], [], [], [], [], []),
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_carton_selection_data",
                    return_value=("[]", set()),
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.build_shipment_line_values",
                        return_value=[{"line": 1}, {"line": 2}],
                    ) as line_values_mock:
                        with mock.patch(
                            "wms.views_scan_shipments.build_shipment_form_context",
                            return_value={"context_key": "value"},
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.build_helper_install_context",
                                return_value=helper_install,
                            ):
                                with mock.patch(
                                    "wms.views_scan_shipments.render",
                                    side_effect=self._render_stub,
                                ):
                                    response = self.client.get(reverse("scan:scan_shipment_create"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/shipment_create.html")
        self.assertEqual(response.context_data["context_key"], "value")
        self.assertEqual(response.context_data["active"], "shipment")
        self.assertEqual(response.context_data["helper_install"], helper_install)
        line_values_mock.assert_called_once_with(2)

    def test_scan_shipment_create_post_returns_handler_response_when_available(self):
        fake_form = SimpleNamespace(initial={"carton_count": 1})
        with mock.patch(
            "wms.views_scan_shipments.ScanShipmentForm",
            return_value=fake_form,
        ):
            with mock.patch(
                "wms.views_scan_shipments.build_shipment_form_payload",
                return_value=([], [], [], [], [], []),
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_carton_selection_data",
                    return_value=("[]", {1}),
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.handle_shipment_create_post",
                        return_value=(HttpResponse("created"), 1, [], {}),
                    ):
                        response = self.client.post(reverse("scan:scan_shipment_create"), {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "created")

    def test_scan_shipment_create_post_renders_context_when_no_handler_response(self):
        fake_form = SimpleNamespace(initial={"carton_count": 1})
        helper_install = {"available": True, "install_url": "/scan/helper/install/"}
        with mock.patch(
            "wms.views_scan_shipments.ScanShipmentForm",
            return_value=fake_form,
        ):
            with mock.patch(
                "wms.views_scan_shipments.build_shipment_form_payload",
                return_value=([], [], [], [], [], []),
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_carton_selection_data",
                    return_value=("[]", {1}),
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.handle_shipment_create_post",
                        return_value=(None, 3, [{"line": 1}], {"1": "err"}),
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.build_shipment_form_context",
                            return_value={"context_key": "post"},
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.build_helper_install_context",
                                return_value=helper_install,
                            ):
                                with mock.patch(
                                    "wms.views_scan_shipments.render",
                                    side_effect=self._render_stub,
                                ):
                                    response = self.client.post(
                                        reverse("scan:scan_shipment_create"), {}
                                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/shipment_create.html")
        self.assertEqual(response.context_data["context_key"], "post")
        self.assertEqual(response.context_data["active"], "shipment")
        self.assertEqual(response.context_data["helper_install"], helper_install)

    def test_scan_shipment_create_exposes_preassigned_carton_metadata_and_confirmation_modal(
        self,
    ):
        correspondent = Contact.objects.create(name="Correspondent create modal")
        destination = Destination.objects.create(
            city="Nouakchott",
            iata_code="NKC",
            country="Mauritanie",
            correspondent_contact=correspondent,
            is_active=True,
        )
        Carton.objects.create(
            code="MM-00003",
            status=CartonStatus.PACKED,
            preassigned_destination=destination,
        )

        response = self.client.get(reverse("scan:scan_shipment_create"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cartons_json"][0]["preassigned_destination_iata"], "NKC")
        self.assertEqual(response.context["cartons_json"][0]["label"], "MM-00003 (NKC)")
        self.assertContains(response, 'id="shipment-preassignment-overlay"')
        self.assertContains(response, "Ce colis est déjà affecté pour __EXPECTED__.")
        self.assertContains(response, "Valider")
        self.assertContains(response, "Refuser")

    def test_scan_shipment_create_translates_preassignment_confirmation_in_english(self):
        self._activate_english()
        correspondent = Contact.objects.create(name="Correspondent create modal en")
        destination = Destination.objects.create(
            city="Nouakchott",
            iata_code="NKC",
            country="Mauritanie",
            correspondent_contact=correspondent,
            is_active=True,
        )
        Carton.objects.create(
            code="MM-00004",
            status=CartonStatus.PACKED,
            preassigned_destination=destination,
        )

        response = self.client.get(reverse("scan:scan_shipment_create"))

        self.assertContains(response, "Destination preassignment")
        self.assertContains(response, "Accept")
        self.assertContains(response, "Reject")
        self.assertNotContains(response, "Pré-affectation destination")

    def test_scan_shipment_edit_redirects_when_shipment_is_not_editable(self):
        shipment = self._create_shipment(status=ShipmentStatus.SHIPPED)
        response = self.client.get(
            reverse("scan:scan_shipment_edit", kwargs={"shipment_id": shipment.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_shipments_ready"))

    def test_scan_shipment_edit_get_renders_context(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        carton = Carton.objects.create(code="C-EDIT-1", shipment=shipment)
        fake_form = object()
        initial = {"destination": "", "carton_count": 1}
        helper_install = {"available": True, "install_url": "/scan/helper/install/"}

        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.build_carton_options",
                return_value=[{"id": carton.id, "code": carton.code}],
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_shipment_edit_initial",
                    return_value=initial,
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.ScanShipmentForm",
                        return_value=fake_form,
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.build_shipment_form_payload",
                            return_value=([], [], [], [], [], []),
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.build_carton_selection_data",
                                return_value=("[]", {carton.id}),
                            ):
                                with mock.patch(
                                    "wms.views_scan_shipments.build_shipment_edit_line_values",
                                    return_value=[{"line": 1}],
                                ):
                                    with mock.patch(
                                        "wms.views_scan_shipments.build_shipment_form_context",
                                        return_value={"context_key": "edit-get"},
                                    ):
                                        with mock.patch(
                                            "wms.views_scan_shipments.build_helper_install_context",
                                            return_value=helper_install,
                                        ):
                                            with mock.patch(
                                                "wms.views_scan_shipments.render",
                                                side_effect=self._render_stub,
                                            ):
                                                response = self.client.get(
                                                    reverse(
                                                        "scan:scan_shipment_edit",
                                                        kwargs={"shipment_id": shipment.id},
                                                    )
                                                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/shipment_create.html")
        self.assertEqual(response.context_data["context_key"], "edit-get")
        self.assertEqual(response.context_data["helper_install"], helper_install)
        self.assertTrue(response.context_data["is_edit"])
        self.assertEqual(response.context_data["shipment"].id, shipment.id)
        self.assertIn("tracking_url", response.context_data)
        self.assertEqual(
            response.context_data["carton_docs"], [{"id": carton.id, "code": carton.code}]
        )

    def test_scan_shipment_edit_post_returns_handler_response_when_available(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        fake_form = object()
        initial = {"destination": "", "carton_count": 1}

        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.build_carton_options",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_shipment_edit_initial",
                    return_value=initial,
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.ScanShipmentForm",
                        return_value=fake_form,
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.build_shipment_form_payload",
                            return_value=([], [], [], [], [], []),
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.build_carton_selection_data",
                                return_value=("[]", set()),
                            ):
                                with mock.patch(
                                    "wms.views_scan_shipments.handle_shipment_edit_post",
                                    return_value=(HttpResponse("edited"), 1, [], {}),
                                ):
                                    response = self.client.post(
                                        reverse(
                                            "scan:scan_shipment_edit",
                                            kwargs={"shipment_id": shipment.id},
                                        ),
                                        {},
                                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "edited")

    def test_scan_shipment_edit_post_renders_context_when_no_handler_response(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        fake_form = object()
        initial = {"destination": "", "carton_count": 2}
        helper_install = {"available": True, "install_url": "/scan/helper/install/"}

        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.build_carton_options",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_shipment_edit_initial",
                    return_value=initial,
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.ScanShipmentForm",
                        return_value=fake_form,
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.build_shipment_form_payload",
                            return_value=([], [], [], [], [], []),
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.build_carton_selection_data",
                                return_value=("[]", set()),
                            ):
                                with mock.patch(
                                    "wms.views_scan_shipments.handle_shipment_edit_post",
                                    return_value=(None, 2, [{"line": 1}], {"1": "err"}),
                                ):
                                    with mock.patch(
                                        "wms.views_scan_shipments.build_shipment_form_context",
                                        return_value={"context_key": "edit-post"},
                                    ):
                                        with mock.patch(
                                            "wms.views_scan_shipments.build_helper_install_context",
                                            return_value=helper_install,
                                        ):
                                            with mock.patch(
                                                "wms.views_scan_shipments.render",
                                                side_effect=self._render_stub,
                                            ):
                                                response = self.client.post(
                                                    reverse(
                                                        "scan:scan_shipment_edit",
                                                        kwargs={"shipment_id": shipment.id},
                                                    ),
                                                    {},
                                                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/shipment_create.html")
        self.assertEqual(response.context_data["context_key"], "edit-post")
        self.assertEqual(response.context_data["helper_install"], helper_install)
        self.assertTrue(response.context_data["is_edit"])

    def test_scan_shipment_track_get_renders_tracking_context(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        fake_form = object()
        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.build_shipment_document_links",
                return_value=(["doc"], ["carton"], ["additional"]),
            ):
                with mock.patch(
                    "wms.views_scan_shipments.next_tracking_status",
                    return_value="planning_ok",
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.ShipmentTrackingForm",
                        return_value=fake_form,
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.handle_shipment_tracking_post",
                            return_value=None,
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.render",
                                side_effect=self._render_stub,
                            ):
                                response = self.client.get(
                                    reverse(
                                        "scan:scan_shipment_track",
                                        kwargs={"tracking_token": shipment.tracking_token},
                                    )
                                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/shipment_tracking.html")
        self.assertTrue(response.context_data["can_update_tracking"])
        self.assertEqual(response.context_data["documents"], ["doc"])
        self.assertEqual(response.context_data["carton_docs"], ["carton"])
        self.assertEqual(response.context_data["additional_docs"], ["additional"])
        self.assertIs(response.context_data["form"], fake_form)
        self.assertEqual(response.context_data["return_to"], "shipments_tracking")

    def test_scan_shipment_track_post_returns_handler_response(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.build_shipment_document_links",
                return_value=([], [], []),
            ):
                with mock.patch(
                    "wms.views_scan_shipments.next_tracking_status",
                    return_value="planning_ok",
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.ShipmentTrackingForm",
                        return_value=object(),
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.handle_shipment_tracking_post",
                            return_value=HttpResponse("tracking-post"),
                        ) as handler_mock:
                            response = self.client.post(
                                reverse(
                                    "scan:scan_shipment_track",
                                    kwargs={"tracking_token": shipment.tracking_token},
                                ),
                                {"status": "planning_ok"},
                            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "tracking-post")
        self.assertFalse(handler_mock.call_args.kwargs["return_to_list"])
        self.assertIsNone(handler_mock.call_args.kwargs["return_to_view"])
        self.assertEqual(handler_mock.call_args.kwargs["return_to_key"], "shipments_tracking")

    def test_scan_shipment_track_post_passes_return_to_list_flag(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.build_shipment_document_links",
                return_value=([], [], []),
            ):
                with mock.patch(
                    "wms.views_scan_shipments.next_tracking_status",
                    return_value="planning_ok",
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.ShipmentTrackingForm",
                        return_value=object(),
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.handle_shipment_tracking_post",
                            return_value=HttpResponse("tracking-post"),
                        ) as handler_mock:
                            response = self.client.post(
                                reverse(
                                    "scan:scan_shipment_track",
                                    kwargs={"tracking_token": shipment.tracking_token},
                                ),
                                {"status": "planning_ok", "return_to_list": "1"},
                            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "tracking-post")
        self.assertTrue(handler_mock.call_args.kwargs["return_to_list"])
        self.assertEqual(
            handler_mock.call_args.kwargs["return_to_view"],
            "scan:scan_shipments_tracking",
        )
        self.assertEqual(handler_mock.call_args.kwargs["return_to_key"], "shipments_tracking")

    def test_scan_shipment_track_get_uses_ready_return_target(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.build_shipment_document_links",
                return_value=([], [], []),
            ):
                with mock.patch(
                    "wms.views_scan_shipments.next_tracking_status",
                    return_value="planning_ok",
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.ShipmentTrackingForm",
                        return_value=object(),
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.handle_shipment_tracking_post",
                            return_value=None,
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.render",
                                side_effect=self._render_stub,
                            ):
                                response = self.client.get(
                                    f"{reverse('scan:scan_shipment_track', kwargs={'tracking_token': shipment.tracking_token})}?return_to=shipments_ready"
                                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["return_to"], "shipments_ready")
        self.assertEqual(
            response.context_data["back_to_url"],
            reverse("scan:scan_shipments_ready"),
        )

    def test_scan_shipment_track_legacy_renders_read_only_tracking(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.build_shipment_document_links",
                return_value=(["doc"], ["carton"], ["additional"]),
            ):
                with mock.patch(
                    "wms.views_scan_shipments.render",
                    side_effect=self._render_stub,
                ):
                    response = self.client.get(
                        reverse(
                            "scan:scan_shipment_track_legacy",
                            kwargs={"shipment_ref": shipment.reference},
                        )
                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/shipment_tracking.html")
        self.assertFalse(response.context_data["can_update_tracking"])
        self.assertIsNone(response.context_data["form"])
        self.assertEqual(response.context_data["tracking_url"], "")
        self.assertEqual(
            response["X-ASF-Legacy-Endpoint"],
            "shipment-track-by-reference; status=deprecated",
        )
        self.assertEqual(response["X-ASF-Legacy-Sunset"], "2026-06-30")

    @override_settings(ENABLE_SHIPMENT_TRACK_LEGACY=False)
    def test_scan_shipment_track_legacy_returns_404_when_feature_disabled(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        response = self.client.get(
            reverse(
                "scan:scan_shipment_track_legacy",
                kwargs={"shipment_ref": shipment.reference},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_scan_shipment_track_legacy_returns_404_for_non_staff_user(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        non_staff = get_user_model().objects.create_user(
            username="scan-shipments-non-staff",
            password="pass1234",
            is_staff=False,
        )
        self.client.force_login(non_staff)
        response = self.client.get(
            reverse(
                "scan:scan_shipment_track_legacy",
                kwargs={"shipment_ref": shipment.reference},
            )
        )
        self.assertEqual(response.status_code, 404)
