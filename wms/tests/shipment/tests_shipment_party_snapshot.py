from datetime import date
from types import SimpleNamespace
from unittest import mock

from django import forms
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from contacts.models import Contact, ContactType
from wms.domain.orders import create_shipment_for_order
from wms.models import (
    Destination,
    Location,
    Order,
    OrderLine,
    OrderStatus,
    OrganizationRole,
    OrganizationRoleAssignment,
    Product,
    RecipientBinding,
    Shipment,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
    ShipperScope,
    Warehouse,
)
from wms.scan_shipment_handlers import _handle_shipment_save_draft_post


class _DraftForm:
    def __init__(self, *, data, fields):
        self.data = data
        self.fields = fields
        self.errors = []

    def add_error(self, field, error):
        self.errors.append((field, str(error)))


class ShipmentPartySnapshotTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(
            username="snapshot-user",
            password="pass1234",  # pragma: allowlist secret
        )
        self.warehouse = Warehouse.objects.create(name="Snapshot WH", code="SWH")
        self.location = Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.product = Product.objects.create(
            sku="SNAP-001",
            name="Snapshot Product",
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )

    def _create_org(self, name):
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_person(self, first_name, last_name, *, organization=None, title=""):
        full_name = f"{first_name} {last_name}".strip()
        return Contact.objects.create(
            name=full_name,
            contact_type=ContactType.PERSON,
            title=title,
            first_name=first_name,
            last_name=last_name,
            organization=organization,
            is_active=True,
        )

    def _assign_role(self, organization, role):
        assignment, _created = OrganizationRoleAssignment.objects.get_or_create(
            organization=organization,
            role=role,
            defaults={"is_active": True},
        )
        if not assignment.is_active:
            assignment.is_active = True
            assignment.save(update_fields=["is_active"])
        return assignment

    def _grant_shipper_scope(self, shipper_org, destination):
        assignment = self._assign_role(shipper_org, OrganizationRole.SHIPPER)
        ShipperScope.objects.get_or_create(
            role_assignment=assignment,
            destination=destination,
            defaults={"is_active": True},
        )

    def _bind_recipient(self, shipper_org, recipient_org, destination):
        self._assign_role(shipper_org, OrganizationRole.SHIPPER)
        self._assign_role(recipient_org, OrganizationRole.RECIPIENT)
        RecipientBinding.objects.get_or_create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination,
            defaults={"is_active": True},
        )

    def _request(self, data):
        request = self.factory.post("/scan/shipment/", data)
        request.user = self.user
        return request

    def _create_scan_triplet(self, code):
        correspondent_org = self._create_org(f"ASF - CORRESPONDANT {code}")
        correspondent = self._create_person(
            "Ibrahima",
            code,
            organization=correspondent_org,
            title="M.",
        )
        destination = Destination.objects.create(
            city=f"Ville {code}",
            iata_code=code,
            country="Mali",
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

        shipper_org = self._create_org(f"Association {code}")
        shipper_contact = self._create_person(
            "Jean",
            code,
            organization=shipper_org,
            title="M.",
        )
        shipper = ShipmentShipper.objects.create(
            organization=shipper_org,
            default_contact=shipper_contact,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

        recipient_org_contact = self._create_org(f"Hopital {code}")
        recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=recipient_org_contact,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        recipient_contact = self._create_person(
            "Alice",
            code,
            organization=recipient_org_contact,
            title="Mme",
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

    def test_create_shipment_for_order_persists_snapshot_without_changing_legacy_labels(self):
        shipper_org = self._create_org("Association Shipper")
        shipper_contact = self._create_person(
            "Jean",
            "Dupont",
            organization=shipper_org,
            title="M.",
        )
        recipient_org = self._create_org("Hopital Bamako")
        recipient_contact = self._create_person(
            "Alice",
            "Martin",
            organization=recipient_org,
            title="Mme",
        )
        correspondent_org = self._create_org("ASF - CORRESPONDANT")
        correspondent_contact = self._create_person(
            "Ibrahima",
            "Keita",
            organization=correspondent_org,
            title="M.",
        )
        destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=correspondent_contact,
            is_active=True,
        )
        self._grant_shipper_scope(shipper_org, destination)
        self._bind_recipient(shipper_org, recipient_org, destination)
        order = Order.objects.create(
            status=OrderStatus.DRAFT,
            shipper_name=shipper_contact.name,
            shipper_contact=shipper_contact,
            recipient_name=recipient_contact.name,
            recipient_contact=recipient_contact,
            correspondent_name=correspondent_contact.name,
            correspondent_contact=correspondent_contact,
            destination_address="Legacy Address",
            destination_city="Bamako",
            destination_country="Mali",
            requested_delivery_date=date(2026, 4, 10),
            created_by=self.user,
        )
        OrderLine.objects.create(order=order, product=self.product, quantity=1)

        shipment = create_shipment_for_order(order=order)

        self.assertEqual(shipment.shipper_name, "Jean Dupont")
        self.assertEqual(shipment.shipper_contact, "Jean Dupont")
        self.assertEqual(shipment.recipient_name, "Alice Martin")
        self.assertEqual(shipment.recipient_contact, "Alice Martin")
        self.assertEqual(shipment.correspondent_name, "Ibrahima Keita")
        self.assertEqual(
            shipment.party_snapshot["shipper"]["label"],
            "M. Jean DUPONT, Association Shipper",
        )
        self.assertEqual(
            shipment.party_snapshot["recipient"]["organization"]["contact_id"],
            recipient_org.id,
        )
        self.assertEqual(
            shipment.party_snapshot["correspondent"]["contact"]["contact_id"],
            correspondent_contact.id,
        )

        shipper_org.name = "Association Updated"
        shipper_org.save(update_fields=["name"])
        shipper_contact.first_name = "Marc"
        shipper_contact.last_name = "Changed"
        shipper_contact.name = "Marc Changed"
        shipper_contact.save(update_fields=["first_name", "last_name", "name"])
        recipient_org.name = "Hopital Updated"
        recipient_org.save(update_fields=["name"])
        recipient_contact.first_name = "Claire"
        recipient_contact.last_name = "Durand"
        recipient_contact.name = "Claire Durand"
        recipient_contact.save(update_fields=["first_name", "last_name", "name"])

        shipment.refresh_from_db()

        self.assertEqual(shipment.shipper_name, "Jean Dupont")
        self.assertEqual(shipment.shipper_contact, "Jean Dupont")
        self.assertEqual(shipment.recipient_name, "Alice Martin")
        self.assertEqual(shipment.recipient_contact, "Alice Martin")
        self.assertEqual(
            shipment.party_snapshot["shipper"]["label"],
            "M. Jean DUPONT, Association Shipper",
        )
        self.assertEqual(
            shipment.party_snapshot["recipient"]["label"],
            "Mme Alice MARTIN, Hopital Bamako",
        )

    def test_create_shipment_for_order_backfills_snapshot_on_existing_shipment(self):
        shipper_org = self._create_org("Association Existing")
        shipper_contact = self._create_person(
            "Jean",
            "Existing",
            organization=shipper_org,
            title="M.",
        )
        recipient_org = self._create_org("Hopital Existing")
        recipient_contact = self._create_person(
            "Alice",
            "Existing",
            organization=recipient_org,
            title="Mme",
        )
        correspondent_org = self._create_org("ASF - CORRESPONDANT Existing")
        correspondent_contact = self._create_person(
            "Ibrahima",
            "Existing",
            organization=correspondent_org,
            title="M.",
        )
        destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="Cote d'Ivoire",
            correspondent_contact=correspondent_contact,
            is_active=True,
        )
        self._grant_shipper_scope(shipper_org, destination)
        self._bind_recipient(shipper_org, recipient_org, destination)
        existing_shipment = Shipment.objects.create(
            shipper_name="Legacy shipper",
            recipient_name="Legacy recipient",
            correspondent_name="Legacy correspondent",
            destination_address="Legacy address",
            destination_country="France",
            created_by=self.user,
        )
        order = Order.objects.create(
            status=OrderStatus.DRAFT,
            shipper_name=shipper_contact.name,
            shipper_contact=shipper_contact,
            recipient_name=recipient_contact.name,
            recipient_contact=recipient_contact,
            correspondent_name=correspondent_contact.name,
            correspondent_contact=correspondent_contact,
            destination_address="Legacy Address",
            destination_city="Abidjan",
            destination_country="Cote d'Ivoire",
            shipment=existing_shipment,
            created_by=self.user,
        )
        OrderLine.objects.create(order=order, product=self.product, quantity=1)

        shipment = create_shipment_for_order(order=order)
        shipment.refresh_from_db()

        self.assertEqual(shipment.id, existing_shipment.id)
        self.assertEqual(shipment.shipper_name, "Legacy shipper")
        self.assertEqual(
            shipment.party_snapshot["shipper"]["label"],
            "M. Jean EXISTING, Association Existing",
        )
        self.assertEqual(shipment.shipper_contact_ref_id, shipper_contact.id)
        self.assertEqual(shipment.recipient_contact_ref_id, recipient_contact.id)
        self.assertEqual(shipment.correspondent_contact_ref_id, correspondent_contact.id)

    def test_save_draft_scan_persists_snapshot_and_frozen_labels(self):
        destination, shipper_contact, recipient_contact, correspondent = self._create_scan_triplet(
            "SNP"
        )
        request = self._request(
            {
                "destination": str(destination.id),
                "shipper_contact": str(shipper_contact.id),
                "recipient_contact": str(recipient_contact.id),
                "correspondent_contact": "",
            }
        )
        form = _DraftForm(
            data=request.POST,
            fields={
                "destination": forms.ModelChoiceField(
                    queryset=Destination.objects.filter(pk=destination.pk)
                ),
                "shipper_contact": forms.ModelChoiceField(
                    queryset=Contact.objects.filter(pk=shipper_contact.pk),
                    required=False,
                ),
                "recipient_contact": forms.ModelChoiceField(
                    queryset=Contact.objects.filter(pk=recipient_contact.pk),
                    required=False,
                ),
                "correspondent_contact": forms.ModelChoiceField(
                    queryset=Contact.objects.none(),
                    required=False,
                ),
            },
        )

        with mock.patch("wms.scan_shipment_handlers.messages.success"):
            with mock.patch(
                "wms.scan_shipment_handlers.redirect",
                return_value=SimpleNamespace(status_code=302, url="/draft/1"),
            ):
                response = _handle_shipment_save_draft_post(request, form=form)

        shipment = Shipment.objects.get(reference__startswith="EXP-TEMP-")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(shipment.shipper_name, "Jean SNP")
        self.assertEqual(shipment.recipient_name, "Alice SNP")
        self.assertEqual(shipment.correspondent_name, "Ibrahima SNP")
        self.assertEqual(
            shipment.party_snapshot["shipper"]["label"],
            "M. Jean SNP, Association SNP",
        )
        self.assertEqual(
            shipment.party_snapshot["recipient"]["contact"]["contact_id"],
            recipient_contact.id,
        )
        self.assertEqual(
            shipment.party_snapshot["correspondent"]["organization"]["contact_id"],
            correspondent.organization_id,
        )
