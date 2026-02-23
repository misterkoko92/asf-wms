from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from contacts.models import Contact, ContactTag, ContactType
from wms.carton_status_events import set_carton_status
from wms.models import (
    AssociationContactTitle,
    AssociationProfile,
    CartonStatus,
    Destination,
    Location,
    Product,
    ProductLot,
    ProductLotStatus,
    Shipment,
    ShipmentTrackingStatus,
    Warehouse,
)


class UiApiE2EWorkflowsTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(
            username="ui-e2e-staff",
            password="pass1234",
            is_staff=True,
        )
        self.superuser = user_model.objects.create_user(
            username="ui-e2e-superuser",
            password="pass1234",
            is_staff=True,
            is_superuser=True,
        )
        self.portal_user = user_model.objects.create_user(
            username="ui-e2e-portal",
            password="pass1234",
        )

        self.staff_client = APIClient()
        self.staff_client.force_authenticate(self.staff_user)
        self.superuser_client = APIClient()
        self.superuser_client.force_authenticate(self.superuser)
        self.portal_client = APIClient()
        self.portal_client.force_authenticate(self.portal_user)

        self.association_contact = Contact.objects.create(
            name="Association E2E",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        AssociationProfile.objects.create(
            user=self.portal_user,
            contact=self.association_contact,
        )

        warehouse = Warehouse.objects.create(name="E2E WH", code="E2E")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.product = Product.objects.create(
            sku="UI-E2E-001",
            name="UI E2E Product",
            brand="Medi",
            default_location=location,
            is_active=True,
            qr_code_image="qr_codes/test.png",
        )
        ProductLot.objects.create(
            product=self.product,
            lot_code="LOT-E2E-BASE",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=50,
            quantity_reserved=0,
            location=location,
        )

        self.correspondent_contact = self._create_contact(
            "E2E Correspondent",
            tags=["correspondant"],
            contact_type=ContactType.PERSON,
        )
        self.destination = Destination.objects.create(
            city="RUN",
            iata_code="RUN",
            country="France",
            correspondent_contact=self.correspondent_contact,
            is_active=True,
        )
        self.correspondent_contact.destinations.add(self.destination)

        self.shipper_contact = self._create_contact("E2E Shipper", tags=["expediteur"])
        self.shipper_contact.destinations.add(self.destination)
        self.recipient_contact = self._create_contact("E2E Recipient", tags=["destinataire"])
        self.recipient_contact.destinations.add(self.destination)
        self.donor_contact = self._create_contact("E2E Donor", tags=["donateur"])

    def _create_contact(self, name, *, tags, contact_type=ContactType.ORGANIZATION):
        contact = Contact.objects.create(
            name=name,
            contact_type=contact_type,
            is_active=True,
        )
        for tag_name in tags:
            tag, _ = ContactTag.objects.get_or_create(name=tag_name)
            contact.tags.add(tag)
        return contact

    def _post_tracking(self, shipment_id, status_value):
        return self.staff_client.post(
            f"/api/v1/ui/shipments/{shipment_id}/tracking-events/",
            {
                "status": status_value,
                "actor_name": "E2E Ops",
                "actor_structure": "ASF",
                "comments": f"Transition {status_value}",
            },
            format="json",
        )

    def test_e2e_scan_workflow_stock_to_close_with_docs_labels_templates(self):
        stock_update = self.staff_client.post(
            "/api/v1/ui/stock/update/",
            {
                "product_code": self.product.sku,
                "quantity": 6,
                "expires_on": "2027-12-31",
                "lot_code": "LOT-E2E-NEW",
                "donor_contact_id": self.donor_contact.id,
            },
            format="json",
        )
        self.assertEqual(stock_update.status_code, 201)

        create_shipment = self.staff_client.post(
            "/api/v1/ui/shipments/",
            {
                "destination": self.destination.id,
                "shipper_contact": self.shipper_contact.id,
                "recipient_contact": self.recipient_contact.id,
                "correspondent_contact": self.correspondent_contact.id,
                "lines": [{"product_code": self.product.sku, "quantity": 2}],
            },
            format="json",
        )
        self.assertEqual(create_shipment.status_code, 201)
        shipment_id = create_shipment.json()["shipment"]["id"]
        shipment = Shipment.objects.get(pk=shipment_id)

        for carton in shipment.carton_set.all():
            set_carton_status(
                carton=carton,
                new_status=CartonStatus.LABELED,
                reason="e2e_label_ready",
                user=self.staff_user,
            )

        for tracking_status in (
            ShipmentTrackingStatus.PLANNING_OK,
            ShipmentTrackingStatus.PLANNED,
            ShipmentTrackingStatus.BOARDING_OK,
            ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            ShipmentTrackingStatus.RECEIVED_RECIPIENT,
        ):
            tracking_response = self._post_tracking(shipment_id, tracking_status)
            self.assertEqual(
                tracking_response.status_code,
                201,
                msg=f"failed transition: {tracking_status}",
            )

        docs_list = self.staff_client.get(f"/api/v1/ui/shipments/{shipment_id}/documents/")
        self.assertEqual(docs_list.status_code, 200)

        upload_response = self.staff_client.post(
            f"/api/v1/ui/shipments/{shipment_id}/documents/",
            {
                "document_file": SimpleUploadedFile(
                    "e2e-proof.pdf",
                    b"%PDF-1.4 e2e",
                    content_type="application/pdf",
                )
            },
            format="multipart",
        )
        self.assertEqual(upload_response.status_code, 201)

        labels_response = self.staff_client.get(f"/api/v1/ui/shipments/{shipment_id}/labels/")
        self.assertEqual(labels_response.status_code, 200)
        self.assertGreaterEqual(len(labels_response.json()["labels"]), 1)

        close_response = self.staff_client.post(
            f"/api/v1/ui/shipments/{shipment_id}/close/",
            {},
            format="json",
        )
        self.assertEqual(close_response.status_code, 200)
        shipment.refresh_from_db()
        self.assertIsNotNone(shipment.closed_at)

        list_templates = self.superuser_client.get("/api/v1/ui/templates/")
        self.assertEqual(list_templates.status_code, 200)
        patch_template = self.superuser_client.patch(
            "/api/v1/ui/templates/shipment_note/",
            {
                "action": "save",
                "layout": {"blocks": [{"id": "e2e-note", "type": "text"}]},
            },
            format="json",
        )
        self.assertEqual(patch_template.status_code, 200)
        self.assertTrue(patch_template.json()["ok"])

    def test_e2e_portal_workflow_recipients_account_and_order(self):
        recipient_create = self.portal_client.post(
            "/api/v1/ui/portal/recipients/",
            {
                "destination_id": self.destination.id,
                "structure_name": "Hopital E2E",
                "contact_title": AssociationContactTitle.MR,
                "contact_last_name": "Martin",
                "contact_first_name": "Luc",
                "phones": "0102030405",
                "emails": "luc.martin@example.org",
                "address_line1": "5 Rue E2E",
                "postal_code": "75001",
                "city": "Paris",
                "country": "France",
                "notify_deliveries": True,
                "is_delivery_contact": True,
            },
            format="json",
        )
        self.assertEqual(recipient_create.status_code, 201)
        recipient_id = recipient_create.json()["recipient"]["id"]

        order_create = self.portal_client.post(
            "/api/v1/ui/portal/orders/",
            {
                "destination_id": self.destination.id,
                "recipient_id": str(recipient_id),
                "notes": "Commande E2E",
                "lines": [{"product_id": self.product.id, "quantity": 1}],
            },
            format="json",
        )
        self.assertEqual(order_create.status_code, 201)
        self.assertTrue(order_create.json()["ok"])

        recipient_patch = self.portal_client.patch(
            f"/api/v1/ui/portal/recipients/{recipient_id}/",
            {
                "destination_id": self.destination.id,
                "structure_name": "Hopital E2E Updated",
                "contact_title": AssociationContactTitle.MRS,
                "contact_last_name": "Martin",
                "contact_first_name": "Lucie",
                "phones": "0102030406",
                "emails": "lucie.martin@example.org",
                "address_line1": "6 Rue E2E",
                "postal_code": "75002",
                "city": "Paris",
                "country": "France",
                "notify_deliveries": True,
                "is_delivery_contact": False,
            },
            format="json",
        )
        self.assertEqual(recipient_patch.status_code, 200)

        account_patch = self.portal_client.patch(
            "/api/v1/ui/portal/account/",
            {
                "association_name": "Association E2E Updated",
                "association_email": "association.e2e@example.org",
                "association_phone": "0203040506",
                "address_line1": "10 Rue Assoc E2E",
                "address_line2": "",
                "postal_code": "69001",
                "city": "Lyon",
                "country": "France",
                "contacts": [
                    {
                        "title": AssociationContactTitle.MR,
                        "last_name": "Admin",
                        "first_name": "Portal",
                        "phone": "0600000000",
                        "email": "portal.admin@example.org",
                        "is_administrative": True,
                        "is_shipping": False,
                        "is_billing": False,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(account_patch.status_code, 200)
        self.assertEqual(
            account_patch.json()["account"]["association_name"],
            "Association E2E Updated",
        )

        dashboard_response = self.portal_client.get("/api/v1/ui/portal/dashboard/")
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertGreaterEqual(dashboard_response.json()["kpis"]["orders_total"], 1)
