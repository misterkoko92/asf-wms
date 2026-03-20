from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from contacts.correspondent_recipient_promotion import SUPPORT_ORGANIZATION_NAME
from contacts.models import Contact, ContactType
from wms.contact_labels import (
    build_contact_select_label,
    build_shipment_recipient_select_label,
)
from wms.models import Destination, Shipment, ShipmentStatus
from wms.planning.sources import build_correspondent_reference, build_shipper_reference
from wms.print_context import build_shipment_document_context
from wms.shipment_party_snapshot import build_shipment_party_snapshot
from wms.shipment_view_helpers import build_shipments_ready_rows, build_shipments_tracking_rows


class _FakeFiltered:
    def __init__(self, count):
        self._count = count

    def count(self):
        return self._count


class _FakeReadyCartonSet:
    def __init__(self, total, ready):
        self._total = total
        self._ready = ready

    def count(self):
        return self._total

    def filter(self, **_kwargs):
        return _FakeFiltered(self._ready)


class _FakeTrackingCartonSet:
    def __init__(self, total):
        self._total = total

    def count(self):
        return self._total


class _FakePrintCartonSet:
    def __init__(self, cartons):
        self._cartons = cartons

    def all(self):
        return SimpleNamespace(order_by=lambda *_args: self._cartons)


class ShipmentPartyLabelFormattingTests(SimpleTestCase):
    def test_build_contact_select_label_formats_referent_before_structure(self):
        organization = SimpleNamespace(name="Association Test")
        contact = SimpleNamespace(
            contact_type=ContactType.PERSON,
            title="M.",
            first_name="Jean",
            last_name="Dupont",
            name="Jean Dupont",
            organization=organization,
        )

        label = build_contact_select_label(contact)

        self.assertEqual(label, "M. Jean DUPONT, Association Test")

    def test_build_shipment_recipient_select_label_formats_support_correspondent_with_iata(self):
        organization = SimpleNamespace(name=SUPPORT_ORGANIZATION_NAME)
        contact = SimpleNamespace(
            contact_type=ContactType.PERSON,
            title="",
            first_name="Christian",
            last_name="Limbio",
            name="Christian Limbio",
            organization=organization,
        )
        destination = SimpleNamespace(iata_code="BGF")

        label = build_shipment_recipient_select_label(contact, destination=destination)

        self.assertEqual(label, "Christian LIMBIO, ASF - CORRESPONDANT - BGF")


class ShipmentPartyLabelReadersTests(SimpleTestCase):
    def test_build_shipments_ready_rows_prefers_snapshot_label(self):
        now = timezone.now()
        shipper_org = SimpleNamespace(name="ORGANISATION RENOMMEE")
        shipper_contact = SimpleNamespace(
            contact_type=ContactType.PERSON,
            title="M.",
            first_name="Jean",
            last_name="Dupont",
            name="Jean Dupont",
            organization=shipper_org,
        )
        recipient_contact = SimpleNamespace(
            contact_type=ContactType.PERSON,
            title="Mme",
            first_name="Alice",
            last_name="Martin",
            name="Alice Martin",
            organization=SimpleNamespace(name="Hopital Renomme"),
        )
        shipment = SimpleNamespace(
            id=1,
            reference="S-001",
            tracking_token="token-1",
            carton_count=1,
            ready_count=1,
            carton_set=_FakeReadyCartonSet(total=1, ready=1),
            destination=SimpleNamespace(iata_code="BKO"),
            shipper_name="Fallback Sender",
            shipper_contact_ref=shipper_contact,
            recipient_name="Fallback Recipient",
            recipient_contact_ref=recipient_contact,
            party_snapshot={
                "shipper": {"label": "M. Jean DUPONT, Association Test"},
                "recipient": {"label": "Mme Alice MARTIN, Hopital Bamako"},
            },
            created_at=now,
            ready_at=now,
            status=ShipmentStatus.PACKED,
        )

        with mock.patch(
            "wms.shipment_view_helpers.ShipmentUnitEquivalenceRule.objects.filter",
            return_value=SimpleNamespace(select_related=lambda *_args: []),
        ):
            rows = build_shipments_ready_rows([shipment])

        self.assertEqual(rows[0]["shipper_name"], "M. Jean DUPONT, Association Test")
        self.assertEqual(rows[0]["recipient_name"], "Mme Alice MARTIN, Hopital Bamako")

    def test_build_shipments_tracking_rows_formats_live_contact_label_without_snapshot(self):
        now = timezone.now()
        shipper_contact = SimpleNamespace(
            contact_type=ContactType.PERSON,
            title="M.",
            first_name="Jean",
            last_name="Dupont",
            name="Jean Dupont",
            organization=SimpleNamespace(name="Association Test"),
        )
        recipient_contact = SimpleNamespace(
            contact_type=ContactType.PERSON,
            title="Dr",
            first_name="Alice",
            last_name="Martin",
            name="Alice Martin",
            organization=SimpleNamespace(name="Hopital Bamako"),
        )
        shipment = SimpleNamespace(
            id=21,
            reference="S-021",
            tracking_token="token-21",
            carton_count=2,
            carton_set=_FakeTrackingCartonSet(2),
            shipper_name="Fallback Sender",
            shipper_contact_ref=shipper_contact,
            recipient_name="Fallback Recipient",
            recipient_contact_ref=recipient_contact,
            party_snapshot={},
            planned_at=now,
            boarding_ok_at=now,
            shipped_tracking_at=now,
            received_correspondent_at=now,
            delivered_at=now,
            status=ShipmentStatus.DELIVERED,
            is_disputed=False,
            closed_at=None,
            closed_by=None,
        )

        rows = build_shipments_tracking_rows([shipment])

        self.assertEqual(rows[0]["shipper_name"], "M. Jean DUPONT, Association Test")
        self.assertEqual(rows[0]["recipient_name"], "Dr Alice MARTIN, Hopital Bamako")

    def test_build_shipment_document_context_prefers_snapshot_labels(self):
        cartons = [SimpleNamespace(id=10)]
        shipment = SimpleNamespace(
            reference="SHP-10",
            shipper_name="Legacy shipper",
            shipper_contact="Legacy shipper",
            shipper_contact_ref=None,
            recipient_name="Legacy recipient",
            recipient_contact="Legacy recipient",
            recipient_contact_ref=None,
            correspondent_name="Legacy correspondent",
            correspondent_contact_ref=None,
            party_snapshot={
                "shipper": {
                    "label": "M. Jean DUPONT, Association Test",
                    "contact_label": "M. Jean DUPONT",
                    "organization_label": "Association Test",
                    "contact": {
                        "notification_emails": ["jean@example.com"],
                        "phone": "+33 1 00 00 00 00",
                    },
                    "organization": {"notification_emails": ["ops@example.com"]},
                },
                "recipient": {
                    "label": "Dr Alice MARTIN, Hopital Bamako",
                    "contact_label": "Dr Alice MARTIN",
                    "organization_label": "Hopital Bamako",
                    "contact": {},
                    "organization": {},
                },
                "correspondent": {
                    "label": "M. Ibrahima KEITA, ASF - CORRESPONDANT",
                    "contact_label": "M. Ibrahima KEITA",
                    "organization_label": "ASF - CORRESPONDANT",
                    "contact": {},
                    "organization": {},
                },
            },
            destination=SimpleNamespace(city="Paris", iata_code="CDG"),
            destination_address="Fallback Address",
            destination_country="France",
            requested_delivery_date=None,
            notes="",
            carton_set=_FakePrintCartonSet(cartons),
        )
        carton_items_qs = mock.MagicMock()
        carton_items_qs.select_related.return_value = []

        with mock.patch("wms.print_context.build_shipment_item_rows", return_value=[]):
            with mock.patch("wms.print_context.build_shipment_aggregate_rows", return_value=[]):
                with mock.patch(
                    "wms.print_context.CartonFormat.objects.filter",
                    return_value=SimpleNamespace(first=lambda: None),
                ):
                    with mock.patch(
                        "wms.print_context.CartonFormat.objects.first",
                        return_value=SimpleNamespace(id=1),
                    ):
                        with mock.patch("wms.print_context.build_carton_rows", return_value=[]):
                            with mock.patch(
                                "wms.print_context.CartonItem.objects.filter",
                                return_value=carton_items_qs,
                            ):
                                with mock.patch(
                                    "wms.print_context.compute_weight_total_g",
                                    return_value=0,
                                ):
                                    with mock.patch(
                                        "wms.print_context.build_shipment_type_labels",
                                        return_value="",
                                    ):
                                        with mock.patch(
                                            "wms.print_context.build_contact_info",
                                            side_effect=lambda _contact, fallback_name: {
                                                "name": fallback_name,
                                                "person": fallback_name,
                                                "company": fallback_name,
                                                "address": "",
                                                "phone": "",
                                                "email": "",
                                            },
                                        ):
                                            with mock.patch(
                                                "wms.print_context.build_org_context",
                                                return_value={},
                                            ):
                                                context = build_shipment_document_context(
                                                    shipment,
                                                    "shipment_note",
                                                )

        self.assertEqual(
            context["shipper_info"]["name"],
            "M. Jean DUPONT, Association Test",
        )
        self.assertEqual(context["shipper_info"]["person"], "M. Jean DUPONT")
        self.assertEqual(context["shipper_info"]["company"], "Association Test")
        self.assertEqual(
            context["recipient_info"]["name"],
            "Dr Alice MARTIN, Hopital Bamako",
        )
        self.assertEqual(
            context["correspondent_info"]["name"],
            "M. Ibrahima KEITA, ASF - CORRESPONDANT",
        )


class ShipmentPartyPlanningReferencesTests(TestCase):
    def _create_org(self, name, *, email=""):
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            email=email,
            is_active=True,
        )

    def _create_person(self, first_name, last_name, *, organization, email="", title=""):
        full_name = f"{first_name} {last_name}".strip()
        return Contact.objects.create(
            name=full_name,
            contact_type=ContactType.PERSON,
            first_name=first_name,
            last_name=last_name,
            title=title,
            organization=organization,
            email=email,
            is_active=True,
        )

    def test_build_shipper_reference_prefers_snapshot_label_and_org_identity(self):
        shipper_org = self._create_org("Association Snapshot", email="org@example.com")
        shipper_contact = self._create_person(
            "Jean",
            "Dupont",
            organization=shipper_org,
            email="jean@example.com",
            title="M.",
        )
        snapshot = build_shipment_party_snapshot(
            shipper_contact=shipper_contact,
            recipient_contact=None,
            correspondent_contact=None,
            shipper_name=shipper_contact.name,
        )
        shipment = Shipment.objects.create(
            shipper_name=shipper_contact.name,
            shipper_contact_ref=shipper_contact,
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            party_snapshot=snapshot,
        )
        shipper_org.name = "Association Renommee"
        shipper_org.save(update_fields=["name"])

        reference = build_shipper_reference(shipment)

        self.assertEqual(reference["contact_id"], shipper_org.id)
        self.assertEqual(reference["contact_name"], "M. Jean DUPONT, Association Snapshot")

    def test_build_correspondent_reference_prefers_snapshot_label_over_destination_contact(self):
        old_org = self._create_org("ASF - CORRESPONDANT", email="old@example.com")
        old_contact = self._create_person(
            "Ibrahima",
            "Keita",
            organization=old_org,
            email="ibrahima@example.com",
            title="M.",
        )
        destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="ML",
            correspondent_contact=old_contact,
            is_active=True,
        )
        snapshot = build_shipment_party_snapshot(
            shipper_contact=None,
            recipient_contact=None,
            correspondent_contact=old_contact,
            correspondent_name=old_contact.name,
        )
        shipment = Shipment.objects.create(
            shipper_name="Shipper",
            recipient_name="Recipient",
            correspondent_name=old_contact.name,
            destination=destination,
            destination_address="Airport Road",
            destination_country="Mali",
            party_snapshot=snapshot,
        )
        new_org = self._create_org("Autre Correspondant", email="new@example.com")
        new_contact = self._create_person(
            "Amadou",
            "Diallo",
            organization=new_org,
            email="amadou@example.com",
            title="M.",
        )
        destination.correspondent_contact = new_contact
        destination.save(update_fields=["correspondent_contact"])

        reference = build_correspondent_reference(shipment)

        self.assertEqual(reference["contact_id"], old_org.id)
        self.assertEqual(reference["contact_name"], "M. Ibrahima KEITA, ASF - CORRESPONDANT")
