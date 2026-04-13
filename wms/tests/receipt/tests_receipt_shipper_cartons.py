from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import Carton, CartonSourceKind, CartonStatus, Receipt, Warehouse


class ReceiptShipperCartonsTests(TestCase):
    def setUp(self):
        self.shipper = Contact.objects.create(
            name="Receipt Shipper",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.warehouse = Warehouse.objects.create(name="Receipt WH", code="RWH")
        self.receipt = Receipt.objects.create(
            warehouse=self.warehouse,
            source_contact=self.shipper,
        )

    def test_shipper_received_carton_keeps_receipt_provenance(self):
        carton = Carton.objects.create(
            code="SHIPPER-CARTON-001",
            status=CartonStatus.PACKED,
            source_kind=CartonSourceKind.SHIPPER_RECEIVED,
            source_receipt=self.receipt,
        )

        self.assertEqual(carton.source_receipt_id, self.receipt.id)
        self.assertEqual(carton.source_kind, CartonSourceKind.SHIPPER_RECEIVED)
