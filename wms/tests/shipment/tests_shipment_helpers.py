from django.test import TestCase

from contacts.models import Contact, ContactAddress, ContactType
from wms.models import (
    Destination,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from wms.shipment_helpers import (
    build_destination_label,
    build_shipment_contact_payload,
    parse_shipment_lines,
)


class ShipmentHelpersTests(TestCase):
    def _create_organization(self, name):
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_person(self, name, *, organization):
        first_name, _, last_name = name.partition(" ")
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.PERSON,
            first_name=first_name,
            last_name=last_name or first_name,
            organization=organization,
            is_active=True,
        )

    def _create_destination_with_correspondent(self, code):
        correspondent_org = self._create_organization(f"Correspondant {code}")
        correspondent = self._create_person(f"Corr {code}", organization=correspondent_org)
        destination = Destination.objects.create(
            city=f"Ville {code}",
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
        return destination, correspondent

    def _create_shipper(self, name, *, can_send_to_all=False):
        organization = self._create_organization(name)
        default_contact = self._create_person(f"Jean {name}", organization=organization)
        shipper = ShipmentShipper.objects.create(
            organization=organization,
            default_contact=default_contact,
            validation_status=ShipmentValidationStatus.VALIDATED,
            can_send_to_all=can_send_to_all,
            is_active=True,
        )
        return shipper, default_contact

    def _create_linked_recipient_contact(
        self,
        *,
        shipper,
        destination,
        recipient_name,
        referent_name,
        is_default=True,
    ):
        organization = self._create_organization(recipient_name)
        ContactAddress.objects.create(
            contact=organization,
            address_line1=f"{recipient_name} addr",
            country="France",
            is_default=True,
        )
        recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=organization,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        contact = self._create_person(referent_name, organization=organization)
        recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_org,
            contact=contact,
            is_active=True,
        )
        link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient_org,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=recipient_contact,
            is_default=is_default,
            is_active=True,
        )
        return contact, recipient_org, link

    def test_build_destination_label_returns_empty_for_missing_destination(self):
        self.assertEqual(build_destination_label(None), "")

    def test_build_destination_label_uses_destination_string(self):
        destination, _correspondent = self._create_destination_with_correspondent("PAR")

        self.assertEqual(build_destination_label(destination), str(destination))

    def test_build_shipment_contact_payload_collects_shipment_party_contacts(self):
        destination, correspondent = self._create_destination_with_correspondent("ABJ")
        shipper, shipper_contact = self._create_shipper("ASF")
        recipient_contact, recipient_org, _link = self._create_linked_recipient_contact(
            shipper=shipper,
            destination=destination,
            recipient_name="Hopital Abidjan",
            referent_name="Alice Martin",
        )

        (
            destinations_json,
            shippers_json,
            recipients_json,
            correspondents_json,
        ) = build_shipment_contact_payload()

        self.assertEqual(
            destinations_json,
            [
                {
                    "id": destination.id,
                    "label": str(destination),
                    "city": destination.city,
                    "iata_code": destination.iata_code,
                    "country": destination.country,
                    "correspondent_contact_id": correspondent.id,
                }
            ],
        )
        self.assertEqual(
            shippers_json,
            [
                {
                    "id": shipper_contact.id,
                    "name": "ASF (Jean, ASF)",
                    "is_priority_shipper": False,
                    "organization_id": shipper.organization_id,
                    "default_destination_id": destination.id,
                    "allowed_destination_ids": [destination.id],
                    "scope_destination_ids": [destination.id],
                }
            ],
        )
        self.assertEqual(
            recipients_json,
            [
                {
                    "id": recipient_contact.id,
                    "name": "Hopital Abidjan (Alice, MARTIN)",
                    "organization_id": recipient_org.organization_id,
                    "countries": ["France"],
                    "default_destination_id": destination.id,
                    "allowed_destination_ids": [destination.id],
                    "bound_shipper_ids": [shipper.organization_id],
                    "binding_pairs": [
                        {
                            "shipper_id": shipper.organization_id,
                            "destination_id": destination.id,
                        }
                    ],
                }
            ],
        )
        self.assertEqual(
            correspondents_json,
            [
                {
                    "id": correspondent.id,
                    "name": correspondent.name,
                    "default_destination_id": destination.id,
                    "covered_destination_ids": [destination.id],
                    "recipient_labels_by_destination_id": {
                        str(destination.id): f"Correspondant ABJ (Corr, ABJ)"
                    },
                }
            ],
        )

    def test_build_shipment_contact_payload_reuses_same_recipient_contact_for_multiple_shippers(
        self,
    ):
        destination, _correspondent = self._create_destination_with_correspondent("BKO")
        shipper_a, _ = self._create_shipper("ASF")
        shipper_b, _ = self._create_shipper("MSF")
        organization = self._create_organization("Hopital Bamako")
        ContactAddress.objects.create(
            contact=organization,
            address_line1="Hopital Bamako addr",
            country="Mali",
            is_default=True,
        )
        recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=organization,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        shared_contact = self._create_person("Docteur Truc", organization=organization)
        shipment_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_org,
            contact=shared_contact,
            is_active=True,
        )
        for shipper in (shipper_a, shipper_b):
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

        _destinations_json, _shippers_json, recipients_json, _correspondents_json = (
            build_shipment_contact_payload()
        )

        self.assertEqual(len(recipients_json), 1)
        self.assertEqual(
            recipients_json[0]["bound_shipper_ids"],
            sorted([shipper_a.organization_id, shipper_b.organization_id]),
        )
        self.assertEqual(
            recipients_json[0]["binding_pairs"],
            [
                {
                    "shipper_id": shipper_a.organization_id,
                    "destination_id": destination.id,
                },
                {
                    "shipper_id": shipper_b.organization_id,
                    "destination_id": destination.id,
                },
            ],
        )

    def test_build_shipment_contact_payload_marks_exact_asf_shipper_as_priority(self):
        destination, _correspondent = self._create_destination_with_correspondent("CMN")
        asf_shipper, _ = self._create_shipper("AVIATION SANS FRONTIERES", can_send_to_all=True)
        regional_shipper, _ = self._create_shipper("AVIATION SANS FRONTIERES SUD")
        self._create_linked_recipient_contact(
            shipper=regional_shipper,
            destination=destination,
            recipient_name="Hopital Casablanca",
            referent_name="Youssef Contact",
        )

        _destinations_json, shippers_json, _recipients_json, _correspondents_json = (
            build_shipment_contact_payload()
        )

        priority_flags = {
            entry["organization_id"]: entry["is_priority_shipper"] for entry in shippers_json
        }
        self.assertTrue(priority_flags[asf_shipper.organization_id])
        self.assertFalse(priority_flags[regional_shipper.organization_id])

    def test_parse_shipment_lines_accepts_valid_carton_and_product_lines(self):
        product = type("Product", (), {"id": 7, "name": "Produit test"})()

        line_values, line_items, line_errors = parse_shipment_lines(
            carton_count=2,
            data={
                "line_1_carton_id": "12",
                "line_2_product_code": "SKU-1",
                "line_2_quantity": "2",
                "line_2_expires_on": "2026-02-01",
            },
            allowed_carton_ids={"12"},
        )

        self.assertEqual(line_values[0]["carton_id"], "12")
        self.assertEqual(line_values[1]["product_code"], "SKU-1")
        self.assertEqual(line_errors, {"2": ["Produit introuvable."]})
        self.assertEqual(
            line_items, [{"carton_id": 12, "preassigned_destination_confirmed": False}]
        )
