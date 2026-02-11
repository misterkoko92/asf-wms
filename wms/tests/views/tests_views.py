from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from contacts.models import Contact, ContactAddress, ContactTag, ContactType
from wms.models import (
    AssociationProfile,
    Carton,
    CartonItem,
    CartonFormat,
    CartonStatus,
    Destination,
    Document,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    Location,
    Order,
    OrderStatus,
    Product,
    ProductLot,
    ProductLotStatus,
    PublicAccountRequest,
    PublicOrderLink,
    Receipt,
    ReceiptHorsFormat,
    ReceiptLine,
    ReceiptStatus,
    ReceiptType,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    Warehouse,
)
from wms.services import StockError


class ScanViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="scan-user",
            password="pass1234",
            is_staff=True,
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="scan-admin", password="pass1234", email="admin@example.com"
        )
        self.client.force_login(self.user)
        self.warehouse = Warehouse.objects.create(name="Reception", code="REC")
        self.location = Location.objects.create(
            warehouse=self.warehouse, zone="A", aisle="01", shelf="001"
        )
        self.product = Product.objects.create(
            sku="SKU-001",
            name="Produit Test",
            weight_g=100,
            volume_cm3=100,
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )
        CartonFormat.objects.create(
            name="Standard",
            length_cm=40,
            width_cm=30,
            height_cm=30,
            max_weight_g=8000,
            is_default=True,
        )
        ProductLot.objects.create(
            product=self.product,
            lot_code="LOT-01",
            received_on=date(2025, 12, 1),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=50,
            location=self.location,
        )

        self.shipper = self._create_contact(
            "Shipper",
            tags=["expediteur"],
            address_country="FRANCE",
        )
        self.recipient = self._create_contact(
            "Recipient",
            tags=["destinataire"],
            address_country="COTE D'IVOIRE",
        )
        self.correspondent = self._create_contact(
            "Correspondent",
            tags=["correspondant"],
            address_country="COTE D'IVOIRE",
            contact_type=ContactType.PERSON,
        )
        self.destination = Destination.objects.create(
            city="ABIDJAN",
            iata_code="ABJ",
            country="COTE D'IVOIRE",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        self.transporter = self._create_contact(
            "Transporter",
            tags=["transporteur"],
            address_country="FRANCE",
        )
        self.donor = self._create_contact(
            "Donor",
            tags=["donateur"],
            address_country="FRANCE",
        )

    def _create_contact(self, name, tags, address_country, contact_type=ContactType.ORGANIZATION):
        contact = Contact.objects.create(
            name=name, contact_type=contact_type, is_active=True
        )
        for tag in tags:
            tag_obj, _ = ContactTag.objects.get_or_create(name=tag)
            contact.tags.add(tag_obj)
        ContactAddress.objects.create(
            contact=contact,
            address_line1="1 Rue Test",
            city="City",
            postal_code="00000",
            country=address_country,
            is_default=True,
        )
        return contact

    def _create_shipment_with_carton(self):
        shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name=self.shipper.name,
            recipient_name=self.recipient.name,
            correspondent_name=self.correspondent.name,
            destination=self.destination,
            destination_address=str(self.destination),
            destination_country=self.destination.country,
            created_by=self.user,
        )
        carton = Carton.objects.create(
            code="C-SHIP",
            status=CartonStatus.PACKED,
            shipment=shipment,
        )
        CartonItem.objects.create(
            carton=carton,
            product_lot=ProductLot.objects.first(),
            quantity=1,
        )
        return shipment, carton

    def _request_scan_route(self, route_name, method="get", kwargs=None, data=None):
        url = reverse(route_name, kwargs=kwargs or {})
        client_method = getattr(self.client, method)
        return client_method(url, data or {})

    def _scan_internal_route_specs(self):
        shipment, carton = self._create_shipment_with_carton()
        document = Document.objects.create(shipment=shipment, doc_type="additional")
        return [
            ("scan:scan_root", "get", {}, None),
            ("scan:scan_stock", "get", {}, None),
            ("scan:scan_cartons_ready", "get", {}, None),
            ("scan:scan_shipments_ready", "get", {}, None),
            ("scan:scan_receipts_view", "get", {}, None),
            ("scan:scan_receive", "get", {}, None),
            ("scan:scan_receive_pallet", "get", {}, None),
            ("scan:scan_receive_association", "get", {}, None),
            ("scan:scan_stock_update", "get", {}, None),
            ("scan:scan_orders_view", "get", {}, None),
            ("scan:scan_order", "get", {}, None),
            ("scan:scan_pack", "get", {}, None),
            ("scan:scan_shipment_create", "get", {}, None),
            ("scan:scan_shipment_edit", "get", {"shipment_id": shipment.id}, None),
            (
                "scan:scan_shipment_document",
                "get",
                {"shipment_id": shipment.id, "doc_type": "shipment_note"},
                None,
            ),
            (
                "scan:scan_shipment_carton_document",
                "get",
                {"shipment_id": shipment.id, "carton_id": carton.id},
                None,
            ),
            ("scan:scan_carton_document", "get", {"carton_id": carton.id}, None),
            ("scan:scan_carton_picking", "get", {"carton_id": carton.id}, None),
            (
                "scan:scan_shipment_document_upload",
                "post",
                {"shipment_id": shipment.id},
                {},
            ),
            (
                "scan:scan_shipment_document_delete",
                "post",
                {"shipment_id": shipment.id, "document_id": document.id},
                {},
            ),
            ("scan:scan_shipment_labels", "get", {"shipment_id": shipment.id}, None),
            (
                "scan:scan_shipment_label",
                "get",
                {"shipment_id": shipment.id, "carton_id": carton.id},
                None,
            ),
            ("scan:scan_print_templates", "get", {}, None),
            (
                "scan:scan_print_template_edit",
                "get",
                {"doc_type": "shipment_note"},
                None,
            ),
            ("scan:scan_print_template_preview", "post", {}, {}),
            ("scan:scan_import", "get", {}, None),
            ("scan:scan_faq", "get", {}, None),
            ("scan:scan_out", "get", {}, None),
            ("scan:scan_sync", "get", {}, None),
        ]

    def _create_public_order_link_with_order(self):
        link = PublicOrderLink.objects.create(label="Public test")
        order = Order.objects.create(
            status=OrderStatus.DRAFT,
            public_link=link,
            shipper_name=self.shipper.name,
            recipient_name=self.recipient.name,
            correspondent_name=self.correspondent.name,
            destination_address="1 rue test",
            destination_city="Paris",
            destination_country="France",
            created_by=self.user,
        )
        order.lines.create(product=self.product, quantity=1)
        return link, order

    def test_scan_stock_update_creates_lot(self):
        url = reverse("scan:scan_stock_update")
        payload = {
            "product_code": self.product.sku,
            "quantity": 5,
            "expires_on": "2026-01-10",
            "lot_code": "LOT-NEW",
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ProductLot.objects.count(), 2)

    def test_scan_internal_routes_require_staff(self):
        non_staff = get_user_model().objects.create_user(
            username="scan-non-staff",
            password="pass1234",
        )
        self.client.force_login(non_staff)
        for route_name, method, kwargs, data in self._scan_internal_route_specs():
            with self.subTest(route_name=route_name, method=method):
                response = self._request_scan_route(
                    route_name,
                    method=method,
                    kwargs=kwargs,
                    data=data,
                )
                self.assertEqual(response.status_code, 403)

    def test_scan_internal_routes_redirect_anonymous_to_admin_login(self):
        self.client.logout()
        for route_name, method, kwargs, data in self._scan_internal_route_specs():
            with self.subTest(route_name=route_name, method=method):
                response = self._request_scan_route(
                    route_name,
                    method=method,
                    kwargs=kwargs,
                    data=data,
                )
                self.assertEqual(response.status_code, 302)
                self.assertIn("/admin/login/", response.url)

    def test_scan_cartons_ready_blocks_assigned_update(self):
        shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Contact",
            destination_address="Address",
            destination_country="France",
            created_by=self.user,
        )
        carton = Carton.objects.create(
            code="C-001",
            status=CartonStatus.PACKED,
            shipment=shipment,
        )
        url = reverse("scan:scan_cartons_ready")
        response = self.client.post(
            url,
            {"action": "update_carton_status", "carton_id": carton.id, "status": "draft"},
        )
        self.assertEqual(response.status_code, 302)
        carton.refresh_from_db()
        self.assertEqual(carton.status, CartonStatus.PACKED)

    def test_scan_receive_create_and_receive_line(self):
        url = reverse("scan:scan_receive")
        response = self.client.post(
            url,
            {
                "action": "create_receipt",
                "receipt_type": ReceiptType.DONATION,
                "received_on": "2025-12-20",
                "warehouse": self.warehouse.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        receipt = Receipt.objects.first()
        self.assertIsNotNone(receipt)
        response = self.client.post(
            url,
            {
                "action": "add_line",
                "receipt_id": receipt.id,
                "product_code": self.product.sku,
                "quantity": 3,
                "lot_code": "LOT-R1",
                "receive_now": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        receipt.refresh_from_db()
        line = ReceiptLine.objects.get(receipt=receipt)
        self.assertIsNotNone(line.received_lot_id)
        self.assertEqual(receipt.status, ReceiptStatus.RECEIVED)

    def test_scan_receive_receive_now_error_refreshes_context(self):
        receipt = Receipt.objects.create(
            receipt_type=ReceiptType.DONATION,
            status=ReceiptStatus.DRAFT,
            received_on=date(2025, 12, 20),
            warehouse=self.warehouse,
            created_by=self.user,
        )
        url = reverse("scan:scan_receive")
        with mock.patch(
            "wms.receipt_handlers.receive_receipt_line",
            side_effect=StockError("x"),
        ):
            response = self.client.post(
                url,
                {
                    "action": "add_line",
                    "receipt_id": receipt.id,
                    "product_code": self.product.sku,
                    "quantity": 2,
                    "receive_now": "on",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ReceiptLine.objects.count(), 1)
        self.assertEqual(len(response.context["receipt_lines"]), 1)

    def test_scan_order_create_and_prepare(self):
        url = reverse("scan:scan_order")
        response = self.client.post(
            url,
            {
                "action": "create_order",
                "shipper_name": "Sender",
                "recipient_name": "Recipient",
                "destination_address": "10 Rue Test",
                "destination_country": "France",
            },
        )
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get()
        order_id = order.id
        response = self.client.post(
            url,
            {
                "action": "add_line",
                "order_id": order_id,
                "product_code": self.product.sku,
                "quantity": 4,
            },
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            url,
            {
                "action": "prepare_order",
                "order_id": order_id,
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_scan_order_add_line_reserve_error_refreshes_context(self):
        order = Order.objects.create(
            status=OrderStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Contact",
            destination_address="10 Rue Test",
            destination_country="France",
            created_by=self.user,
        )
        url = reverse("scan:scan_order")
        with mock.patch(
            "wms.order_scan_handlers.reserve_stock_for_order",
            side_effect=StockError("x"),
        ):
            response = self.client.post(
                url,
                {
                    "action": "add_line",
                    "order_id": order.id,
                    "product_code": self.product.sku,
                    "quantity": 4,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("order_lines", response.context)

    def test_scan_pack_creates_carton(self):
        url = reverse("scan:scan_pack")
        response = self.client.post(
            url,
            {
                "line_count": 1,
                "line_1_product_code": self.product.sku,
                "line_1_quantity": 2,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Carton.objects.count(), 1)

    def test_scan_shipment_create_assigns_carton(self):
        carton = Carton.objects.create(
            code="C-READY",
            status=CartonStatus.PACKED,
        )
        CartonItem.objects.create(
            carton=carton,
            product_lot=ProductLot.objects.first(),
            quantity=1,
        )
        url = reverse("scan:scan_shipment_create")
        response = self.client.post(
            url,
            {
                "destination": self.destination.id,
                "shipper_contact": self.shipper.id,
                "recipient_contact": self.recipient.id,
                "correspondent_contact": self.correspondent.id,
                "carton_count": 1,
                "line_1_carton_id": carton.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        carton.refresh_from_db()
        self.assertIsNotNone(carton.shipment_id)

    def test_scan_shipment_create_from_product(self):
        url = reverse("scan:scan_shipment_create")
        response = self.client.post(
            url,
            {
                "destination": self.destination.id,
                "shipper_contact": self.shipper.id,
                "recipient_contact": self.recipient.id,
                "correspondent_contact": self.correspondent.id,
                "carton_count": 1,
                "line_1_product_code": self.product.sku,
                "line_1_quantity": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Shipment.objects.count(), 1)

    def test_scan_shipment_edit_updates_destination(self):
        shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name=self.shipper.name,
            recipient_name=self.recipient.name,
            correspondent_name=self.correspondent.name,
            destination=self.destination,
            destination_address=str(self.destination),
            destination_country=self.destination.country,
            created_by=self.user,
        )
        carton = Carton.objects.create(code="C-EDIT", status=CartonStatus.PACKED, shipment=shipment)
        CartonItem.objects.create(
            carton=carton,
            product_lot=ProductLot.objects.first(),
            quantity=1,
        )
        new_destination = Destination.objects.create(
            city="BAMAKO",
            iata_code="BKO",
            country="COTE D'IVOIRE",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        url = reverse("scan:scan_shipment_edit", args=[shipment.id])
        response = self.client.post(
            url,
            {
                "destination": new_destination.id,
                "shipper_contact": self.shipper.id,
                "recipient_contact": self.recipient.id,
                "correspondent_contact": self.correspondent.id,
                "carton_count": 1,
                "line_1_carton_id": carton.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        shipment.refresh_from_db()
        self.assertEqual(shipment.destination_id, new_destination.id)

    def test_scan_shipment_document_upload_rejects_extension(self):
        shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Contact",
            destination_address="Addr",
            destination_country="France",
            created_by=self.user,
        )
        url = reverse("scan:scan_shipment_document_upload", args=[shipment.id])
        upload = SimpleUploadedFile("malware.exe", b"nope", content_type="application/octet-stream")
        response = self.client.post(url, {"document_file": upload})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Document.objects.count(), 0)

    def test_scan_print_templates_requires_superuser(self):
        url = reverse("scan:scan_print_templates")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.superuser)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_scan_print_template_edit_renders_for_superuser(self):
        self.client.force_login(self.superuser)
        url = reverse("scan:scan_print_template_edit", args=["shipment_note"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_scan_receive_pallet_creates_receipt(self):
        url = reverse("scan:scan_receive_pallet")
        response = self.client.post(
            url,
            {
                "received_on": "2025-12-20",
                "pallet_count": 2,
                "source_contact": self.donor.id,
                "carrier_contact": self.transporter.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        receipt = Receipt.objects.filter(receipt_type=ReceiptType.PALLET).first()
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.pallet_count, 2)

    def test_scan_receive_association_creates_receipt(self):
        url = reverse("scan:scan_receive_association")
        response = self.client.post(
            url,
            {
                "received_on": "2025-12-20",
                "carton_count": 3,
                "hors_format_count": 1,
                "line_1_description": "Hors format",
                "source_contact": self.shipper.id,
                "carrier_contact": self.transporter.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        receipt = Receipt.objects.filter(receipt_type=ReceiptType.ASSOCIATION).first()
        self.assertIsNotNone(receipt)
        self.assertEqual(ReceiptHorsFormat.objects.count(), 1)

    def test_scan_out_consumes_stock(self):
        url = reverse("scan:scan_out")
        response = self.client.post(
            url,
            {
                "product_code": self.product.sku,
                "quantity": 5,
            },
        )
        self.assertEqual(response.status_code, 302)
        lot = ProductLot.objects.first()
        self.assertEqual(lot.quantity_on_hand, 45)

    def test_scan_sync_returns_state(self):
        url = reverse("scan:scan_sync")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("version", payload)
        self.assertIn("changed_at", payload)

    def test_scan_shipment_document_renders(self):
        shipment, _carton = self._create_shipment_with_carton()
        url = reverse("scan:scan_shipment_document", args=[shipment.id, "shipment_note"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_scan_shipment_carton_document_renders(self):
        shipment, carton = self._create_shipment_with_carton()
        url = reverse("scan:scan_shipment_carton_document", args=[shipment.id, carton.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_scan_shipment_labels_render(self):
        shipment, carton = self._create_shipment_with_carton()
        url = reverse("scan:scan_shipment_labels", args=[shipment.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        url = reverse("scan:scan_shipment_label", args=[shipment.id, carton.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_scan_shipment_track_accepts_token_route(self):
        shipment, _carton = self._create_shipment_with_carton()
        self.client.logout()
        url = reverse("scan:scan_shipment_track", args=[shipment.tracking_token])
        response = self.client.post(
            url,
            {
                "status": "planning_ok",
                "actor_name": "Test",
                "actor_structure": "ASF",
                "comments": "ok",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            ShipmentTrackingEvent.objects.filter(shipment=shipment).count(), 1
        )

    def test_scan_public_routes_allow_anonymous(self):
        shipment, _carton = self._create_shipment_with_carton()
        link, order = self._create_public_order_link_with_order()
        self.client.logout()
        routes = [
            reverse("scan:scan_service_worker"),
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
            reverse("scan:scan_public_order", args=[link.token]),
            reverse("scan:scan_public_account_request", args=[link.token]),
            reverse("scan:scan_public_order_summary", args=[link.token, order.id]),
        ]
        for url in routes:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_scan_shipment_track_legacy_blocks_anonymous(self):
        shipment, _carton = self._create_shipment_with_carton()
        self.client.logout()
        legacy_url = reverse("scan:scan_shipment_track_legacy", args=[shipment.reference])
        response = self.client.get(legacy_url)
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            legacy_url,
            {
                "status": "planning_ok",
                "actor_name": "Test",
                "actor_structure": "ASF",
                "comments": "ko",
            },
        )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(
            ShipmentTrackingEvent.objects.filter(shipment=shipment).count(), 0
        )

    def test_scan_shipment_track_legacy_blocks_non_staff(self):
        shipment, _carton = self._create_shipment_with_carton()
        non_staff = get_user_model().objects.create_user(
            username="legacy-non-staff",
            password="pass1234",
        )
        self.client.force_login(non_staff)
        legacy_url = reverse("scan:scan_shipment_track_legacy", args=[shipment.reference])
        response = self.client.get(legacy_url)
        self.assertEqual(response.status_code, 404)

    def test_scan_shipment_track_legacy_is_read_only_for_staff(self):
        shipment, _carton = self._create_shipment_with_carton()
        self.client.force_login(self.superuser)
        legacy_url = reverse("scan:scan_shipment_track_legacy", args=[shipment.reference])
        response = self.client.get(legacy_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Mise &agrave; jour du suivi indisponible sur ce lien legacy.",
        )
        self.assertNotContains(response, str(shipment.tracking_token))
        response = self.client.post(
            legacy_url,
            {
                "status": "planning_ok",
                "actor_name": "Test",
                "actor_structure": "ASF",
                "comments": "ko",
            },
        )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(
            ShipmentTrackingEvent.objects.filter(shipment=shipment).count(), 0
        )


class PortalPermissionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="portal-user",
            password="pass1234",
            email="portal@example.com",
        )
        self.contact = Contact.objects.create(
            name="Association Test",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def test_portal_dashboard_requires_association_profile(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_portal_routes_redirect_to_change_password_when_forced(self):
        AssociationProfile.objects.create(
            user=self.user,
            contact=self.contact,
            must_change_password=True,
        )
        self.client.force_login(self.user)

        dashboard_response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(dashboard_response.status_code, 302)
        self.assertEqual(
            dashboard_response.url,
            reverse("portal:portal_change_password"),
        )

        password_response = self.client.get(reverse("portal:portal_change_password"))
        self.assertEqual(password_response.status_code, 200)

    def test_portal_dashboard_allows_user_with_profile(self):
        AssociationProfile.objects.create(
            user=self.user,
            contact=self.contact,
            must_change_password=False,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(response.status_code, 200)


class PublicAccountRequestViewTests(TestCase):
    def setUp(self):
        self.url = reverse("portal:portal_account_request")

    def _payload(self, **overrides):
        payload = {
            "association_name": "Association Test",
            "email": "association@example.com",
            "phone": "0102030405",
            "line1": "1 Rue Test",
            "line2": "",
            "postal_code": "75001",
            "city": "Paris",
            "country": "France",
            "notes": "Demande de test",
            "contact_id": "",
        }
        payload.update(overrides)
        return payload

    @override_settings(ACCOUNT_REQUEST_THROTTLE_SECONDS=300)
    @mock.patch("wms.account_request_handlers.get_admin_emails")
    def test_portal_account_request_creates_request_and_sends_notifications(
        self,
        get_admin_emails_mock,
    ):
        get_admin_emails_mock.return_value = ["admin@example.com"]

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(self.url, self._payload())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(PublicAccountRequest.objects.count(), 1)
        self.assertEqual(len(callbacks), 1)
        queued_events = IntegrationEvent.objects.filter(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.PENDING,
        )
        self.assertEqual(queued_events.count(), 2)

    @override_settings(ACCOUNT_REQUEST_THROTTLE_SECONDS=3600)
    def test_portal_account_request_throttles_repeated_submission_from_same_ip(self):
        with self.captureOnCommitCallbacks(execute=True):
            first_response = self.client.post(
                self.url,
                self._payload(email="first@example.com"),
                REMOTE_ADDR="10.0.0.1",
            )
        self.assertEqual(first_response.status_code, 302)

        with self.captureOnCommitCallbacks(execute=True):
            second_response = self.client.post(
                self.url,
                self._payload(email="second@example.com"),
                REMOTE_ADDR="10.0.0.1",
            )
        self.assertEqual(second_response.status_code, 200)
        self.assertContains(
            second_response,
            "Une demande récente a déjà été envoyée. Merci de patienter quelques minutes.",
        )
        self.assertEqual(PublicAccountRequest.objects.count(), 1)
        self.assertEqual(
            IntegrationEvent.objects.filter(
                source="wms.email",
                event_type="send_email",
            ).count(),
            1,
        )
