from django.test import TestCase

from contacts.models import Contact, ContactAddress, ContactTag, ContactType
from wms.models import (
    Destination,
    OrganizationRole,
    OrganizationRoleAssignment,
    Product,
    RecipientBinding,
    ShipperScope,
)
from wms.shipment_helpers import (
    build_destination_label,
    build_shipment_contact_payload,
    parse_shipment_lines,
)


class ShipmentHelpersTests(TestCase):
    def test_build_destination_label_returns_empty_for_missing_destination(self):
        self.assertEqual(build_destination_label(None), "")

    def test_build_destination_label_uses_destination_string(self):
        correspondent = Contact.objects.create(name="Correspondent")
        destination = Destination.objects.create(
            city="Paris",
            iata_code="PAR",
            country="France",
            correspondent_contact=correspondent,
        )
        self.assertEqual(build_destination_label(destination), str(destination))

    def test_build_shipment_contact_payload_collects_destination_scoped_contacts(self):
        correspondent = Contact.objects.create(name="Corr A")
        destination = Destination.objects.create(
            city="Lyon",
            iata_code="LYS",
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper = Contact.objects.create(
            name="Shipper Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper.destinations.add(destination)
        shipper_tag = ContactTag.objects.create(name="expediteur")
        shipper.tags.add(shipper_tag)
        recipient = Contact.objects.create(
            name="Recipient Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient.destinations.add(destination)
        ContactAddress.objects.create(
            contact=recipient,
            address_line1="1 Rue Test",
            city="Lyon",
            country="France",
            is_default=True,
        )
        ContactAddress.objects.create(
            contact=recipient,
            address_line1="2 Main St",
            city="London",
            country="UK",
            is_default=False,
        )
        recipient_tag = ContactTag.objects.create(name="destinataire")
        recipient.tags.add(recipient_tag)

        corr_contact = Contact.objects.create(
            name="Corr Contact",
            is_active=True,
        )
        corr_contact.destinations.add(destination)
        correspondent_tag = ContactTag.objects.create(name="correspondant")
        corr_contact.tags.add(correspondent_tag)

        (
            destinations_json,
            shippers_json,
            recipients_json,
            correspondents_json,
        ) = build_shipment_contact_payload()

        self.assertEqual(len(destinations_json), 1)
        destination_row = destinations_json[0]
        self.assertEqual(destination_row["id"], destination.id)
        self.assertEqual(destination_row["label"], str(destination))
        self.assertEqual(destination_row["city"], "Lyon")
        self.assertEqual(destination_row["iata_code"], "LYS")
        self.assertEqual(destination_row["country"], "France")
        self.assertEqual(destination_row["correspondent_contact_id"], correspondent.id)
        self.assertEqual(
            shippers_json,
            [
                {
                    "id": shipper.id,
                    "name": "Shipper Org",
                    "organization_id": shipper.id,
                    "destination_id": destination.id,
                    "destination_ids": [destination.id],
                    "scoped_destination_ids": [],
                }
            ],
        )
        self.assertEqual(
            {entry["id"] for entry in recipients_json}, {recipient.id, corr_contact.id}
        )
        recipient_entry = next(entry for entry in recipients_json if entry["id"] == recipient.id)
        self.assertEqual(recipient_entry["name"], "Recipient Org")
        self.assertEqual(recipient_entry["organization_id"], recipient.id)
        self.assertEqual(recipient_entry["countries"], ["France", "UK"])
        self.assertEqual(recipient_entry["destination_id"], destination.id)
        self.assertEqual(recipient_entry["destination_ids"], [destination.id])
        self.assertEqual(recipient_entry["linked_shipper_ids"], [])
        self.assertEqual(recipient_entry["binding_pairs"], [])
        promoted_correspondent_entry = next(
            entry for entry in recipients_json if entry["id"] == corr_contact.id
        )
        self.assertEqual(promoted_correspondent_entry["name"], "Corr Contact")
        self.assertEqual(promoted_correspondent_entry["organization_id"], corr_contact.id)
        self.assertEqual(promoted_correspondent_entry["countries"], [])
        self.assertEqual(promoted_correspondent_entry["destination_id"], destination.id)
        self.assertEqual(promoted_correspondent_entry["destination_ids"], [destination.id])
        self.assertEqual(promoted_correspondent_entry["linked_shipper_ids"], [])
        self.assertEqual(promoted_correspondent_entry["binding_pairs"], [])
        self.assertEqual(
            correspondents_json,
            [
                {
                    "id": corr_contact.id,
                    "name": "Corr Contact",
                    "destination_id": destination.id,
                    "destination_ids": [destination.id],
                },
                {
                    "id": correspondent.id,
                    "name": "Corr A",
                    "destination_id": destination.id,
                    "destination_ids": [destination.id],
                },
            ],
        )

    def test_build_shipment_contact_payload_includes_destination_correspondent_without_tag(self):
        correspondent = Contact.objects.create(
            name="Corr Untagged",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Dakar",
            iata_code="DKR-CORR",
            country="Senegal",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper = Contact.objects.create(
            name="Shipper Dakar",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_tag = ContactTag.objects.create(name="expediteur")
        shipper.tags.add(shipper_tag)
        shipper.destinations.add(destination)

        _, _, _, correspondents_json = build_shipment_contact_payload()

        self.assertIn(
            {
                "id": correspondent.id,
                "name": "Corr Untagged",
                "destination_id": destination.id,
                "destination_ids": [destination.id],
            },
            correspondents_json,
        )

    def test_build_shipment_contact_payload_formats_shipper_and_recipient_names(self):
        correspondent = Contact.objects.create(name="Corr B")
        destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ-FMT",
            country="Cote d'Ivoire",
            correspondent_contact=correspondent,
            is_active=True,
        )
        organization = Contact.objects.create(
            name="ASSOCIATION FORMATTED",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper = Contact.objects.create(
            name="Legacy Shipper",
            contact_type=ContactType.PERSON,
            title="M.",
            first_name="Jean",
            last_name="Dupont",
            organization=organization,
            is_active=True,
        )
        shipper.destinations.add(destination)
        shipper_tag = ContactTag.objects.create(name="expediteur")
        shipper.tags.add(shipper_tag)

        recipient = Contact.objects.create(
            name="Legacy Recipient",
            contact_type=ContactType.PERSON,
            title="Mme",
            first_name="Alice",
            last_name="Martin",
            organization=organization,
            is_active=True,
        )
        recipient.destinations.add(destination)
        recipient_tag = ContactTag.objects.create(name="destinataire")
        recipient.tags.add(recipient_tag)

        _, shippers_json, recipients_json, _ = build_shipment_contact_payload()

        shipper_entry = next(entry for entry in shippers_json if entry["id"] == shipper.id)
        recipient_entry = next(entry for entry in recipients_json if entry["id"] == recipient.id)
        self.assertEqual(
            shipper_entry["name"],
            "ASSOCIATION FORMATTED (M., Jean, DUPONT)",
        )
        self.assertEqual(
            recipient_entry["name"],
            "ASSOCIATION FORMATTED (Mme, Alice, MARTIN)",
        )

    def test_build_shipment_contact_payload_excludes_people_without_organization(self):
        correspondent = Contact.objects.create(name="Corr Scope")
        destination = Destination.objects.create(
            city="Cotonou",
            iata_code="COO-SCOPE",
            country="Benin",
            correspondent_contact=correspondent,
            is_active=True,
        )
        organization = Contact.objects.create(
            name="ASSOCIATION SCOPE",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_tag = ContactTag.objects.create(name="expediteur")
        recipient_tag = ContactTag.objects.create(name="destinataire")

        shipper_org = Contact.objects.create(
            name="Shipper Org Scope",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_org.tags.add(shipper_tag)
        shipper_org.destinations.add(destination)

        shipper_person_with_org = Contact.objects.create(
            name="Shipper Person Scope",
            contact_type=ContactType.PERSON,
            first_name="Jean",
            last_name="Dupont",
            organization=organization,
            is_active=True,
        )
        shipper_person_with_org.tags.add(shipper_tag)
        shipper_person_with_org.destinations.add(destination)

        shipper_person_no_org = Contact.objects.create(
            name="Shipper Person No Org Scope",
            contact_type=ContactType.PERSON,
            first_name="Paul",
            last_name="Martin",
            is_active=True,
        )
        shipper_person_no_org.tags.add(shipper_tag)
        shipper_person_no_org.destinations.add(destination)

        recipient_org = Contact.objects.create(
            name="Recipient Org Scope",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_org.tags.add(recipient_tag)
        recipient_org.destinations.add(destination)
        recipient_org.linked_shippers.add(shipper_org)

        recipient_person_with_org = Contact.objects.create(
            name="Recipient Person Scope",
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Yao",
            organization=organization,
            is_active=True,
        )
        recipient_person_with_org.tags.add(recipient_tag)
        recipient_person_with_org.destinations.add(destination)
        recipient_person_with_org.linked_shippers.add(shipper_org)

        recipient_person_no_org = Contact.objects.create(
            name="Recipient Person No Org Scope",
            contact_type=ContactType.PERSON,
            first_name="Lea",
            last_name="Ndiaye",
            is_active=True,
        )
        recipient_person_no_org.tags.add(recipient_tag)
        recipient_person_no_org.destinations.add(destination)
        recipient_person_no_org.linked_shippers.add(shipper_org)

        _, shippers_json, recipients_json, _ = build_shipment_contact_payload()
        shipper_ids = {entry["id"] for entry in shippers_json}
        recipient_ids = {entry["id"] for entry in recipients_json}

        self.assertIn(shipper_org.id, shipper_ids)
        self.assertIn(shipper_person_with_org.id, shipper_ids)
        self.assertNotIn(shipper_person_no_org.id, shipper_ids)
        self.assertIn(recipient_org.id, recipient_ids)
        self.assertIn(recipient_person_with_org.id, recipient_ids)
        self.assertNotIn(recipient_person_no_org.id, recipient_ids)

    def test_build_shipment_contact_payload_disambiguates_same_organization_shippers(self):
        correspondent = Contact.objects.create(name="Corr C")
        destination = Destination.objects.create(
            city="Lome",
            iata_code="LFW-DUP",
            country="Togo",
            correspondent_contact=correspondent,
            is_active=True,
        )
        organization = Contact.objects.create(
            name="ASSOCIATION DUP",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_tag = ContactTag.objects.create(name="expediteur")
        shipper_a = Contact.objects.create(
            name="Shipper A",
            contact_type=ContactType.PERSON,
            title="M.",
            first_name="Jean",
            last_name="Dupont",
            organization=organization,
            is_active=True,
        )
        shipper_b = Contact.objects.create(
            name="Shipper B",
            contact_type=ContactType.PERSON,
            title="Mme",
            first_name="Alice",
            last_name="Martin",
            organization=organization,
            is_active=True,
        )
        for shipper in (shipper_a, shipper_b):
            shipper.destinations.add(destination)
            shipper.tags.add(shipper_tag)

        recipient_tag = ContactTag.objects.create(name="destinataire")
        recipient_a = Contact.objects.create(
            name="Recipient A",
            contact_type=ContactType.PERSON,
            title="M.",
            first_name="Paul",
            last_name="Ndiaye",
            organization=organization,
            is_active=True,
        )
        recipient_b = Contact.objects.create(
            name="Recipient B",
            contact_type=ContactType.PERSON,
            title="Mme",
            first_name="Lea",
            last_name="Yao",
            organization=organization,
            is_active=True,
        )
        for recipient in (recipient_a, recipient_b):
            recipient.destinations.add(destination)
            recipient.tags.add(recipient_tag)
            recipient.linked_shippers.add(shipper_a)

        _, shippers_json, recipients_json, _ = build_shipment_contact_payload()
        shipper_labels = {
            entry["id"]: entry["name"]
            for entry in shippers_json
            if entry["id"] in {shipper_a.id, shipper_b.id}
        }
        recipient_labels = {
            entry["id"]: entry["name"]
            for entry in recipients_json
            if entry["id"] in {recipient_a.id, recipient_b.id}
        }

        self.assertEqual(
            shipper_labels[shipper_a.id],
            "ASSOCIATION DUP (M., Jean, DUPONT)",
        )
        self.assertEqual(
            shipper_labels[shipper_b.id],
            "ASSOCIATION DUP (Mme, Alice, MARTIN)",
        )
        self.assertEqual(
            recipient_labels[recipient_a.id],
            "ASSOCIATION DUP (M., Paul, NDIAYE)",
        )
        self.assertEqual(
            recipient_labels[recipient_b.id],
            "ASSOCIATION DUP (Mme, Lea, YAO)",
        )

    def test_build_shipment_contact_payload_uses_org_roles_scope_and_binding_pairs(self):
        correspondent = Contact.objects.create(name="Corr Roles")
        destination_abj = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ-ROLE",
            country="Cote d'Ivoire",
            correspondent_contact=correspondent,
            is_active=True,
        )
        destination_dla = Destination.objects.create(
            city="Douala",
            iata_code="DLA-ROLE",
            country="Cameroun",
            correspondent_contact=correspondent,
            is_active=True,
        )

        shipper_tag = ContactTag.objects.create(name="expediteur")
        recipient_tag = ContactTag.objects.create(name="destinataire")

        shipper_org = Contact.objects.create(
            name="Shipper Roles",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_org.tags.add(shipper_tag)

        recipient_org = Contact.objects.create(
            name="Recipient Roles",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_org.tags.add(recipient_tag)

        shipper_assignment = OrganizationRoleAssignment.objects.create(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=recipient_org,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )

        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            destination=destination_abj,
            all_destinations=False,
            is_active=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination_abj,
            is_active=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination_dla,
            is_active=True,
        )

        _, shippers_json, recipients_json, _ = build_shipment_contact_payload()

        shipper_entry = next(entry for entry in shippers_json if entry["id"] == shipper_org.id)
        recipient_entry = next(
            entry for entry in recipients_json if entry["id"] == recipient_org.id
        )
        self.assertEqual(shipper_entry["organization_id"], shipper_org.id)
        self.assertEqual(recipient_entry["organization_id"], recipient_org.id)
        self.assertEqual(shipper_entry["scoped_destination_ids"], [destination_abj.id])
        self.assertEqual(
            recipient_entry["binding_pairs"],
            [
                {
                    "shipper_id": shipper_org.id,
                    "destination_id": destination_abj.id,
                },
                {
                    "shipper_id": shipper_org.id,
                    "destination_id": destination_dla.id,
                },
            ],
        )

    def test_parse_shipment_lines_collects_all_error_branches(self):
        product = Product.objects.create(
            sku="SHIP-001",
            name="Shipment Product",
            qr_code_image="qr_codes/test.png",
        )
        data = {
            "line_1_carton_id": "1",
            "line_1_product_code": product.sku,
            "line_1_quantity": "1",
            "line_2_carton_id": "2",
            "line_2_product_code": "",
            "line_2_quantity": "",
            "line_3_carton_id": "",
            "line_3_product_code": "",
            "line_3_quantity": "1",
            "line_4_carton_id": "",
            "line_4_product_code": product.sku,
            "line_4_quantity": "",
            "line_5_carton_id": "",
            "line_5_product_code": product.sku,
            "line_5_quantity": "0",
            "line_6_carton_id": "",
            "line_6_product_code": "UNKNOWN",
            "line_6_quantity": "1",
            "line_7_carton_id": "",
            "line_7_product_code": "",
            "line_7_quantity": "",
        }

        line_values, line_items, line_errors = parse_shipment_lines(
            carton_count=7,
            data=data,
            allowed_carton_ids={"1"},
        )

        self.assertEqual(len(line_values), 7)
        self.assertEqual(line_items, [])
        self.assertEqual(
            line_errors,
            {
                "1": ["Choisissez un carton OU créez un colis depuis un produit."],
                "2": ["Carton indisponible."],
                "3": ["Produit requis."],
                "4": ["Quantité requise."],
                "5": ["Quantité invalide."],
                "6": ["Produit introuvable."],
                "7": ["Renseignez un carton ou un produit."],
            },
        )

    def test_parse_shipment_lines_accepts_valid_carton_and_product_lines(self):
        product = Product.objects.create(
            sku="SHIP-VALID",
            name="Shipment Valid Product",
            qr_code_image="qr_codes/test.png",
        )
        data = {
            "line_1_carton_id": "10",
            "line_1_product_code": "",
            "line_1_quantity": "",
            "line_2_carton_id": "",
            "line_2_product_code": "SHIP-VALID",
            "line_2_quantity": "3",
        }

        line_values, line_items, line_errors = parse_shipment_lines(
            carton_count=2,
            data=data,
            allowed_carton_ids={"10"},
        )

        self.assertEqual(len(line_values), 2)
        self.assertEqual(
            line_items,
            [
                {"carton_id": 10},
                {"product": product, "quantity": 3},
            ],
        )
        self.assertEqual(line_errors, {})
