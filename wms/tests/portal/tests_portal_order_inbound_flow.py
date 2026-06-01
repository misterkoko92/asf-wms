import json
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from wms.models import (
    AssociationPickupAddress,
    DocumentScanStatus,
    IntegrationEvent,
    Location,
    Order,
    OrderDocumentType,
    OrderInboundArrivalMode,
    OrderReviewStatus,
    PortalOrderDraft,
    PortalOrderDraftStatus,
    Product,
    ProductLot,
    ShipmentRecipientOrganization,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
    Warehouse,
)
from wms.portal_recipient_sync import sync_association_recipient_to_contact
from wms.tests.views.tests_views_portal import PortalBaseTestCase


class PortalOrderInboundFlowTests(PortalBaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = cls._create_portal_user("portal-inbound-user", "portal-inbound@example.com")
        cls.profile = cls._create_profile(cls.user, with_address=True)
        cls.delivery_recipient = cls._create_delivery_recipient(cls.profile)
        sync_association_recipient_to_contact(cls.delivery_recipient)
        shipment_recipient = ShipmentRecipientOrganization.objects.get(
            organization=cls.delivery_recipient.synced_contact,
            destination=cls.delivery_recipient.destination,
        )
        shipment_recipient.validation_status = ShipmentValidationStatus.VALIDATED
        shipment_recipient.save(update_fields=["validation_status"])
        cls._create_portal_operational_contact(
            cls.profile,
            is_administrative=True,
            email="inbound-admin@example.org",
            phone="+33101010101",
        )
        cls._create_portal_operational_contact(
            cls.profile,
            is_shipping=True,
            email="inbound-prep@example.org",
            phone="+33202020202",
        )
        ShipmentShipperRecipientLink.objects.get_or_create(
            shipper=cls.profile.contact.shipment_shippers.get(),
            recipient_organization=shipment_recipient,
            defaults={"is_active": True},
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.order_create_url = reverse("portal:portal_order_create")
        self.draft_autosave_url = reverse("portal:portal_order_draft_autosave")
        self.draft_clear_url = reverse("portal:portal_order_draft_clear")

    def _create_stock_product(self, *, sku="DRAFT-SKU", name="Produit brouillon"):
        product = Product.objects.create(sku=sku, name=name, weight_g=100)
        warehouse = Warehouse.objects.create(name=f"Entrepôt {sku}")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        ProductLot.objects.create(
            product=product,
            lot_code=f"LOT-{sku}",
            quantity_on_hand=1000,
            location=location,
        )
        return product

    def _base_payload(self):
        return {
            "destination_id": str(self.delivery_recipient.destination_id),
            "recipient_id": str(self.delivery_recipient.id),
            "notes": "Flux inbound expéditeur",
            "has_shipper_inbound": "1",
            "declared_carton_count": "4",
            "declared_out_of_format_count": "1",
            "parcel_guidelines_confirmed": "1",
        }

    def test_portal_order_draft_autosave_stores_payload_without_creating_order(self):
        product = self._create_stock_product()
        order_count = Order.objects.count()
        event_count = IntegrationEvent.objects.count()

        response = self.client.post(
            self.draft_autosave_url,
            data=json.dumps(
                {
                    "payload": {
                        "form_data": {
                            "destination_id": str(self.delivery_recipient.destination_id),
                            "recipient_id": str(self.delivery_recipient.id),
                            "notes": "Brouillon autosave",
                            "has_shipper_inbound": False,
                            "wants_stock_completion": False,
                        },
                        "line_quantities": {str(product.id): "500"},
                    }
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), order_count)
        self.assertEqual(IntegrationEvent.objects.count(), event_count)
        draft = PortalOrderDraft.objects.get()
        self.assertEqual(draft.created_by, self.user)
        self.assertEqual(draft.association_contact, self.profile.contact)
        self.assertEqual(draft.status, PortalOrderDraftStatus.ACTIVE)
        self.assertEqual(draft.payload["line_quantities"][str(product.id)], "500")
        self.assertEqual(draft.payload["form_data"]["notes"], "Brouillon autosave")

    def test_portal_order_create_restores_active_draft_on_get(self):
        product = self._create_stock_product(sku="DRAFT-RESTORE")
        PortalOrderDraft.objects.create(
            created_by=self.user,
            association_contact=self.profile.contact,
            payload={
                "form_data": {
                    "destination_id": str(self.delivery_recipient.destination_id),
                    "recipient_id": str(self.delivery_recipient.id),
                    "notes": "Notes restaurées",
                    "has_shipper_inbound": False,
                    "wants_stock_completion": False,
                },
                "line_quantities": {str(product.id): "498"},
            },
        )

        response = self.client.get(self.order_create_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form_data"]["destination_id"],
            str(self.delivery_recipient.destination_id),
        )
        self.assertEqual(response.context["form_data"]["notes"], "Notes restaurées")
        self.assertEqual(response.context["line_quantities"][str(product.id)], "498")
        self.assertContains(response, f'name="product_{product.id}_qty"', html=False)
        self.assertContains(response, 'value="498"', html=False)

    def test_portal_order_draft_clear_abandons_current_draft_and_starts_blank_order(self):
        PortalOrderDraft.objects.create(
            created_by=self.user,
            association_contact=self.profile.contact,
            payload={
                "form_data": {
                    "destination_id": str(self.delivery_recipient.destination_id),
                    "recipient_id": str(self.delivery_recipient.id),
                    "notes": "Brouillon à effacer",
                },
                "line_quantities": {},
            },
        )

        response = self.client.get(self.order_create_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Effacer le brouillon en cours et créer une nouvelle commande",
        )
        self.assertContains(response, "Brouillon à effacer")

        response = self.client.post(self.draft_clear_url)

        self.assertEqual(response.status_code, 200)
        draft = PortalOrderDraft.objects.get()
        self.assertEqual(draft.status, PortalOrderDraftStatus.ABANDONED)

        response = self.client.get(self.order_create_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form_data"]["notes"], "")
        self.assertNotContains(response, "Brouillon à effacer")

    def test_portal_order_create_marks_active_draft_submitted_after_successful_submit(self):
        draft = PortalOrderDraft.objects.create(
            created_by=self.user,
            association_contact=self.profile.contact,
            payload={
                "form_data": {
                    "destination_id": str(self.delivery_recipient.destination_id),
                    "recipient_id": str(self.delivery_recipient.id),
                    "notes": "Commande finale",
                },
                "line_quantities": {},
            },
        )
        payload = self._base_payload()
        payload["arrival_mode"] = OrderInboundArrivalMode.DROPOFF_WAREHOUSE

        with mock.patch("wms.views_portal_orders.send_portal_order_notifications"):
            response = self.client.post(self.order_create_url, payload)

        self.assertEqual(response.status_code, 302)
        draft.refresh_from_db()
        order = Order.objects.filter(association_contact=self.profile.contact).latest("id")
        self.assertEqual(draft.status, PortalOrderDraftStatus.SUBMITTED)
        self.assertEqual(draft.submitted_order, order)

    def test_portal_order_create_supports_shipper_inbound_dropoff_without_documents(self):
        payload = self._base_payload()
        payload["arrival_mode"] = OrderInboundArrivalMode.DROPOFF_WAREHOUSE

        with mock.patch("wms.views_portal_orders.send_portal_order_notifications"):
            response = self.client.post(self.order_create_url, payload)

        self.assertEqual(response.status_code, 302)
        order = Order.objects.filter(association_contact=self.profile.contact).latest("id")
        self.assertEqual(
            order.inbound_delivery.arrival_mode, OrderInboundArrivalMode.DROPOFF_WAREHOUSE
        )
        self.assertEqual(order.inbound_delivery.declared_carton_count, 4)
        self.assertEqual(order.inbound_delivery.declared_out_of_format_count, 1)
        self.assertEqual(order.inbound_delivery.declared_pallet_count, 0)
        self.assertTrue(order.inbound_delivery.parcel_guidelines_confirmed)

    def test_portal_order_create_requires_parcel_guidelines_confirmation(self):
        payload = self._base_payload()
        payload["arrival_mode"] = OrderInboundArrivalMode.DROPOFF_WAREHOUSE
        payload.pop("parcel_guidelines_confirmed")

        response = self.client.post(self.order_create_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Certifiez que les colis respectent les consignes ASF.")
        self.assertFalse(Order.objects.filter(association_contact=self.profile.contact).exists())

    def test_portal_order_create_requires_pickup_phone(self):
        payload = self._base_payload()
        payload.update(
            {
                "arrival_mode": OrderInboundArrivalMode.PICKUP_REQUESTED,
                "declared_pallet_count": "1",
                "pickup_contact_name": "Alice",
                "pickup_contact_phone": "",
                "pickup_contact_phone_2": "",
                "pickup_address_line1": "12 Rue Logistique",
                "pickup_postal_code": "75010",
                "pickup_city": "Paris",
                "pickup_country": "France",
                "pickup_available_from_date": "2026-04-20",
                "pickup_opening_slot_1_start": "09:00",
                "pickup_opening_slot_1_end": "12:00",
                "pickup_has_no_access_constraints": "1",
                "tail_lift_required": "1",
                "pallet_truck_required": "1",
                "pickup_information_confirmed": "1",
            }
        )

        response = self.client.post(self.order_create_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Au moins un numéro de téléphone est requis pour l&#x27;enlèvement."
        )
        self.assertFalse(Order.objects.filter(association_contact=self.profile.contact).exists())

    def test_portal_order_create_requires_pallet_count_for_pickup(self):
        payload = self._base_payload()
        payload.update(
            {
                "arrival_mode": OrderInboundArrivalMode.PICKUP_REQUESTED,
                "declared_pallet_count": "",
                "pickup_contact_name": "Alice",
                "pickup_contact_phone": "0102030405",
                "pickup_address_line1": "12 Rue Logistique",
                "pickup_postal_code": "75010",
                "pickup_city": "Paris",
                "pickup_country": "France",
                "pickup_available_from_date": "2026-04-20",
                "pickup_opening_slot_1_start": "09:00",
                "pickup_opening_slot_1_end": "12:00",
                "pickup_has_no_access_constraints": "1",
                "tail_lift_required": "1",
                "pallet_truck_required": "1",
                "pickup_information_confirmed": "1",
            }
        )

        response = self.client.post(self.order_create_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nombre de palettes requis pour l&#x27;enlèvement.")
        self.assertFalse(Order.objects.filter(association_contact=self.profile.contact).exists())

    def test_portal_order_create_accepts_pickup_without_desired_pickup_date(self):
        payload = self._base_payload()
        payload.update(
            {
                "arrival_mode": OrderInboundArrivalMode.PICKUP_REQUESTED,
                "declared_pallet_count": "2",
                "pickup_contact_name": "Alice",
                "pickup_contact_phone": "0102030405",
                "pickup_address_line1": "12 Rue Logistique",
                "pickup_postal_code": "75010",
                "pickup_city": "Paris",
                "pickup_country": "France",
                "pickup_available_from_date": "2026-04-20",
                "pickup_opening_slot_1_start": "09:00",
                "pickup_opening_slot_1_end": "12:00",
                "pickup_has_no_access_constraints": "1",
                "tail_lift_required": "1",
                "pallet_truck_required": "1",
                "pickup_information_confirmed": "1",
            }
        )

        with mock.patch("wms.views_portal_orders.send_portal_order_notifications"):
            response = self.client.post(self.order_create_url, payload)

        self.assertEqual(response.status_code, 302)
        order = Order.objects.filter(association_contact=self.profile.contact).latest("id")
        self.assertEqual(
            order.inbound_delivery.arrival_mode, OrderInboundArrivalMode.PICKUP_REQUESTED
        )
        self.assertEqual(order.inbound_delivery.declared_pallet_count, 2)
        self.assertIsNone(order.inbound_delivery.pickup_requested_for_date)

    def test_portal_order_create_exposes_pickup_open_weekdays(self):
        response = self.client.get(self.order_create_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Je prépare mes propres colis")
        self.assertContains(response, "Vos colis doivent respecter les dimensions ASF")
        self.assertContains(response, "Nombre de palette")
        self.assertContains(
            response, "Je souhaite compléter mes colis avec des produits du stock ASF"
        )
        self.assertContains(response, "Je certifie que les colis respectent les consignes d'ASF")
        self.assertContains(response, "Type d'expédition")
        self.assertContains(response, "Stock ASF")
        self.assertNotContains(response, "La structure prépare ses propres colis")
        self.assertNotContains(response, "Flux structure")
        self.assertContains(response, "Jours d'ouverture")
        self.assertContains(response, 'name="pickup_open_weekdays"')
        for value, label in (
            ("monday", "Lundi"),
            ("tuesday", "Mardi"),
            ("wednesday", "Mercredi"),
            ("thursday", "Jeudi"),
            ("friday", "Vendredi"),
            ("saturday", "Samedi"),
            ("sunday", "Dimanche"),
        ):
            self.assertContains(response, f'value="{value}"', html=False)
            self.assertContains(response, label)
        self.assertContains(
            response,
            "Merci de préciser dans les notes de contraintes d'accès s'il y a des particularités pour des dates spécifiques",
        )

    def test_portal_order_create_exposes_ordered_products_filter(self):
        response = self.client.get(self.order_create_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Afficher uniquement les produits commandés")
        self.assertContains(response, 'id="portal-order-show-ordered-only"')
        self.assertContains(response, 'data-order-product-quantity-filter="1"')
        self.assertContains(response, "applyProductRowFilters")

    def test_portal_order_create_prevents_number_inputs_from_changing_on_wheel(self):
        response = self.client.get(self.order_create_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "preventNumberInputWheelChanges")
        self.assertContains(response, "event.preventDefault()")

    def test_portal_order_create_persists_pickup_open_weekdays(self):
        payload = self._base_payload()
        payload.update(
            {
                "arrival_mode": OrderInboundArrivalMode.PICKUP_REQUESTED,
                "declared_pallet_count": "3",
                "save_pickup_address": "1",
                "pickup_contact_name": "Alice",
                "pickup_contact_phone": "0102030405",
                "pickup_address_line1": "12 Rue Logistique",
                "pickup_postal_code": "75010",
                "pickup_city": "Paris",
                "pickup_country": "France",
                "pickup_available_from_date": "2026-04-20",
                "pickup_open_weekdays": ["monday", "wednesday", "friday"],
                "pickup_opening_slot_1_start": "09:00",
                "pickup_opening_slot_1_end": "12:00",
                "pickup_has_no_access_constraints": "1",
                "tail_lift_required": "1",
                "pallet_truck_required": "1",
                "pickup_information_confirmed": "1",
            }
        )

        with mock.patch("wms.views_portal_orders.send_portal_order_notifications"):
            response = self.client.post(self.order_create_url, payload)

        self.assertEqual(response.status_code, 302)
        order = Order.objects.filter(association_contact=self.profile.contact).latest("id")
        self.assertEqual(
            order.inbound_delivery.pickup_open_weekdays,
            ["monday", "wednesday", "friday"],
        )
        self.assertEqual(
            order.inbound_delivery.pickup_address_book_entry.pickup_open_weekdays,
            ["monday", "wednesday", "friday"],
        )

    def test_portal_order_create_reopens_collapses_after_pickup_validation_error(self):
        payload = self._base_payload()
        payload.update(
            {
                "arrival_mode": OrderInboundArrivalMode.PICKUP_REQUESTED,
                "declared_pallet_count": "1",
                "pickup_contact_name": "Alice",
                "pickup_contact_phone": "",
                "pickup_contact_phone_2": "",
                "pickup_address_line1": "12 Rue Logistique",
                "pickup_postal_code": "75010",
                "pickup_city": "Paris",
                "pickup_country": "France",
                "pickup_available_from_date": "2026-04-20",
                "pickup_opening_slot_1_start": "09:00",
                "pickup_opening_slot_1_end": "12:00",
                "pickup_has_no_access_constraints": "1",
                "tail_lift_required": "1",
                "pallet_truck_required": "1",
                "pickup_information_confirmed": "1",
            }
        )

        response = self.client.post(self.order_create_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'id="portal-order-create-shipper-inbound-collapse" class="collapse show"',
            html=False,
        )
        self.assertContains(
            response,
            'id="portal-order-create-pickup-collapse" class="collapse show"',
            html=False,
        )
        self.assertRegex(
            response.content.decode(),
            r'id="portal-order-create-fulfillment-step"[^>]*data-portal-order-step-hidden="0"',
        )
        self.assertRegex(
            response.content.decode(),
            r'id="portal-order-create-review-step"[^>]*data-portal-order-step-hidden="0"',
        )

    def test_portal_order_detail_allows_upload_before_approval(self):
        order = Order.objects.create(
            association_contact=self.profile.contact,
            shipper_name=self.profile.contact.name,
            shipper_contact=self.profile.contact,
            recipient_name=self.delivery_recipient.name,
            destination_address="1 Rue Test",
            destination_city=self.delivery_recipient.destination.city,
            destination_country=self.delivery_recipient.destination.country,
            review_status=OrderReviewStatus.PENDING,
        )

        response = self.client.post(
            reverse("portal:portal_order_detail", kwargs={"order_id": order.id}),
            {
                "action": "upload_docs",
                "doc_file_invoice": SimpleUploadedFile("invoice.pdf", b"%PDF-1.4 invoice"),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.documents.count(), 1)
        document = order.documents.get()
        self.assertEqual(document.doc_type, OrderDocumentType.INVOICE)
        self.assertEqual(document.scan_status, DocumentScanStatus.PENDING)

    def test_portal_order_create_saves_pickup_address_when_requested(self):
        payload = self._base_payload()
        payload.update(
            {
                "arrival_mode": OrderInboundArrivalMode.PICKUP_REQUESTED,
                "declared_pallet_count": "1",
                "save_pickup_address": "1",
                "pickup_company_name": "Logistique ASF",
                "pickup_contact_name": "Alice",
                "pickup_contact_phone": "0102030405",
                "pickup_address_line1": "12 Rue Logistique",
                "pickup_postal_code": "75010",
                "pickup_city": "Paris",
                "pickup_country": "France",
                "pickup_available_from_date": "2026-04-20",
                "pickup_opening_slot_1_start": "09:00",
                "pickup_opening_slot_1_end": "12:00",
                "pickup_has_no_access_constraints": "1",
                "tail_lift_required": "1",
                "pallet_truck_required": "1",
                "pickup_information_confirmed": "1",
            }
        )

        with mock.patch("wms.views_portal_orders.send_portal_order_notifications"):
            response = self.client.post(self.order_create_url, payload)

        self.assertEqual(response.status_code, 302)
        order = Order.objects.filter(association_contact=self.profile.contact).latest("id")
        self.assertIsNotNone(order.inbound_delivery.pickup_address_book_entry_id)
        address_entry = order.inbound_delivery.pickup_address_book_entry
        self.assertEqual(address_entry.association_contact_id, self.profile.contact_id)
        self.assertEqual(address_entry.pickup_address_line1, "12 Rue Logistique")
        self.assertEqual(address_entry.times_used, 1)

    def test_portal_order_create_can_reuse_saved_pickup_address(self):
        address_entry = AssociationPickupAddress.objects.create(
            association_contact=self.profile.contact,
            label="Entrepôt Paris",
            pickup_company_name="Logistique ASF",
            pickup_contact_name="Alice",
            pickup_contact_phone="0102030405",
            pickup_address_line1="12 Rue Logistique",
            pickup_postal_code="75010",
            pickup_city="Paris",
            pickup_country="France",
            pickup_opening_slot_1_start="09:00",
            pickup_opening_slot_1_end="12:00",
            pickup_has_no_access_constraints=True,
            tail_lift_required=True,
            pallet_truck_required=True,
            pickup_information_confirmed=True,
        )
        payload = self._base_payload()
        payload.update(
            {
                "arrival_mode": OrderInboundArrivalMode.PICKUP_REQUESTED,
                "declared_pallet_count": "1",
                "pickup_address_book_entry_id": str(address_entry.id),
                "pickup_available_from_date": "2026-04-20",
                "pickup_information_confirmed": "1",
            }
        )

        with mock.patch("wms.views_portal_orders.send_portal_order_notifications"):
            response = self.client.post(self.order_create_url, payload)

        self.assertEqual(response.status_code, 302)
        order = Order.objects.filter(association_contact=self.profile.contact).latest("id")
        self.assertEqual(order.inbound_delivery.pickup_address_book_entry_id, address_entry.id)
        self.assertEqual(order.inbound_delivery.pickup_contact_name, "Alice")
        self.assertEqual(order.inbound_delivery.pickup_address_line1, "12 Rue Logistique")
