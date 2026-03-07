from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.models import Receipt, ReceiptShipmentAllocation, ReceiptType, Shipment, Warehouse


class ReceiptShipmentAllocationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="billing-allocation-user",
            is_staff=True,
        )
        self.client.force_login(self.user)
        self.warehouse = Warehouse.objects.create(name="Allocation", code="ALLOC")

    def _create_contact(self, name):
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_receipt(self, *, association, carton_count=5):
        return Receipt.objects.create(
            receipt_type=ReceiptType.ASSOCIATION,
            source_contact=association,
            carton_count=carton_count,
            warehouse=self.warehouse,
        )

    def _create_shipment(self, *, association, reference):
        return Shipment.objects.create(
            reference=reference,
            shipper_name=association.name,
            shipper_contact_ref=association,
            recipient_name="Recipient",
            destination_address="1 rue de la logistique",
        )

    def test_allocation_allows_one_receipt_to_multiple_shipments(self):
        association = self._create_contact("Association A")
        receipt = self._create_receipt(association=association)
        shipment_a = self._create_shipment(association=association, reference="EXP-ALLOC-01")
        shipment_b = self._create_shipment(association=association, reference="EXP-ALLOC-02")

        ReceiptShipmentAllocation.objects.create(
            receipt=receipt,
            shipment=shipment_a,
            allocated_received_units=10,
            created_by=self.user,
        )
        ReceiptShipmentAllocation.objects.create(
            receipt=receipt,
            shipment=shipment_b,
            allocated_received_units=6,
            created_by=self.user,
        )

        self.assertEqual(receipt.shipment_allocations.count(), 2)
        self.assertEqual(shipment_a.receipt_allocations.get().allocated_received_units, 10)
        self.assertEqual(shipment_b.receipt_allocations.get().allocated_received_units, 6)

    def test_allocation_rejects_receipts_from_different_associations(self):
        association_a = self._create_contact("Association A")
        association_b = self._create_contact("Association B")
        shipment = self._create_shipment(association=association_a, reference="EXP-ALLOC-03")
        receipt_a = self._create_receipt(association=association_a, carton_count=4)
        receipt_b = self._create_receipt(association=association_b, carton_count=7)

        ReceiptShipmentAllocation.objects.create(
            receipt=receipt_a,
            shipment=shipment,
            allocated_received_units=4,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            ReceiptShipmentAllocation.objects.create(
                receipt=receipt_b,
                shipment=shipment,
                allocated_received_units=7,
                created_by=self.user,
            )

    def test_receive_association_page_can_add_allocation_for_selected_receipt(self):
        association = self._create_contact("Association Receipt Page")
        receipt = self._create_receipt(association=association)
        shipment = self._create_shipment(association=association, reference="EXP-ALLOC-04")

        response = self.client.post(
            reverse("scan:scan_receive_association"),
            {
                "action": "add_allocation",
                "receipt_id": receipt.id,
                "shipment": shipment.id,
                "allocated_received_units": 8,
                "note": "First split",
            },
        )

        self.assertEqual(response.status_code, 302)
        allocation = ReceiptShipmentAllocation.objects.get(receipt=receipt, shipment=shipment)
        self.assertEqual(allocation.allocated_received_units, 8)
        self.assertEqual(allocation.note, "First split")

    def test_receive_association_page_displays_selected_receipt_allocations(self):
        association = self._create_contact("Association Summary")
        receipt = self._create_receipt(association=association)
        shipment = self._create_shipment(association=association, reference="EXP-ALLOC-05")
        ReceiptShipmentAllocation.objects.create(
            receipt=receipt,
            shipment=shipment,
            allocated_received_units=9,
            note="Receipt summary",
            created_by=self.user,
        )

        response = self.client.get(
            reverse("scan:scan_receive_association"),
            {"receipt_id": receipt.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, receipt.reference)
        self.assertContains(response, shipment.reference)
        self.assertContains(response, "Receipt summary")

    def test_shipment_edit_page_displays_allocation_metadata(self):
        association = self._create_contact("Association Shipment Page")
        receipt = self._create_receipt(association=association)
        shipment = self._create_shipment(association=association, reference="EXP-ALLOC-06")
        ReceiptShipmentAllocation.objects.create(
            receipt=receipt,
            shipment=shipment,
            allocated_received_units=11,
            note="Shipment summary",
            created_by=self.user,
        )

        response = self.client.get(reverse("scan:scan_shipment_edit", args=[shipment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, receipt.reference)
        self.assertContains(response, "11")
        self.assertContains(response, "Shipment summary")
