from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms.helper_install import build_helper_install_context
from wms.models import (
    Carton,
    CartonFormat,
    CartonItem,
    CartonSourceKind,
    CartonStatus,
    CartonVolunteerActivity,
    CartonVolunteerActivityAction,
    Destination,
    Location,
    Order,
    OrderInboundArrivalMode,
    OrderInboundDelivery,
    OrderReviewStatus,
    OrderShipmentLink,
    Product,
    ProductCategory,
    ProductLot,
    PublicAccountRequest,
    PublicAccountRequestStatus,
    PublicAccountRequestType,
    Receipt,
    ReceiptShipmentAllocation,
    ReceiptType,
    RecipientProductPreference,
    RecipientProductPreferenceStatus,
    Shipment,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentStatus,
    ShipmentTrackingAccessGrant,
    ShipmentTrackingAccessRole,
    ShipmentTrackingEvent,
    ShipmentTrackingIdentityStatus,
    ShipmentTrackingStatus,
    ShipmentValidationStatus,
    VolunteerAccountRequest,
    VolunteerAccountRequestStatus,
    VolunteerProfile,
    Warehouse,
    WmsRuntimeSettings,
)
from wms.shipment_tracking_access import ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY
from wms.shipment_view_helpers import build_shipments_tracking_rows
from wms.views_scan_shipments import (
    _annotate_carton_selection_compatibility,
    _assign_pending_contact_to_shipment,
    _build_tracking_login_url,
    _build_tracking_set_password_url,
    _get_or_create_tracking_pending_user,
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

    def _create_shipment(
        self,
        *,
        status=ShipmentStatus.DRAFT,
        reference=None,
        destination=None,
        shipper_name="Aviation Sans Frontieres",
    ):
        return Shipment.objects.create(
            reference=reference,
            status=status,
            shipper_name=shipper_name,
            recipient_name="Association Dest",
            destination=destination,
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.staff_user,
        )

    def _create_tracking_event(self, shipment, status, *, created_at=None):
        event = ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=status,
            actor_name="Ops",
            actor_structure="ASF",
            comments="step",
            created_by=self.staff_user,
        )
        if created_at is not None:
            ShipmentTrackingEvent.objects.filter(pk=event.pk).update(created_at=created_at)
            event.created_at = created_at
        return event

    def _mark_shipment_planned(self, shipment, *, created_at=None):
        return self._create_tracking_event(
            shipment,
            ShipmentTrackingStatus.PLANNED,
            created_at=created_at,
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

    def _get_test_product_lot(self):
        if hasattr(self, "_test_product_lot"):
            return self._test_product_lot
        warehouse = Warehouse.objects.create(name="Main test warehouse")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        product = Product.objects.create(
            sku="SKU-SHIPMENTS-1",
            name="Compresses",
            brand="ACME",
        )
        self._test_product_lot = ProductLot.objects.create(
            product=product,
            lot_code="LOT-SHIPMENTS-1",
            quantity_on_hand=20,
            location=location,
        )
        return self._test_product_lot

    def _create_product_lot(
        self,
        *,
        sku,
        name,
        barcode="",
        ean="",
        quantity_on_hand=20,
    ):
        base_lot = self._get_test_product_lot()
        product = Product.objects.create(
            sku=sku,
            name=name,
            barcode=barcode,
            ean=ean,
        )
        return ProductLot.objects.create(
            product=product,
            lot_code=f"LOT-{sku}",
            quantity_on_hand=quantity_on_hand,
            location=base_lot.location,
        )

    def _create_carton_with_item(
        self,
        *,
        code,
        shipment=None,
        status=CartonStatus.PACKED,
        product_lot=None,
        preassigned_destination=None,
        created_at=None,
        prepared_by=None,
    ):
        carton = Carton.objects.create(
            code=code,
            shipment=shipment,
            status=status,
            preassigned_destination=preassigned_destination,
            prepared_by=prepared_by,
        )
        CartonItem.objects.create(
            carton=carton,
            product_lot=product_lot or self._get_test_product_lot(),
            quantity=1,
        )
        if created_at is not None:
            Carton.objects.filter(pk=carton.pk).update(created_at=created_at)
            carton.created_at = created_at
        return carton

    def _create_shipment_party_triplet(self, code):
        correspondent_org = Contact.objects.create(
            name=f"Correspondent Org {code}",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        correspondent = Contact.objects.create(
            name=f"Correspondent {code}",
            contact_type=ContactType.PERSON,
            first_name="Correspondent",
            last_name=code,
            organization=correspondent_org,
            is_active=True,
        )
        destination = Destination.objects.create(
            city=f"Destination {code}",
            iata_code=code,
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=correspondent_org,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_correspondent=True,
            is_active=True,
        )

        shipper_org = Contact.objects.create(
            name=f"Shipper Org {code}",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_contact = Contact.objects.create(
            name=f"Shipper {code}",
            contact_type=ContactType.PERSON,
            first_name="Shipper",
            last_name=code,
            organization=shipper_org,
            is_active=True,
        )
        shipper = ShipmentShipper.objects.create(
            organization=shipper_org,
            default_contact=shipper_contact,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

        recipient_org_contact = Contact.objects.create(
            name=f"Recipient Org {code}",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=recipient_org_contact,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        recipient_contact = Contact.objects.create(
            name=f"Recipient {code}",
            contact_type=ContactType.PERSON,
            first_name="Recipient",
            last_name=code,
            organization=recipient_org_contact,
            is_active=True,
        )
        shipment_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_org,
            contact=recipient_contact,
            is_active=True,
        )
        link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient_org,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=shipment_recipient_contact,
            is_default=True,
            is_active=True,
        )
        return destination, shipper_contact, recipient_contact, correspondent

    def test_tracking_pending_account_helpers_create_update_and_assign(self):
        created_user = _get_or_create_tracking_pending_user(
            email="pending-new@example.com",
            role=ShipmentTrackingAccessRole.SHIPPER,
            identifier="ASF-PENDING",
            first_name="Ada",
            last_name="Lovelace",
        )
        existing_user = get_user_model().objects.create_user(
            username="pending-existing",
            email="pending-existing@example.com",
            password="pass1234",
            first_name="Old",
            is_active=False,
        )

        updated_user = _get_or_create_tracking_pending_user(
            email=existing_user.email,
            role=ShipmentTrackingAccessRole.VOLUNTEER,
            identifier="VOL-1",
            first_name="Grace",
            last_name="Hopper",
        )

        created_user.refresh_from_db()
        updated_user.refresh_from_db()
        self.assertEqual(created_user.first_name, "Ada")
        self.assertFalse(created_user.has_usable_password())
        self.assertEqual(updated_user.first_name, "Grace")
        self.assertEqual(updated_user.last_name, "Hopper")
        self.assertTrue(updated_user.is_active)

        shipment = self._create_shipment(reference="SHP-PENDING-ASSIGN")
        shipper = Contact.objects.create(name="Pending Shipper", email="shipper@example.com")
        recipient = Contact.objects.create(name="Pending Recipient", email="recipient@example.com")
        correspondent = Contact.objects.create(
            name="Pending Correspondent",
            email="correspondent@example.com",
        )

        _assign_pending_contact_to_shipment(
            shipment=shipment,
            role=ShipmentTrackingAccessRole.SHIPPER,
            contact=shipper,
        )
        _assign_pending_contact_to_shipment(
            shipment=shipment,
            role=ShipmentTrackingAccessRole.RECIPIENT,
            contact=recipient,
        )
        _assign_pending_contact_to_shipment(
            shipment=shipment,
            role=ShipmentTrackingAccessRole.CORRESPONDENT,
            contact=correspondent,
        )

        shipment.refresh_from_db()
        self.assertEqual(shipment.shipper_contact_ref, shipper)
        self.assertEqual(shipment.recipient_contact_ref, recipient)
        self.assertEqual(shipment.correspondent_contact_ref, correspondent)

    def test_tracking_pending_account_url_helpers_include_next_and_grant(self):
        shipment = self._create_shipment(reference="SHP-PENDING-URL")
        contact = Contact.objects.create(
            name="Pending URL Contact", email="pending-url@example.com"
        )
        user = get_user_model().objects.create_user(
            username="pending-url-user",
            email=contact.email,
            password="pass1234",
        )
        grant = ShipmentTrackingAccessGrant.objects.create(
            user=user,
            role=ShipmentTrackingAccessRole.SHIPPER,
            contact=contact,
            identity_status=ShipmentTrackingIdentityStatus.PENDING,
        )
        request = self.factory.get("/")

        login_url = _build_tracking_login_url(
            shipment=shipment,
            role=ShipmentTrackingAccessRole.SHIPPER,
            identifier=contact.asf_id,
        )
        set_password_url = _build_tracking_set_password_url(
            request,
            user=user,
            grant=grant,
            next_url=login_url,
        )

        self.assertIn(reverse("scan:scan_shipment_tracking_access_login"), login_url)
        self.assertIn(str(shipment.tracking_token), login_url)
        self.assertIn(contact.asf_id, login_url)
        self.assertIn("/scan/shipment/track/access/set-password/", set_password_url)
        self.assertIn(f"grant={grant.id}", set_password_url)

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

    def test_scan_shipment_create_prefills_parties_and_lines_from_querystring(self):
        fake_form = object()
        with (
            mock.patch(
                "wms.views_scan_shipments.ScanShipmentForm",
                return_value=fake_form,
            ) as form_mock,
            mock.patch(
                "wms.views_scan_shipments._build_shipment_form_support",
                return_value={"allowed_carton_ids": set()},
            ),
            mock.patch(
                "wms.views_scan_shipments._render_shipment_form",
                return_value=HttpResponse("prefilled"),
            ) as render_mock,
        ):
            response = self.client.get(
                reverse("scan:scan_shipment_create"),
                {
                    "destination": "12",
                    "shipper_contact": "34",
                    "recipient_contact": "56",
                    "carton_count": "2",
                    "line_1_product_code": "SKU-001",
                    "line_1_quantity": "7",
                    "line_2_product_code": "SKU-002",
                    "line_2_quantity": "3",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "prefilled")
        form_mock.assert_called_once_with(
            None,
            destination_id="12",
            initial={
                "destination": "12",
                "shipper_contact": "34",
                "recipient_contact": "56",
                "carton_count": 2,
            },
        )
        self.assertEqual(render_mock.call_args.kwargs["carton_count"], 2)
        self.assertEqual(
            render_mock.call_args.kwargs["line_values"],
            [
                {
                    "carton_id": "",
                    "product_code": "SKU-001",
                    "quantity": "7",
                    "expires_on": "",
                },
                {
                    "carton_id": "",
                    "product_code": "SKU-002",
                    "quantity": "3",
                    "expires_on": "",
                },
            ],
        )

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

    def test_scan_cartons_ready_exposes_batch_shipment_assignment_controls(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        self._create_carton_with_item(code="C-ASSIGN-UI")

        response = self.client.get(reverse("scan:scan_cartons_ready"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="bulk_assign_cartons_shipment"')
        self.assertContains(response, 'name="bulk_shipment_id"')
        self.assertContains(response, shipment.reference)

    def test_annotate_carton_selection_compatibility_skips_invalid_rows_and_ids(self):
        cartons_json = [
            "invalid-row",
            {},
            {"id": "invalid-id"},
            {"id": 999999},
        ]
        recipient_contacts_json = [
            {
                "recipient_organization_ids_by_destination_id": {
                    "1": "invalid",
                    "2": None,
                }
            }
        ]

        _annotate_carton_selection_compatibility(
            cartons_json=cartons_json,
            recipient_contacts_json=recipient_contacts_json,
        )

        self.assertEqual(
            cartons_json[1]["compatibility_by_recipient_organization_id"],
            {},
        )
        self.assertEqual(
            cartons_json[2]["compatibility_by_recipient_organization_id"],
            {},
        )
        self.assertEqual(
            cartons_json[3]["compatibility_by_recipient_organization_id"],
            {},
        )

    def test_annotate_carton_selection_compatibility_limits_queries_for_multiple_rows(self):
        correspondent = Contact.objects.create(
            name="Correspondent ABJ",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="COTE D'IVOIRE",
            correspondent_contact=correspondent,
            is_active=True,
        )
        secondary_product = Product.objects.create(
            sku="SKU-SHIPMENTS-2",
            name="Bandages",
            brand="ACME",
        )
        secondary_lot = ProductLot.objects.create(
            product=secondary_product,
            lot_code="LOT-SHIPMENTS-2",
            quantity_on_hand=20,
            location=self._get_test_product_lot().location,
        )
        recipient_organizations = []
        recipient_contacts_json = []
        for index in range(4):
            organization = Contact.objects.create(
                name=f"Recipient org {index}",
                contact_type=ContactType.ORGANIZATION,
                is_active=True,
            )
            recipient_organization = ShipmentRecipientOrganization.objects.create(
                organization=organization,
                destination=destination,
                validation_status="validated",
                is_active=True,
            )
            RecipientProductPreference.objects.create(
                recipient_organization=recipient_organization,
                product=self._get_test_product_lot().product,
                status=RecipientProductPreferenceStatus.REQUESTED,
                quantity_target=10,
                period_unit="week",
                updated_by=self.staff_user,
            )
            recipient_organizations.append(recipient_organization)
            recipient_contacts_json.append(
                {
                    "recipient_organization_ids_by_destination_id": {
                        str(destination.id): recipient_organization.id,
                    }
                }
            )

        cartons = []
        for index in range(4):
            carton = Carton.objects.create(code=f"C-BULK-{index}", status=CartonStatus.PACKED)
            CartonItem.objects.create(
                carton=carton,
                product_lot=self._get_test_product_lot(),
                quantity=1,
            )
            CartonItem.objects.create(
                carton=carton,
                product_lot=secondary_lot,
                quantity=1,
            )
            cartons.append(carton)
        cartons_json = [{"id": carton.id} for carton in cartons]

        previous_debug_cursor = connection.force_debug_cursor
        connection.force_debug_cursor = True
        try:
            with CaptureQueriesContext(connection) as ctx:
                _annotate_carton_selection_compatibility(
                    cartons_json=cartons_json,
                    recipient_contacts_json=recipient_contacts_json,
                )
        finally:
            connection.force_debug_cursor = previous_debug_cursor

        self.assertLessEqual(len(ctx), 12)
        for carton_row in cartons_json:
            for recipient_organization in recipient_organizations:
                self.assertEqual(
                    carton_row["compatibility_by_recipient_organization_id"][
                        str(recipient_organization.id)
                    ]["bucket"],
                    "tres_adaptes",
                )

    def test_scan_cartons_ready_uses_fixed_width_select_classes_and_descending_shipment_order(self):
        older = self._create_shipment(status=ShipmentStatus.DRAFT, reference="250999")
        newer = self._create_shipment(status=ShipmentStatus.DRAFT, reference="260014")
        self._create_carton_with_item(code="C-ASSIGN-ORDER")

        response = self.client.get(reverse("scan:scan_cartons_ready"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-carton-bulk-action-select")
        self.assertContains(response, "scan-carton-bulk-shipment-select")
        self.assertContains(response, "ui-select--sm")
        self.assertContains(response, "ui-select--xl")
        self.assertNotContains(response, "w-auto scan-carton-bulk-action-select")
        self.assertNotContains(response, "w-auto scan-carton-bulk-shipment-select")
        content = response.content.decode()
        self.assertLess(content.index(newer.reference), content.index(older.reference))

    def test_scan_cartons_ready_assigns_selected_cartons_when_only_target_shipment_is_posted(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        carton_a = self._create_carton_with_item(code="C-ASSIGN-FALLBACK-1")
        carton_b = self._create_carton_with_item(code="C-ASSIGN-FALLBACK-2")

        response = self.client.post(
            reverse("scan:scan_cartons_ready"),
            {
                "bulk_shipment_id": str(shipment.id),
                "selected_carton_ids": [str(carton_a.id), str(carton_b.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        carton_a.refresh_from_db()
        carton_b.refresh_from_db()
        shipment.refresh_from_db()
        self.assertEqual(carton_a.shipment_id, shipment.id)
        self.assertEqual(carton_b.shipment_id, shipment.id)
        self.assertEqual(carton_a.status, CartonStatus.ASSIGNED)
        self.assertEqual(carton_b.status, CartonStatus.ASSIGNED)
        self.assertEqual(shipment.status, ShipmentStatus.PICKING)

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
        self.assertEqual(response.context_data["active"], "shipments_dossiers")
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

    def test_scan_shipments_ready_renders_dossiers_title_and_search_form(self):
        response = self.client.get(reverse("scan:scan_shipments_ready"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dossiers")
        self.assertContains(response, 'name="q"')
        self.assertContains(response, "Rechercher une expédition")

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
                    "documents_summary": "6 docs",
                }
            ],
        ):
            response = self.client.get(reverse("scan:scan_shipments_ready"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-shipments-ready-table")
        self.assertContains(response, "scan-shipment-reference-col")
        self.assertContains(response, "scan-shipments-ready-head-label")
        self.assertContains(response, "Nb Colis Equivalent")
        self.assertContains(response, "scan-shipment-ready-col")
        self.assertContains(response, "6 docs")
        self.assertContains(response, "scan-shipment-status-cell")
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

    def test_scan_cartons_ready_uses_bulk_toolbar_and_open_action(self):
        with mock.patch(
            "wms.views_scan_shipments.build_cartons_ready_rows",
            return_value=[
                {
                    "id": 1,
                    "code": "C-READY",
                    "created_at": None,
                    "status_label": "Prêt",
                    "status_value": CartonStatus.PACKED,
                    "status_tone": "ready",
                    "status_badges": [
                        {"label": "Disponible", "variant": "prep-packed"},
                        {"label": "Libre", "variant": "assignment-free"},
                    ],
                    "detail_url": "/scan/carton/1/edit/",
                    "shipment_reference": "",
                    "product_rows": [
                        {"label": "Compresses", "quantity": 50, "display": "Compresses x 50"},
                        {"label": "Gants", "quantity": 2, "display": "Gants x 2"},
                    ],
                    "has_packing_list": True,
                    "has_picking": True,
                    "preparation_status_value": CartonStatus.PACKED,
                    "is_assigned": False,
                    "shipment_id": None,
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
                    "status_badges": [
                        {"label": "Créé", "variant": "prep-draft"},
                        {"label": "Affecté", "variant": "assignment-assigned"},
                    ],
                    "detail_url": "/scan/carton/2/edit/",
                    "shipment_reference": "S-001",
                    "product_rows": [
                        {"label": "Mask (lot L1)", "quantity": 2, "display": "Mask (lot L1) x 2"},
                    ],
                    "has_packing_list": True,
                    "has_picking": True,
                    "preparation_status_value": CartonStatus.DRAFT,
                    "is_assigned": True,
                    "shipment_id": 1,
                    "weight_kg": None,
                    "volume_percent": None,
                },
            ],
        ):
            response = self.client.get(reverse("scan:scan_cartons_ready"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="carton-bulk-actions"')
        self.assertContains(response, 'name="selected_carton_ids"')
        self.assertContains(response, 'name="bulk_action"')
        self.assertContains(response, "scan-carton-bulk-action-select")
        self.assertContains(response, "scan-carton-table-head")
        self.assertContains(response, "scan-carton-table-head-label")
        self.assertContains(
            response,
            'name="bulk_document" value="packing_lists" class="scan-scan-btn btn btn-outline-secondary"',
        )
        self.assertContains(
            response,
            'name="bulk_document" value="picking" class="scan-scan-btn btn btn-outline-success"',
        )
        self.assertContains(response, "scan-carton-status-col")
        self.assertContains(response, "scan-carton-select-checkbox")
        self.assertContains(response, 'id="carton-select-all"')
        self.assertContains(response, 'data-carton-select-all="1"')
        self.assertContains(response, "Produits")
        self.assertContains(response, "Marquer en préparation")
        self.assertContains(response, "Marquer prêt / disponible")
        self.assertContains(response, "Marquer affecté")
        self.assertContains(response, "Compresses x 50")
        self.assertContains(response, "Gants x 2")
        self.assertContains(response, "Mask (lot L1) x 2")
        self.assertContains(response, "Disponible")
        self.assertContains(response, "Créé")
        self.assertContains(response, 'href="/scan/carton/1/edit/"')
        self.assertContains(response, "Ouvrir")
        self.assertContains(response, 'id="carton-status-skip-confirmation-overlay"')
        self.assertContains(response, 'name="confirm_skipped_statuses"')
        self.assertContains(response, "scan/modules/cartons-ready.js")
        self.assertContains(
            response,
            "scan-carton-status-pill--prep-packed",
        )
        self.assertContains(response, "scan-carton-status-pill--assignment-assigned")
        self.assertContains(response, "scan-carton-status-pill--assignment-free")
        self.assertNotContains(response, ">Documents<", html=False)
        self.assertNotContains(response, "scan-carton-status-select-wrap")
        self.assertNotContains(response, "Imprimer / télécharger")
        self.assertNotContains(response, 'class="scan-scan-btn btn btn-danger"')
        self.assertNotContains(response, "Emplacement")
        self.assertNotContains(response, "Remplissage")
        self.assertNotContains(response, "Contenu")

    def test_scan_cartons_ready_filters_by_shipment_reference_querystring(self):
        matched_shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        other_shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        self._create_carton_with_item(code="C-MATCH", shipment=matched_shipment)
        self._create_carton_with_item(code="C-OTHER", shipment=other_shipment)

        response = self.client.get(
            reverse("scan:scan_cartons_ready"),
            {"shipment_reference": matched_shipment.reference},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "C-MATCH")
        self.assertNotContains(response, "C-OTHER")
        self.assertContains(response, f"Expédition filtrée : {matched_shipment.reference}")
        self.assertContains(response, "Voir tous les colis")

    def test_scan_cartons_ready_filters_free_available_cartons(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        self._create_carton_with_item(code="C-FREE-READY", status=CartonStatus.PACKED)
        self._create_carton_with_item(
            code="C-FREE-DRAFT",
            status=CartonStatus.DRAFT,
        )
        self._create_carton_with_item(
            code="C-ASSIGNED",
            shipment=shipment,
            status=CartonStatus.PACKED,
        )

        response = self.client.get(
            reverse("scan:scan_cartons_ready"),
            {"assignment": "free", "status": CartonStatus.PACKED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "C-FREE-READY")
        self.assertNotContains(response, "C-FREE-DRAFT")
        self.assertNotContains(response, "C-ASSIGNED")
        self.assertContains(response, 'name="assignment"')
        self.assertContains(response, 'value="free" selected')
        self.assertContains(response, 'name="status"')

    def test_scan_cartons_ready_filters_assigned_and_preassigned_cartons(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        destination, _shipper, _recipient, _correspondent = self._create_shipment_party_triplet(
            "LFW"
        )
        self._create_carton_with_item(code="C-FREE")
        self._create_carton_with_item(code="C-ASSIGNED", shipment=shipment)
        self._create_carton_with_item(
            code="C-PREASSIGNED",
            preassigned_destination=destination,
        )

        assigned_response = self.client.get(
            reverse("scan:scan_cartons_ready"),
            {"assignment": "assigned"},
        )
        preassigned_response = self.client.get(
            reverse("scan:scan_cartons_ready"),
            {"assignment": "preassigned"},
        )

        self.assertEqual(assigned_response.status_code, 200)
        self.assertContains(assigned_response, "C-ASSIGNED")
        self.assertNotContains(assigned_response, "C-FREE")
        self.assertNotContains(assigned_response, "C-PREASSIGNED")
        self.assertContains(assigned_response, 'value="assigned" selected')
        self.assertEqual(preassigned_response.status_code, 200)
        self.assertContains(preassigned_response, "C-PREASSIGNED")
        self.assertNotContains(preassigned_response, "C-FREE")
        self.assertNotContains(preassigned_response, "C-ASSIGNED")
        self.assertContains(preassigned_response, 'value="preassigned" selected')

    def test_scan_cartons_ready_ignores_invalid_filter_values(self):
        self._create_carton_with_item(code="C-INVALID-FILTER-A")
        self._create_carton_with_item(code="C-INVALID-FILTER-B")

        response = self.client.get(
            reverse("scan:scan_cartons_ready"),
            {
                "assignment": "outside",
                "status": "outside",
                "created_on": "not-a-date",
                "prepared_by": "not-a-volunteer-id",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "C-INVALID-FILTER-A")
        self.assertContains(response, "C-INVALID-FILTER-B")
        self.assertNotContains(response, 'value="outside" selected')

    def test_scan_cartons_ready_filters_by_product_query(self):
        syringe_lot = self._create_product_lot(
            sku="SYRINGE-FILTER",
            name="Seringues 10ml",
            barcode="BAR-SYR",
            ean="EAN-SYR",
        )
        gloves_lot = self._create_product_lot(
            sku="GLOVES-FILTER",
            name="Gants nitrile",
        )
        self._create_carton_with_item(code="C-SYRINGE", product_lot=syringe_lot)
        self._create_carton_with_item(code="C-GLOVES", product_lot=gloves_lot)

        response = self.client.get(reverse("scan:scan_cartons_ready"), {"q": "seringue"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "C-SYRINGE")
        self.assertContains(response, "Seringues 10ml")
        self.assertNotContains(response, "C-GLOVES")
        self.assertContains(response, 'name="q"')
        self.assertContains(response, 'value="seringue"')

    def test_scan_cartons_ready_filters_by_created_date(self):
        selected_date = timezone.make_aware(datetime(2026, 4, 29, 9, 30))
        other_date = timezone.make_aware(datetime(2026, 4, 28, 17, 0))
        self._create_carton_with_item(code="C-DATE-MATCH", created_at=selected_date)
        self._create_carton_with_item(code="C-DATE-OTHER", created_at=other_date)

        response = self.client.get(
            reverse("scan:scan_cartons_ready"),
            {"created_on": "2026-04-29"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "C-DATE-MATCH")
        self.assertNotContains(response, "C-DATE-OTHER")
        self.assertContains(response, 'name="created_on"')
        self.assertContains(response, 'value="2026-04-29"')

    def test_scan_cartons_ready_filters_by_prepared_volunteer(self):
        volunteer_user = get_user_model().objects.create_user(
            username="volunteer-filter",
            first_name="Alice",
            last_name="Martin",
            is_staff=True,
        )
        other_user = get_user_model().objects.create_user(
            username="volunteer-other",
            first_name="Bob",
            last_name="Durand",
            is_staff=True,
        )
        volunteer = VolunteerProfile.objects.create(user=volunteer_user, is_active=True)
        other_volunteer = VolunteerProfile.objects.create(user=other_user, is_active=True)
        selected_carton = self._create_carton_with_item(
            code="C-VOLUNTEER-MATCH",
            prepared_by=volunteer_user,
        )
        other_carton = self._create_carton_with_item(
            code="C-VOLUNTEER-OTHER",
            prepared_by=other_user,
        )
        CartonVolunteerActivity.objects.create(
            carton=selected_carton,
            volunteer=volunteer,
            action=CartonVolunteerActivityAction.PREPARED,
            actor=self.staff_user,
        )
        CartonVolunteerActivity.objects.create(
            carton=other_carton,
            volunteer=other_volunteer,
            action=CartonVolunteerActivityAction.PREPARED,
            actor=self.staff_user,
        )

        response = self.client.get(
            reverse("scan:scan_cartons_ready"),
            {"prepared_by": str(volunteer.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "C-VOLUNTEER-MATCH")
        self.assertNotContains(response, "C-VOLUNTEER-OTHER")
        self.assertContains(response, 'name="prepared_by"')
        self.assertContains(response, f'value="{volunteer.id}" selected')
        self.assertContains(response, "Alice MARTIN")

    def test_scan_cartons_ready_bulk_picking_redirects_to_grouped_route(self):
        carton = Carton.objects.create(code="C-BULK-PICK", status=CartonStatus.PICKING)

        response = self.client.post(
            reverse("scan:scan_cartons_ready"),
            {
                "bulk_document": "picking",
                "selected_carton_ids": [str(carton.id)],
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('scan:scan_cartons_picking')}?carton_ids={carton.id}",
        )

    def test_scan_cartons_ready_bulk_packing_lists_redirects_to_bundle_route(self):
        carton = Carton.objects.create(code="C-BULK-DOC", status=CartonStatus.PICKING)

        response = self.client.post(
            reverse("scan:scan_cartons_ready"),
            {
                "bulk_document": "packing_lists",
                "selected_carton_ids": [str(carton.id)],
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('scan:scan_cartons_view_bundle', args=['packing_lists'])}?carton_ids={carton.id}",
        )

    def test_scan_cartons_ready_bulk_apply_updates_selected_cartons_to_packed(self):
        carton = Carton.objects.create(code="C-BULK-READY", status=CartonStatus.PICKING)

        response = self.client.post(
            reverse("scan:scan_cartons_ready"),
            {
                "bulk_action": "bulk_update_cartons_packed",
                "selected_carton_ids": [str(carton.id)],
            },
        )

        self.assertRedirects(response, reverse("scan:scan_cartons_ready"))
        carton.refresh_from_db()
        self.assertEqual(carton.status, CartonStatus.PACKED)

    def test_scan_cartons_ready_formats_editable_shipment_labels_for_toolbar_and_modal(self):
        correspondent_org = Contact.objects.create(
            name="Destination Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        correspondent = Contact.objects.create(
            name="Destination Person",
            contact_type=ContactType.PERSON,
            first_name="Destination",
            last_name="Person",
            organization=correspondent_org,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Nouakchott",
            iata_code="NKC",
            country="Mauritanie",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipment = self._create_shipment(
            status=ShipmentStatus.DRAFT,
            reference="260012",
            destination=destination,
            shipper_name="Expéditeur",
        )
        self._create_carton_with_item(code="C-LABEL-260012")

        response = self.client.get(reverse("scan:scan_cartons_ready"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{shipment.id}"')
        self.assertContains(response, "260012 - NKC - Expéditeur")

    def test_scan_cartons_ready_renders_preassignment_mismatch_modal_and_checkbox_metadata(self):
        correspondent_org = Contact.objects.create(
            name="Mismatch Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        correspondent = Contact.objects.create(
            name="Mismatch Person",
            contact_type=ContactType.PERSON,
            first_name="Mismatch",
            last_name="Person",
            organization=correspondent_org,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Nouakchott",
            iata_code="NKC",
            country="Mauritanie",
            correspondent_contact=correspondent,
            is_active=True,
        )
        carton = self._create_carton_with_item(code="C-MISMATCH-UI")
        carton.preassigned_destination = destination
        carton.save(update_fields=["preassigned_destination"])

        response = self.client.get(reverse("scan:scan_cartons_ready"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="carton-preassignment-mismatch-overlay"')
        self.assertContains(response, 'id="carton-preassignment-mismatch-message"')
        self.assertContains(response, 'name="confirm_preassigned_destination_mismatch"')
        self.assertContains(
            response,
            f'data-carton-preassigned-destination-id="{destination.id}"',
        )
        self.assertContains(
            response,
            'data-carton-preassigned-destination-code="NKC"',
        )
        self.assertContains(
            response,
            f'data-carton-id="{carton.id}"',
        )

    def test_scan_carton_edit_renders_carton_fiche_sections(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        carton = Carton.objects.create(
            code="C-FICHE-001",
            status=CartonStatus.ASSIGNED,
            shipment=shipment,
        )

        response = self.client.get(reverse("scan:scan_carton_edit", args=[carton.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "scan/pack.html")
        self.assertContains(response, f"Fiche colis {carton.code}")
        self.assertContains(response, "Synthèse")
        self.assertContains(response, "Contenu")
        self.assertContains(response, "Documents")
        self.assertContains(response, "Modifier")
        self.assertContains(
            response,
            reverse("scan:scan_shipment_edit", args=[shipment.id]),
        )
        self.assertContains(
            response,
            reverse("scan:scan_shipment_carton_document", args=[shipment.id, carton.id]),
        )
        self.assertContains(
            response,
            reverse("scan:scan_carton_picking", args=[carton.id]),
        )
        self.assertContains(response, "Créer un nouveau produit")
        self.assertContains(
            response,
            'id="pack-create-product-link"',
        )
        self.assertContains(response, 'href="/scan/import/"')
        self.assertNotContains(response, 'id="pack-unknown-product-overlay"')

    def test_scan_carton_edit_exposes_delete_action_for_editable_carton(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        carton = self._create_carton_with_item(
            code="C-DELETE-UI-001",
            shipment=shipment,
            status=CartonStatus.ASSIGNED,
        )

        response = self.client.get(reverse("scan:scan_carton_edit", args=[carton.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="action" value="delete_carton"')
        self.assertContains(response, f'name="carton_id" value="{carton.id}"')
        self.assertContains(response, "Supprimer le colis")

    def test_scan_carton_edit_delete_action_deletes_editable_carton(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        carton = self._create_carton_with_item(
            code="C-DELETE-POST-001",
            shipment=shipment,
            status=CartonStatus.ASSIGNED,
        )

        response = self.client.post(
            reverse("scan:scan_carton_edit", args=[carton.id]),
            {
                "action": "delete_carton",
                "carton_id": str(carton.id),
            },
        )

        self.assertRedirects(response, reverse("scan:scan_cartons_ready"))
        self.assertFalse(Carton.objects.filter(pk=carton.id).exists())

    def test_scan_carton_edit_renders_read_only_fiche_when_shipment_is_planned(self):
        shipment = self._create_shipment(status=ShipmentStatus.PLANNED)
        carton = Carton.objects.create(
            code="C-LOCKED-001",
            status=CartonStatus.ASSIGNED,
            shipment=shipment,
        )

        response = self.client.get(reverse("scan:scan_carton_edit", args=[carton.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "scan/pack.html")
        self.assertContains(response, f"Fiche colis {carton.code}")
        self.assertContains(response, "Colis verrouillé")
        self.assertContains(response, "Expédition planifiée")
        self.assertContains(
            response,
            reverse("scan:scan_shipment_edit", args=[shipment.id]),
        )
        self.assertNotContains(response, 'id="carton-edit-panel"')
        self.assertNotContains(response, 'id="pack-lines"')
        self.assertNotContains(response, 'name="action" value="delete_carton"')

    def test_scan_shipments_tracking_renders_rows_context(self):
        with mock.patch(
            "wms.views_scan_shipments.build_shipments_tracking_list_context",
            return_value={
                "shipments": [
                    {
                        "id": 1,
                        "reference": "S-TRACK-001",
                        "is_disputed": True,
                        "can_close": False,
                        "status_value": ShipmentStatus.PLANNED,
                    },
                    {
                        "id": 2,
                        "reference": "S-TRACK-002",
                        "is_disputed": False,
                        "can_close": True,
                        "status_value": ShipmentStatus.DELIVERED,
                    },
                    {
                        "id": 3,
                        "reference": "S-TRACK-003",
                        "is_disputed": False,
                        "can_close": False,
                        "status_value": ShipmentStatus.SHIPPED,
                    },
                    {
                        "id": 4,
                        "reference": "S-TRACK-004",
                        "is_disputed": False,
                        "can_close": False,
                        "status_value": ShipmentStatus.RECEIVED_CORRESPONDENT,
                    },
                ],
                "summary_cards": [
                    {"id": "open-disputes", "value": 1},
                    {"id": "closable-cases", "value": 1},
                    {"id": "waiting-stopover", "value": 1},
                    {"id": "waiting-delivery", "value": 1},
                ],
                "planned_week_value": "",
                "planned_week_invalid": False,
                "closed_filter": "exclude",
                "dispute_filter": "all",
                "destination_filter_value": "",
                "destination_filter_label": "",
                "query": "",
                "total_count": 4,
                "page_size": 100,
                "shipments_page": SimpleNamespace(has_other_pages=lambda: False),
                "page_prev_url": None,
                "page_next_url": None,
                "reset_url": reverse("scan:scan_shipments_tracking"),
            },
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
            [
                {
                    "id": 1,
                    "reference": "S-TRACK-001",
                    "is_disputed": True,
                    "can_close": False,
                    "status_value": ShipmentStatus.PLANNED,
                },
                {
                    "id": 2,
                    "reference": "S-TRACK-002",
                    "is_disputed": False,
                    "can_close": True,
                    "status_value": ShipmentStatus.DELIVERED,
                },
                {
                    "id": 3,
                    "reference": "S-TRACK-003",
                    "is_disputed": False,
                    "can_close": False,
                    "status_value": ShipmentStatus.SHIPPED,
                },
                {
                    "id": 4,
                    "reference": "S-TRACK-004",
                    "is_disputed": False,
                    "can_close": False,
                    "status_value": ShipmentStatus.RECEIVED_CORRESPONDENT,
                },
            ],
        )
        self.assertEqual(
            [card["id"] for card in response.context_data["summary_cards"]],
            [
                "open-disputes",
                "closable-cases",
                "waiting-stopover",
                "waiting-delivery",
            ],
        )
        self.assertEqual(
            [card["value"] for card in response.context_data["summary_cards"]],
            [1, 1, 1, 1],
        )

    def test_scan_shipments_tracking_paginates_filtered_results(self):
        for index in range(105):
            shipment = self._create_shipment(
                status=ShipmentStatus.PLANNED,
                reference=f"EXP-{index:03d}",
            )
            self._mark_shipment_planned(shipment)

        target = self._create_shipment(
            status=ShipmentStatus.PLANNED,
            reference="EXP-COMPRESSE",
        )
        self._mark_shipment_planned(target)

        response = self.client.get(
            reverse("scan:scan_shipments_tracking"),
            {"q": "COMPRESSE"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EXP-COMPRESSE")
        self.assertEqual(response.context["shipments_page"].number, 1)
        self.assertEqual(len(response.context["shipments"]), 1)

    def test_scan_shipments_tracking_page_urls_preserve_filters(self):
        planned_at = timezone.make_aware(datetime(2026, 4, 13, 10, 0))
        for index in range(105):
            shipment = self._create_shipment(
                status=ShipmentStatus.PLANNED,
                reference=f"EXP-FILTER-{index:03d}",
            )
            shipment.is_disputed = True
            shipment.save(update_fields=["is_disputed"])
            self._mark_shipment_planned(shipment, created_at=planned_at)

        response = self.client.get(
            reverse("scan:scan_shipments_tracking"),
            {
                "planned_week": "2026-W16",
                "closed": "all",
                "dispute": "open",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("planned_week=2026-W16", response.context["page_next_url"])
        self.assertIn("closed=all", response.context["page_next_url"])
        self.assertIn("dispute=open", response.context["page_next_url"])

    def test_scan_shipments_tracking_filters_by_destination_query_param(self):
        correspondent_a = Contact.objects.create(
            name="Correspondent ABJ",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        correspondent_b = Contact.objects.create(
            name="Correspondent BZV",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        destination_a = Destination.objects.create(
            city="ABJ",
            iata_code="ABJ",
            country="Cote d'Ivoire",
            correspondent_contact=correspondent_a,
            is_active=True,
        )
        destination_b = Destination.objects.create(
            city="BZV",
            iata_code="BZV",
            country="Congo",
            correspondent_contact=correspondent_b,
            is_active=True,
        )
        shipment_a = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            reference="EXP-TRACK-ABJ",
            shipper_name="Sender A",
            recipient_name="Recipient A",
            destination=destination_a,
            destination_address="1 Rue A",
            destination_country=destination_a.country,
            created_by=self.staff_user,
        )
        shipment_b = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            reference="EXP-TRACK-BZV",
            shipper_name="Sender B",
            recipient_name="Recipient B",
            destination=destination_b,
            destination_address="1 Rue B",
            destination_country=destination_b.country,
            created_by=self.staff_user,
        )

        with mock.patch(
            "wms.views_scan_shipments.render",
            side_effect=self._render_stub,
        ):
            response = self.client.get(
                reverse("scan:scan_shipments_tracking"),
                {"destination": destination_b.id},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["reference"] for row in response.context_data["shipments"]],
            [shipment_b.reference],
        )
        self.assertEqual(
            response.context_data["destination_filter_value"],
            str(destination_b.id),
        )
        self.assertEqual(
            response.context_data["destination_filter_label"],
            str(destination_b),
        )
        self.assertNotIn(
            shipment_a.reference,
            [row["reference"] for row in response.context_data["shipments"]],
        )

    def test_build_shipments_tracking_rows_marks_dispute_with_primary_next_action(self):
        shipment = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            is_disputed=True,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.staff_user,
        )

        row = build_shipments_tracking_rows([shipment])[0]

        self.assertEqual(row["next_action_label"], "Traiter le litige")
        self.assertEqual(row["row_tone"], "danger")
        self.assertEqual(row["status_display"]["label"], "Litige - Planifié")

    def test_scan_pack_hides_top_reference_scan_button(self):
        response = self.client.get(reverse("scan:scan_pack"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-scan-target="id_shipment_reference"')

    def test_scan_pack_uses_guided_creation_sections_and_hides_location_admin_action(self):
        response = self.client.get(reverse("scan:scan_pack"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-pack-add-line-btn")
        self.assertContains(response, 'id="pack-section-content"')
        self.assertContains(response, 'id="pack-section-distribution"')
        self.assertContains(response, 'id="pack-section-output"')
        self.assertContains(response, 'id="pack-section-assignment"')
        self.assertContains(response, 'id="pack-section-review"')
        self.assertContains(response, 'id="id_forced_carton_count"')
        self.assertContains(response, 'name="carton_distribution_mode"')
        self.assertContains(response, 'value="auto"')
        self.assertContains(response, 'value="manual"')
        self.assertNotContains(response, 'id="id_free_batch_carton_count"')
        self.assertNotContains(response, 'name="confirm_free_carton_batch"')
        self.assertNotContains(response, 'value="prepare_available_batch"')
        self.assertNotContains(response, 'data-free-carton-batch-submit="1"')
        self.assertNotContains(response, 'id="free-carton-batch-confirmation-overlay"')
        self.assertContains(response, "Nombre de colis")
        self.assertContains(response, 'value="prepare_without_conditioning"')
        self.assertContains(response, 'value="prepare_available"')
        self.assertContains(response, "btn btn-outline-secondary")
        self.assertContains(response, "btn btn-success")
        self.assertContains(response, 'for="id_carton_length_cm">Longueur</label>')
        self.assertContains(response, 'for="id_carton_width_cm">Largeur</label>')
        self.assertContains(response, 'for="id_carton_height_cm">Hauteur</label>')
        self.assertContains(response, 'for="id_carton_max_weight_g">Poids</label>')
        self.assertContains(response, "ui-comp-actions")
        self.assertNotContains(response, "Ajouter emplacement")

    def test_scan_pack_rejects_deprecated_free_batch_action_from_view(self):
        lot = self._get_test_product_lot()
        CartonFormat.objects.create(
            name="Batch test",
            length_cm=40,
            width_cm=30,
            height_cm=30,
            max_weight_g=8000,
            is_default=True,
        )

        response = self.client.post(
            reverse("scan:scan_pack"),
            {
                "action": "prepare_available_batch",
                "free_batch_carton_count": "2",
                "line_count": "1",
                "line_1_product_code": lot.product.sku,
                "line_1_quantity": "3",
                "confirm_defaults": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Carton.objects.count(), 0)
        self.assertContains(
            response,
            "Le mode batch colis libres a été remplacé par le nombre de colis manuel.",
        )
        self.assertNotContains(response, 'id="id_free_batch_carton_count"')

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
        self.assertContains(response, "Choisir une commande")
        self.assertContains(response, reverse("scan:scan_preparateur_order_select"))
        self.assertContains(response, "Voir les colis")
        self.assertNotContains(response, "Voir dernier colis")
        self.assertContains(response, reverse("scan:scan_cartons_ready"))
        self.assertContains(response, f"Bonjour {preparateur.username}")
        self.assertNotContains(response, "Runs magasin")
        self.assertNotContains(response, 'id="scan-faq-link"')
        self.assertNotContains(response, 'id="scan-masthead-account-toggle"')
        self.assertNotContains(response, "Tableau De Bord")
        self.assertNotContains(response, "Vue Stock")
        self.assertNotContains(response, "Admin Django")

    def test_preparateur_can_view_all_non_shipped_cartons_without_prepared_by_filter(self):
        preparateur = self._create_preparateur_user()
        other_user = get_user_model().objects.create_user(
            username="scan-preparateur-other",
            password="pass1234",
            is_staff=True,
        )
        visible_carton = self._create_carton_with_item(
            code="C-PREP-VISIBLE-001",
            status=CartonStatus.PACKED,
        )
        visible_carton.prepared_by = other_user
        visible_carton.save(update_fields=["prepared_by"])
        shipped_carton = self._create_carton_with_item(
            code="C-PREP-SHIPPED-001",
            status=CartonStatus.SHIPPED,
        )
        shipped_carton.prepared_by = other_user
        shipped_carton.save(update_fields=["prepared_by"])
        self.client.force_login(preparateur)

        response = self.client.get(reverse("scan:scan_cartons_ready"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "C-PREP-VISIBLE-001")
        self.assertNotContains(response, "C-PREP-SHIPPED-001")
        self.assertContains(response, reverse("scan:scan_carton_edit", args=[visible_carton.id]))

    def test_preparateur_can_print_any_non_shipped_carton(self):
        preparateur = self._create_preparateur_user()
        other_user = get_user_model().objects.create_user(
            username="scan-preparateur-print-other",
            password="pass1234",
            is_staff=True,
        )
        carton = self._create_carton_with_item(
            code="C-PREP-PRINT-001",
            status=CartonStatus.PACKED,
        )
        carton.prepared_by = other_user
        carton.save(update_fields=["prepared_by"])
        self.client.force_login(preparateur)

        with mock.patch("wms.views_print_docs._try_generate_pack_pdf_response") as pdf_response:
            pdf_response.return_value = HttpResponse("packing-list")
            response = self.client.get(reverse("scan:scan_carton_document", args=[carton.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"packing-list")

    def test_preparateur_cannot_print_shipped_carton(self):
        preparateur = self._create_preparateur_user()
        carton = self._create_carton_with_item(
            code="C-PREP-PRINT-SHIPPED-001",
            status=CartonStatus.SHIPPED,
        )
        self.client.force_login(preparateur)

        response = self.client.get(reverse("scan:scan_carton_document", args=[carton.id]))

        self.assertEqual(response.status_code, 403)

    def test_scan_pack_preparateur_renders_unknown_product_modal_with_location_selectors(self):
        preparateur = self._create_preparateur_user()
        self.client.force_login(preparateur)
        self._get_test_product_lot()

        response = self.client.get(reverse("scan:scan_pack"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="pack-unknown-product-modal"')
        self.assertContains(response, 'name="unknown_product_name"')
        self.assertContains(response, 'name="unknown_product_brand"')
        self.assertContains(response, 'name="unknown_product_initial_quantity"')
        self.assertContains(response, 'name="unknown_product_pack_family"')
        self.assertContains(response, 'name="unknown_product_length_cm"')
        self.assertContains(response, 'name="unknown_product_width_cm"')
        self.assertContains(response, 'name="unknown_product_height_cm"')
        self.assertContains(response, 'name="unknown_product_weight_g"')
        self.assertContains(response, 'name="unknown_product_location"')
        self.assertContains(response, 'id="id_unknown_product_location_warehouse"')
        self.assertContains(response, 'id="id_unknown_product_location_zone"')
        self.assertContains(response, 'id="id_unknown_product_location_aisle"')
        self.assertContains(response, 'id="id_unknown_product_location_shelf"')
        self.assertContains(response, 'id="pack-location-data"')
        self.assertContains(
            response,
            "Pour les CN, merci de noter le volume du produit",
        )
        self.assertNotContains(response, 'name="unknown_product_sku"')
        self.assertNotContains(response, 'id="id_unknown_product_sku"')
        self.assertNotContains(response, 'name="unknown_product_location_free_text"')

    def test_scan_pack_preparateur_unknown_product_requires_dimensions_and_weight(self):
        preparateur = self._create_preparateur_user()
        self.client.force_login(preparateur)
        warehouse = Warehouse.objects.create(name="Prep warehouse required", code="PREQR")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        ProductCategory.objects.create(name="MM")

        response = self.client.post(
            reverse("scan:scan_pack"),
            {
                "action": "create_unknown_product",
                "carton_format_id": "custom",
                "carton_length_cm": "40",
                "carton_width_cm": "30",
                "carton_height_cm": "30",
                "carton_max_weight_g": "8000",
                "line_count": "1",
                "line_1_product_code": "9988776600",
                "line_1_quantity": "2",
                "unknown_product_line_index": "1",
                "unknown_product_source_code": "9988776600",
                "unknown_product_name": "Produit Sans Dimensions",
                "unknown_product_barcode": "9988776600",
                "unknown_product_pack_family": "MM",
                "unknown_product_initial_quantity": "7",
                "unknown_product_location": str(location.id),
                "unknown_product_location_warehouse": warehouse.name,
                "unknown_product_location_zone": location.zone,
                "unknown_product_location_aisle": location.aisle,
                "unknown_product_location_shelf": location.shelf,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["unknown_product_modal_open"])
        self.assertFalse(Product.objects.filter(name="Produit Sans Dimensions").exists())
        self.assertContains(response, 'name="unknown_product_length_cm"')
        self.assertContains(response, 'name="unknown_product_width_cm"')
        self.assertContains(response, 'name="unknown_product_height_cm"')
        self.assertContains(response, 'name="unknown_product_weight_g"')

    def test_scan_pack_preparateur_create_unknown_product_rehydrates_selected_line(self):
        preparateur = self._create_preparateur_user()
        self.client.force_login(preparateur)
        warehouse = Warehouse.objects.create(name="Prep warehouse", code="PREP")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        ProductCategory.objects.create(name="MM")

        with mock.patch("wms.pack_handlers.notify_preparateur_product_review_needed"):
            response = self.client.post(
                reverse("scan:scan_pack"),
                {
                    "action": "create_unknown_product",
                    "carton_format_id": "custom",
                    "carton_length_cm": "40",
                    "carton_width_cm": "30",
                    "carton_height_cm": "30",
                    "carton_max_weight_g": "8000",
                    "line_count": "1",
                    "line_1_product_code": "9988776655",
                    "line_1_quantity": "2",
                    "unknown_product_line_index": "1",
                    "unknown_product_source_code": "9988776655",
                    "unknown_product_name": "Produit Nouveau Préparateur",
                    "unknown_product_barcode": "9988776655",
                    "unknown_product_pack_family": "MM",
                    "unknown_product_initial_quantity": "7",
                    "unknown_product_brand": "Marque Test",
                    "unknown_product_length_cm": "10.5",
                    "unknown_product_width_cm": "4",
                    "unknown_product_height_cm": "2",
                    "unknown_product_weight_g": "250",
                    "unknown_product_location": str(location.id),
                    "unknown_product_location_warehouse": warehouse.name,
                    "unknown_product_location_zone": location.zone,
                    "unknown_product_location_aisle": location.aisle,
                    "unknown_product_location_shelf": location.shelf,
                },
            )

        self.assertEqual(response.status_code, 200)
        product = Product.objects.get(name="Produit Nouveau Préparateur")
        lot = ProductLot.objects.get(product=product)
        self.assertTrue(product.is_incomplete)
        self.assertEqual(product.default_location, location)
        self.assertNotEqual(product.sku, "9988776655")
        self.assertTrue(product.sku)
        self.assertEqual(product.brand, "MARQUE TEST")
        self.assertEqual(product.length_cm, Decimal("10.50"))
        self.assertEqual(product.width_cm, Decimal("4.00"))
        self.assertEqual(product.height_cm, Decimal("2.00"))
        self.assertEqual(product.weight_g, 250)
        self.assertEqual(product.volume_cm3, 84)
        self.assertEqual(lot.quantity_on_hand, 7)
        self.assertEqual(response.context["line_values"][0]["product_code"], product.sku)
        self.assertContains(response, product.sku)

    def test_scan_pack_preparateur_displays_selected_order_summary_from_session(self):
        preparateur = self._create_preparateur_user()
        self.client.force_login(preparateur)
        order = Order.objects.create(
            shipper_name="ASF",
            recipient_name="Association Selectionnée",
            destination_address="1 Rue Test",
            destination_country="France",
            review_status=OrderReviewStatus.APPROVED,
        )
        session = self.client.session
        session["preparateur_selected_order_id"] = order.id
        session.save()

        response = self.client.get(reverse("scan:scan_pack"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Commande sélectionnée")
        self.assertContains(response, f"CMD-{order.id}")
        self.assertContains(response, "Association Selectionnée")

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
                        "packing_list_url": "/scan/cartons/10/document/?delivery=html",
                    },
                    {
                        "code": "CN-20260316-04",
                        "zone_label": "Colis Prets CN",
                        "family": "CN",
                        "items": [],
                        "packing_list_url": "/scan/cartons/11/document/?delivery=html",
                    },
                ],
                "print_urls": [
                    "/scan/cartons/10/document/?delivery=html",
                    "/scan/cartons/11/document/?delivery=html",
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
        self.assertContains(response, 'id="pack-success-backdrop"')
        self.assertContains(response, 'class="btn-close"')
        self.assertContains(response, 'data-pack-success-close="1"')
        self.assertContains(response, 'data-pack-success-print="1"')
        self.assertContains(response, 'data-pack-print-all="1"')
        self.assertContains(response, "Imprimer tout")
        self.assertContains(response, "/scan/cartons/10/document/?delivery=html")
        self.assertContains(response, "/scan/cartons/11/document/?delivery=html")

    def test_scan_pack_preparateur_success_modal_uses_single_print_label_for_one_carton(self):
        preparateur = self._create_preparateur_user()
        self.client.force_login(preparateur)
        session = self.client.session
        session["pack_results"] = [10]
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
                        "packing_list_url": "/scan/cartons/10/document/?delivery=html",
                    }
                ],
                "print_urls": ["/scan/cartons/10/document/?delivery=html"],
                "aggregate": [],
                "show_success_modal": True,
            },
        ):
            response = self.client.get(reverse("scan:scan_pack"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-pack-success-print="1"')
        self.assertContains(response, 'data-pack-print-all="0"')
        self.assertContains(response, "Imprimer")
        self.assertNotContains(response, "Imprimer tout")

    def test_scan_shipment_create_hides_secondary_draft_button_near_submit(self):
        response = self.client.get(reverse("scan:scan_shipment_create"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="action" value="save_draft"')
        self.assertContains(response, 'name="action" value="create_pack"', count=1)

    def test_scan_shipment_create_exposes_preparation_mode_and_redirect_choice(self):
        response = self.client.get(reverse("scan:scan_shipment_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="creation_mode"')
        self.assertContains(response, 'value="with_cartons"')
        self.assertContains(response, 'value="without_cartons"')
        self.assertContains(response, 'id="id_planned_carton_count"')
        self.assertContains(response, 'name="post_create_action"')
        self.assertContains(response, 'value="show_dossier"')
        self.assertContains(response, 'value="stay"')

    def test_scan_shipment_batch_create_renders_line_builder(self):
        response = self.client.get(reverse("scan:scan_shipment_batch_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shipment-batch-form"')
        self.assertContains(response, 'name="row_1_destination"')
        self.assertContains(response, 'name="row_1_planned_carton_count"')
        self.assertContains(response, "Ajouter une expédition")
        self.assertContains(response, "Valider le batch")

    def test_scan_shipment_batch_create_posts_valid_rows_to_summary(self):
        destination_a, shipper_a, recipient_a, correspondent_a = (
            self._create_shipment_party_triplet("BVA")
        )
        destination_b, shipper_b, recipient_b, correspondent_b = (
            self._create_shipment_party_triplet("BVB")
        )

        response = self.client.post(
            reverse("scan:scan_shipment_batch_create"),
            {
                "row_count": "2",
                "row_1_destination": str(destination_a.id),
                "row_1_shipper_contact": str(shipper_a.id),
                "row_1_recipient_contact": str(recipient_a.id),
                "row_1_correspondent_contact": str(correspondent_a.id),
                "row_1_planned_carton_count": "10",
                "row_2_destination": str(destination_b.id),
                "row_2_shipper_contact": str(shipper_b.id),
                "row_2_recipient_contact": str(recipient_b.id),
                "row_2_correspondent_contact": str(correspondent_b.id),
                "row_2_planned_carton_count": "5",
            },
        )

        self.assertRedirects(response, reverse("scan:scan_shipment_batch_summary"))
        shipments = list(Shipment.objects.order_by("id"))
        self.assertEqual([shipment.planned_carton_count for shipment in shipments], [10, 5])
        self.assertEqual(
            self.client.session["shipment_batch_created_ids"],
            [shipment.id for shipment in shipments],
        )

    def test_scan_shipment_batch_create_rerenders_invalid_rows_with_errors(self):
        destination, shipper, recipient, correspondent = self._create_shipment_party_triplet("BVI")

        response = self.client.post(
            reverse("scan:scan_shipment_batch_create"),
            {
                "row_count": "1",
                "row_1_destination": str(destination.id),
                "row_1_shipper_contact": str(shipper.id),
                "row_1_recipient_contact": str(recipient.id),
                "row_1_correspondent_contact": str(correspondent.id),
                "row_1_planned_carton_count": "0",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Batch non enregistré")
        self.assertContains(response, "Nombre de colis prévus requis.")
        self.assertEqual(Shipment.objects.count(), 0)

    def test_scan_shipment_batch_summary_renders_created_shipments(self):
        shipment_a = self._create_shipment(reference="EXP-BATCH-A")
        shipment_b = self._create_shipment(reference="EXP-BATCH-B")
        session = self.client.session
        session["shipment_batch_created_ids"] = [shipment_a.id, shipment_b.id]
        session.save()

        response = self.client.get(reverse("scan:scan_shipment_batch_summary"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EXP-BATCH-A")
        self.assertContains(response, "EXP-BATCH-B")
        self.assertContains(response, "Imprimer les dossiers")
        self.assertContains(response, "Imprimer les étiquettes")

    def test_scan_shipment_create_renders_single_correspondent_display_markers(self):
        response = self.client.get(reverse("scan:scan_shipment_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shipment-correspondent-select-wrap"')
        self.assertContains(response, 'id="shipment-correspondent-single"')

    def test_scan_shipment_create_uses_shared_hidden_alerts_for_empty_party_states(self):
        response = self.client.get(reverse("scan:scan_shipment_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-message error ui-comp-alert scan-hidden", count=3)

    def test_scan_shipment_edit_renders_wave3_edit_panels(self):
        association = Contact.objects.create(
            name="Association Edit Panels",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        warehouse = Warehouse.objects.create(name="Wave 3 Alloc", code="W3A")
        receipt = Receipt.objects.create(
            receipt_type=ReceiptType.ASSOCIATION,
            source_contact=association,
            carton_count=3,
            warehouse=warehouse,
        )
        shipment = Shipment.objects.create(
            reference="EXP-WAVE3-EDIT",
            shipper_name=association.name,
            shipper_contact_ref=association,
            recipient_name="Association Dest",
            destination_address="1 Rue Test",
            status=ShipmentStatus.DRAFT,
            created_by=self.staff_user,
        )
        Carton.objects.create(code="C-WAVE3-001", shipment=shipment)
        ReceiptShipmentAllocation.objects.create(
            receipt=receipt,
            shipment=shipment,
            allocated_received_units=7,
            note="Wave 3 allocation",
            created_by=self.staff_user,
        )

        response = self.client.get(reverse("scan:scan_shipment_edit", args=[shipment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'id="shipment-dossier-grouped-print-actions"',
        )
        self.assertContains(
            response,
            'id="shipment-dossier-paper-print-actions"',
        )
        self.assertContains(
            response,
            'id="shipment-dossier-pdf-export-actions"',
        )
        self.assertContains(response, "shipment-dossier-document-actions")
        self.assertContains(response, "ui-comp-file-input")
        self.assertContains(response, 'id="shipment-dossier-carton-print-actions"')
        self.assertContains(response, 'id="shipment-receipt-allocations-table"')
        self.assertContains(response, receipt.reference)
        self.assertContains(response, "Wave 3 allocation")

    def test_scan_shipment_edit_exposes_confirm_ready_action_for_editable_shipment(self):
        shipment = self._create_shipment(status=ShipmentStatus.PICKING)
        self._create_carton_with_item(
            code="C-CONFIRM-READY-1",
            shipment=shipment,
            status=CartonStatus.ASSIGNED,
        )

        response = self.client.get(reverse("scan:scan_shipment_edit", args=[shipment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="confirm_shipment_ready"')
        self.assertContains(response, "Confirmer prêt")

    def test_scan_shipment_edit_post_confirms_ready_only_on_explicit_action(self):
        shipment = self._create_shipment(status=ShipmentStatus.PICKING)
        carton = self._create_carton_with_item(
            code="C-CONFIRM-READY-2",
            shipment=shipment,
            status=CartonStatus.ASSIGNED,
        )

        response = self.client.post(
            reverse("scan:scan_shipment_edit", args=[shipment.id]),
            {"action": "confirm_shipment_ready"},
        )

        self.assertEqual(response.status_code, 302)
        shipment.refresh_from_db()
        carton.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.PACKED)
        self.assertIsNotNone(shipment.ready_at)
        self.assertEqual(carton.status, CartonStatus.LABELED)

    def test_scan_prepare_kits_groups_top_controls_in_single_panel(self):
        response = self.client.get(reverse("scan:scan_prepare_kits"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-prepare-kits-top-panel-full", count=1)
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
        self.assertEqual(shipment.dossier_last_activity_label, "Dossier clôturé")
        self.assertIsNotNone(shipment.dossier_last_activity_at)
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
                                None,
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
        self.assertTrue(response.context_data["confirm_defaults"])
        self.assertIsNone(response.context_data["forced_carton_count"])
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
            "forced_carton_count": 3,
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
        self.assertEqual(response.context_data["forced_carton_count"], 3)

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
        self.assertEqual(response.context_data["forced_carton_count"], "")
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
        self.assertEqual(response.context_data["forced_carton_count"], "")

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

    def test_scan_shipment_create_exposes_forced_carton_count_field(self):
        response = self.client.get(reverse("scan:scan_shipment_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_forced_carton_count"')
        self.assertContains(response, "Nombre de colis forcé")
        self.assertContains(
            response,
            "répartit uniquement les lignes produit créées ici sur le nombre de colis demandé",
        )

    def test_scan_shipment_create_exposes_carton_source_labels(self):
        warehouse = Warehouse.objects.create(name="Shipment labels warehouse")
        receipt = Receipt.objects.create(
            receipt_type=ReceiptType.ASSOCIATION,
            warehouse=warehouse,
        )
        Carton.objects.create(
            code="AS-SHIPPER-001",
            status=CartonStatus.PACKED,
            source_kind=CartonSourceKind.SHIPPER_RECEIVED,
            source_receipt=receipt,
        )
        Carton.objects.create(
            code="AS-WAREHOUSE-001",
            status=CartonStatus.PACKED,
            source_kind=CartonSourceKind.WAREHOUSE_PREPARED,
        )

        response = self.client.get(reverse("scan:scan_shipment_create"))

        self.assertEqual(response.status_code, 200)
        source_labels = [row["source_label"] for row in response.context["cartons_json"]]
        self.assertIn("Réception expéditeur", source_labels)
        self.assertIn("Préparation ASF", source_labels)

    def test_scan_shipment_edit_renders_read_only_dossier_when_shipment_is_locked(self):
        shipment = self._create_shipment(status=ShipmentStatus.SHIPPED)

        response = self.client.get(
            reverse("scan:scan_shipment_edit", kwargs={"shipment_id": shipment.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "scan/shipment_dossier.html")
        self.assertContains(response, shipment.reference)
        self.assertContains(response, "Dossier expédition")
        self.assertContains(response, "Expédition verrouillée")
        self.assertNotContains(response, 'id="shipment-form"')

    def test_scan_shipment_edit_renders_dossier_sections_and_primary_actions(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        shipment.dossier_last_activity_at = timezone.now()
        shipment.dossier_last_activity_label = "Document ajouté"
        shipment.save(
            update_fields=[
                "dossier_last_activity_at",
                "dossier_last_activity_label",
            ]
        )
        Carton.objects.create(code="C-DOS-1", shipment=shipment)

        response = self.client.get(
            reverse("scan:scan_shipment_edit", kwargs={"shipment_id": shipment.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "scan/shipment_dossier.html")
        self.assertContains(response, f"Dossier expédition {shipment.reference}")
        self.assertContains(response, "Administratif")
        self.assertContains(response, "Documents")
        self.assertContains(response, "Suivi")
        self.assertContains(response, "Modifier")
        self.assertContains(response, "Impression groupée")
        self.assertContains(response, "Documents papier")
        self.assertContains(response, "Par colis")
        self.assertContains(response, "Exports PDF")
        self.assertContains(response, "Imprimer tous les documents")
        self.assertContains(response, "Imprimer dossier papier")
        self.assertContains(
            response, "Imprimer toutes les listes colisage carton (rouleau continu)"
        )
        self.assertContains(response, "Imprimer toutes les listes par carton")
        self.assertContains(response, "Imprimer étiquettes cartons")
        self.assertContains(response, "Étiquette contact")
        self.assertContains(response, "Voir les colis")
        self.assertContains(response, "shipment-dossier-action--cartons")
        self.assertContains(response, "shipment-dossier-action--tracking")
        self.assertContains(response, "shipment-dossier-action--back")
        self.assertContains(response, "shipment-dossier-action--edit")
        self.assertContains(response, "shipment-dossier-action--close")
        self.assertContains(response, "Dernière MAJ :")
        self.assertContains(response, "Document ajouté")
        self.assertContains(response, 'id="shipment-dossier-primary-actions"')
        self.assertContains(response, 'id="shipment-dossier-secondary-actions"')
        self.assertContains(
            response,
            f"{reverse('scan:scan_cartons_ready')}?shipment_reference={shipment.reference}",
        )
        self.assertNotContains(response, "Documents générés")
        self.assertNotContains(response, "Feuille contact")
        content = response.content.decode()
        header_start = content.index('id="shipment-dossier-header"')
        header_end = content.index("</section>", header_start)
        header_html = content[header_start:header_end]
        self.assertLess(header_html.index("Voir les colis"), header_html.index("Modifier"))
        self.assertLess(header_html.index("Modifier"), header_html.index("Ouvrir suivi"))
        self.assertLess(header_html.index("Ouvrir suivi"), header_html.index("Retour aux dossiers"))
        self.assertLess(
            header_html.index('id="shipment-dossier-primary-actions"'),
            header_html.index('id="shipment-dossier-secondary-actions"'),
        )

    def test_scan_shipment_edit_displays_inbound_workflow_summary(self):
        warehouse = Warehouse.objects.create(name="Inbound workflow warehouse")
        association = Contact.objects.create(
            name="Association workflow",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        receipt = Receipt.objects.create(
            receipt_type=ReceiptType.ASSOCIATION,
            warehouse=warehouse,
            source_contact=association,
        )
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        order = Order.objects.create(
            association_contact=association,
            shipper_name="Aviation Sans Frontieres",
            recipient_name="Association Dest",
            destination_address="1 Rue Test",
            destination_country="France",
            review_status=OrderReviewStatus.APPROVED,
        )
        OrderInboundDelivery.objects.create(
            order=order,
            arrival_mode=OrderInboundArrivalMode.DROPOFF_WAREHOUSE,
            declared_carton_count=3,
            receipt=receipt,
        )
        OrderShipmentLink.objects.create(order=order, shipment=shipment, created_by=self.staff_user)
        Carton.objects.create(
            code="AS-FLOW-UNASSIGNED",
            status=CartonStatus.PACKED,
            source_kind=CartonSourceKind.SHIPPER_RECEIVED,
            source_receipt=receipt,
        )
        Carton.objects.create(
            code="AS-FLOW-ASSIGNED",
            status=CartonStatus.ASSIGNED,
            source_kind=CartonSourceKind.SHIPPER_RECEIVED,
            source_receipt=receipt,
            shipment=shipment,
        )

        response = self.client.get(
            reverse("scan:scan_shipment_edit", kwargs={"shipment_id": shipment.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Commande liée")
        self.assertContains(response, f"CMD-{order.id}")
        self.assertContains(response, "Colis expéditeur disponibles")
        self.assertContains(response, "1 / 3")

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
        self.assertEqual(response.content.decode(), "scan/shipment_dossier.html")
        self.assertEqual(response.context_data["context_key"], "edit-get")
        self.assertEqual(response.context_data["helper_install"], helper_install)
        self.assertTrue(response.context_data["is_edit"])
        self.assertFalse(response.context_data["is_locked"])
        self.assertTrue(response.context_data["can_edit"])
        self.assertEqual(response.context_data["shipment"].id, shipment.id)
        self.assertIn("tracking_url", response.context_data)
        self.assertIn("dossier_print_actions", response.context_data)
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
        self.assertEqual(response.content.decode(), "scan/shipment_dossier.html")
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

    def test_scan_shipment_track_get_renders_access_gateway_for_unauthenticated_user(self):
        self.client.logout()
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)

        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
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
        self.assertFalse(response.context_data["can_update_tracking"])
        self.assertTrue(response.context_data["access_required"])
        self.assertIn("gateway_form", response.context_data)
        self.assertIn("recovery_form", response.context_data)
        self.assertIn("pending_form", response.context_data)

    def test_scan_shipment_track_post_unauthenticated_does_not_create_event(self):
        self.client.logout()
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)

        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            response = self.client.post(
                reverse(
                    "scan:scan_shipment_track",
                    kwargs={"tracking_token": shipment.tracking_token},
                ),
                {
                    "status": ShipmentTrackingStatus.PLANNING_OK,
                    "actor_name": "Anon",
                    "actor_structure": "Guest",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ShipmentTrackingEvent.objects.count(), 0)

    def test_scan_shipment_track_gateway_post_redirects_to_login_with_next(self):
        self.client.logout()
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        contact = Contact.objects.create(
            name="Structure Gateway",
            email="gateway@example.com",
            is_active=True,
        )

        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            response = self.client.post(
                reverse(
                    "scan:scan_shipment_track",
                    kwargs={"tracking_token": shipment.tracking_token},
                ),
                {
                    "action": "gateway",
                    "role": ShipmentTrackingAccessRole.SHIPPER,
                    "identifier": contact.asf_id,
                },
            )

        self.assertEqual(response.status_code, 302)
        location = response["Location"]
        self.assertTrue(location.startswith(reverse("scan:scan_shipment_tracking_access_login")))
        query = parse_qs(urlsplit(location).query)
        self.assertEqual(query["role"], [ShipmentTrackingAccessRole.SHIPPER])
        self.assertEqual(query["identifier"], [contact.asf_id])
        self.assertIn(
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token]), query["next"][0]
        )
        self.assertIn(f"identifier={contact.asf_id}", query["next"][0])

    def test_scan_shipment_track_get_allows_matching_restricted_grant_user(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        contact = Contact.objects.create(
            name="Structure Shipper",
            email="shipper-grant@example.com",
            is_active=True,
        )
        shipment.shipper_contact_ref = contact
        shipment.shipper_name = contact.name
        shipment.save(update_fields=["shipper_contact_ref", "shipper_name"])
        user = get_user_model().objects.create_user(
            username="shipper-grant@example.com",
            email="shipper-grant@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        grant = ShipmentTrackingAccessGrant.objects.create(
            user=user,
            role=ShipmentTrackingAccessRole.SHIPPER,
            contact=contact,
            identity_status=ShipmentTrackingIdentityStatus.PENDING,
        )
        self.client.force_login(user)
        session = self.client.session
        session[ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY] = grant.id
        session.save()

        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.render",
                side_effect=self._render_stub,
            ):
                response = self.client.get(
                    reverse(
                        "scan:scan_shipment_track",
                        kwargs={"tracking_token": shipment.tracking_token},
                    ),
                    {
                        "role": ShipmentTrackingAccessRole.SHIPPER,
                        "identifier": contact.asf_id,
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context_data["can_update_tracking"])
        self.assertFalse(response.context_data["access_required"])

    def test_scan_shipment_track_post_blocks_disallowed_role_transition_for_restricted_user(self):
        shipment = self._create_shipment(status=ShipmentStatus.SHIPPED)
        contact = Contact.objects.create(
            name="Structure Shipper Downstream",
            email="shipper-downstream@example.com",
            is_active=True,
        )
        shipment.shipper_contact_ref = contact
        shipment.shipper_name = contact.name
        shipment.save(update_fields=["shipper_contact_ref", "shipper_name"])
        user = get_user_model().objects.create_user(
            username="shipper-downstream@example.com",
            email="shipper-downstream@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        grant = ShipmentTrackingAccessGrant.objects.create(
            user=user,
            role=ShipmentTrackingAccessRole.SHIPPER,
            contact=contact,
            identity_status=ShipmentTrackingIdentityStatus.VERIFIED,
        )
        self.client.force_login(user)
        session = self.client.session
        session[ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY] = grant.id
        session.save()

        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            response = self.client.post(
                reverse(
                    "scan:scan_shipment_track",
                    kwargs={"tracking_token": shipment.tracking_token},
                )
                + f"?role={ShipmentTrackingAccessRole.SHIPPER}&identifier={contact.asf_id}",
                {
                    "status": ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
                    "actor_name": "Shipper",
                    "actor_structure": "Org",
                    "proof_no_photo": "on",
                    "proof_carton_reference": "C-001",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ShipmentTrackingEvent.objects.count(), 0)

    def test_scan_shipment_track_post_stores_actor_snapshot_and_manual_proof_for_restricted_user(
        self,
    ):
        shipment = self._create_shipment(status=ShipmentStatus.SHIPPED)
        contact = Contact.objects.create(
            name="Correspondant Tracking",
            email="correspondant@example.com",
            is_active=True,
        )
        shipment.correspondent_contact_ref = contact
        shipment.correspondent_name = contact.name
        shipment.save(update_fields=["correspondent_contact_ref", "correspondent_name"])
        user = get_user_model().objects.create_user(
            username="correspondant@example.com",
            email="correspondant@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        grant = ShipmentTrackingAccessGrant.objects.create(
            user=user,
            role=ShipmentTrackingAccessRole.CORRESPONDENT,
            contact=contact,
            identity_status=ShipmentTrackingIdentityStatus.PENDING,
        )
        self.client.force_login(user)
        session = self.client.session
        session[ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY] = grant.id
        session.save()

        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            response = self.client.post(
                reverse(
                    "scan:scan_shipment_track",
                    kwargs={"tracking_token": shipment.tracking_token},
                )
                + f"?role={ShipmentTrackingAccessRole.CORRESPONDENT}&identifier={contact.asf_id}",
                {
                    "status": ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
                    "actor_name": "Correspondant",
                    "actor_structure": "Escale",
                    "proof_no_photo": "on",
                    "proof_carton_reference": "C-900",
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        event = ShipmentTrackingEvent.objects.get()
        self.assertEqual(event.actor_role, ShipmentTrackingAccessRole.CORRESPONDENT)
        self.assertEqual(event.actor_identifier, contact.asf_id)
        self.assertEqual(event.actor_email, user.email)
        self.assertEqual(event.actor_identity_status, ShipmentTrackingIdentityStatus.PENDING)
        self.assertEqual(event.auth_source, "qr_restricted")
        self.assertEqual(event.proof_mode, "manual")
        self.assertEqual(event.proof_carton_reference, "C-900")
        self.assertEqual(event.actor_snapshot["role"], ShipmentTrackingAccessRole.CORRESPONDENT)

    def test_scan_shipment_track_pending_shipper_creation_creates_request_and_grant(self):
        self.client.logout()
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        shipment.shipper_contact_ref = None
        shipment.shipper_name = "Nouvelle structure expéditeur"
        shipment.save(update_fields=["shipper_contact_ref", "shipper_name"])

        with mock.patch(
            "wms.views_scan_shipments.send_or_enqueue_email_safe",
            return_value=True,
        ) as send_mock:
            response = self.client.post(
                reverse(
                    "scan:scan_shipment_track",
                    kwargs={"tracking_token": shipment.tracking_token},
                ),
                {
                    "action": "create_pending_account",
                    "role": ShipmentTrackingAccessRole.SHIPPER,
                    "email": "pending-shipper@example.com",
                    "structure_name": "Nouvelle structure expéditeur",
                    "address_line1": "1 rue du test",
                    "city": "Paris",
                    "country": "France",
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        shipment.refresh_from_db()
        self.assertIsNotNone(shipment.shipper_contact_ref)
        self.assertFalse(shipment.shipper_contact_ref.is_active)
        self.assertTrue(
            ShipmentTrackingAccessGrant.objects.filter(
                role=ShipmentTrackingAccessRole.SHIPPER,
                contact=shipment.shipper_contact_ref,
                identity_status=ShipmentTrackingIdentityStatus.PENDING,
            ).exists()
        )
        account_request = PublicAccountRequest.objects.get(contact=shipment.shipper_contact_ref)
        self.assertEqual(account_request.status, PublicAccountRequestStatus.PENDING)
        self.assertEqual(account_request.account_type, PublicAccountRequestType.SHIPPER)
        send_mock.assert_called_once()

    def test_scan_shipment_track_pending_shipper_creation_reuses_pending_request(self):
        self.client.logout()
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        shipment.shipper_contact_ref = None
        shipment.save(update_fields=["shipper_contact_ref"])
        payload = {
            "action": "create_pending_account",
            "role": ShipmentTrackingAccessRole.SHIPPER,
            "email": "pending-shipper-reuse@example.com",
            "structure_name": "Structure reuse",
            "address_line1": "1 rue du test",
            "city": "Paris",
            "country": "France",
        }

        with mock.patch("wms.views_scan_shipments.send_or_enqueue_email_safe", return_value=True):
            for _index in range(2):
                response = self.client.post(
                    reverse(
                        "scan:scan_shipment_track",
                        kwargs={"tracking_token": shipment.tracking_token},
                    ),
                    payload,
                )
                self.assertEqual(response.status_code, 302)

        shipment.refresh_from_db()
        self.assertEqual(
            PublicAccountRequest.objects.filter(
                contact=shipment.shipper_contact_ref,
                status=PublicAccountRequestStatus.PENDING,
            ).count(),
            1,
        )
        self.assertEqual(
            ShipmentTrackingAccessGrant.objects.filter(
                contact=shipment.shipper_contact_ref,
                role=ShipmentTrackingAccessRole.SHIPPER,
            ).count(),
            1,
        )

    def test_scan_shipment_track_pending_volunteer_creation_creates_request_and_grant(self):
        self.client.logout()
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)

        with mock.patch(
            "wms.views_scan_shipments.send_or_enqueue_email_safe",
            return_value=True,
        ) as send_mock:
            response = self.client.post(
                reverse(
                    "scan:scan_shipment_track",
                    kwargs={"tracking_token": shipment.tracking_token},
                ),
                {
                    "action": "create_pending_account",
                    "role": ShipmentTrackingAccessRole.VOLUNTEER,
                    "email": "pending-volunteer@example.com",
                    "first_name": "Jeanne",
                    "last_name": "Test",
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        volunteer_request = VolunteerAccountRequest.objects.get(
            email="pending-volunteer@example.com"
        )
        self.assertEqual(volunteer_request.status, VolunteerAccountRequestStatus.PENDING)
        profile = VolunteerProfile.objects.get(user__email="pending-volunteer@example.com")
        self.assertFalse(profile.is_active)
        self.assertTrue(
            ShipmentTrackingAccessGrant.objects.filter(
                role=ShipmentTrackingAccessRole.VOLUNTEER,
                volunteer_profile=profile,
                identity_status=ShipmentTrackingIdentityStatus.PENDING,
            ).exists()
        )
        send_mock.assert_called_once()

    def test_scan_shipment_track_pending_volunteer_creation_reuses_pending_request(self):
        self.client.logout()
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        payload = {
            "action": "create_pending_account",
            "role": ShipmentTrackingAccessRole.VOLUNTEER,
            "email": "pending-volunteer-reuse@example.com",
            "first_name": "Jean",
            "last_name": "Reuse",
        }

        with mock.patch("wms.views_scan_shipments.send_or_enqueue_email_safe", return_value=True):
            for _index in range(2):
                response = self.client.post(
                    reverse(
                        "scan:scan_shipment_track",
                        kwargs={"tracking_token": shipment.tracking_token},
                    ),
                    payload,
                )
                self.assertEqual(response.status_code, 302)

        self.assertEqual(
            VolunteerAccountRequest.objects.filter(
                email="pending-volunteer-reuse@example.com",
                status=VolunteerAccountRequestStatus.PENDING,
            ).count(),
            1,
        )
        profile = VolunteerProfile.objects.get(user__email="pending-volunteer-reuse@example.com")
        self.assertEqual(
            ShipmentTrackingAccessGrant.objects.filter(
                volunteer_profile=profile,
                role=ShipmentTrackingAccessRole.VOLUNTEER,
            ).count(),
            1,
        )

    @override_settings(ENABLE_SHIPMENT_TRACK_LEGACY=True)
    def test_scan_shipment_track_legacy_renders_read_only_tracking(self):
        runtime = WmsRuntimeSettings.get_solo()
        runtime.enable_shipment_track_legacy = True
        runtime.save(update_fields=["enable_shipment_track_legacy"])
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
