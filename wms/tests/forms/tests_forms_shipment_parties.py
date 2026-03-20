from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.forms import ScanShipmentForm
from wms.models import (
    Destination,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)


class ScanShipmentFormShipmentPartyTests(TestCase):
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

    def _create_recipient_structure(
        self, name, *, destination, validation_status=None, is_active=True
    ):
        organization = self._create_organization(name)
        recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=organization,
            destination=destination,
            validation_status=validation_status or ShipmentValidationStatus.VALIDATED,
            is_active=is_active,
        )
        return recipient_org, organization

    def _authorize_recipient_contact(
        self,
        *,
        shipper,
        recipient_org,
        person_name,
        is_default=False,
        authorization_active=True,
        link_active=True,
    ):
        person = self._create_person(person_name, organization=recipient_org.organization)
        recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_org,
            contact=person,
            is_active=True,
        )
        link, _created = ShipmentShipperRecipientLink.objects.get_or_create(
            shipper=shipper,
            recipient_organization=recipient_org,
            defaults={"is_active": True},
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=recipient_contact,
            is_default=is_default,
            is_active=authorization_active,
        )
        if link.is_active != link_active:
            link.is_active = link_active
            link.save(update_fields=["is_active"])
        return person

    def test_scan_shipment_form_prefills_default_recipient_contact_for_shipper_link(self):
        destination, correspondent = self._create_destination_with_correspondent("ABJ")
        shipper, shipper_contact = self._create_shipper("ASF")
        recipient_org, _recipient_structure = self._create_recipient_structure(
            "Hopital Abidjan",
            destination=destination,
        )
        default_recipient = self._authorize_recipient_contact(
            shipper=shipper,
            recipient_org=recipient_org,
            person_name="Alice Default",
            is_default=True,
        )
        secondary_recipient = self._authorize_recipient_contact(
            shipper=shipper,
            recipient_org=recipient_org,
            person_name="Bruno Secondary",
        )
        other_shipper, _other_shipper_contact = self._create_shipper("MSF")
        other_recipient_org, _ = self._create_recipient_structure(
            "Hopital Dakar",
            destination=destination,
        )
        other_recipient = self._authorize_recipient_contact(
            shipper=other_shipper,
            recipient_org=other_recipient_org,
            person_name="Charlie Other",
            is_default=True,
        )

        form = ScanShipmentForm(
            destination_id=str(destination.id),
            initial={"shipper_contact": str(shipper_contact.id)},
        )

        self.assertEqual(
            set(form.fields["shipper_contact"].queryset.values_list("id", flat=True)),
            {shipper_contact.id, other_shipper.default_contact_id},
        )
        self.assertEqual(
            set(form.fields["recipient_contact"].queryset.values_list("id", flat=True)),
            {default_recipient.id, secondary_recipient.id},
        )
        self.assertNotIn(
            other_recipient.id,
            set(form.fields["recipient_contact"].queryset.values_list("id", flat=True)),
        )
        self.assertEqual(form.fields["recipient_contact"].initial, default_recipient.id)
        self.assertEqual(
            list(form.fields["correspondent_contact"].queryset.values_list("id", flat=True)),
            [correspondent.id],
        )
        self.assertEqual(form.fields["correspondent_contact"].initial, correspondent.id)

    def test_scan_shipment_form_rejects_recipient_without_active_validated_authorization(self):
        destination, correspondent = self._create_destination_with_correspondent("BKO")
        shipper, shipper_contact = self._create_shipper("ASF Bamako")
        pending_recipient_org, _ = self._create_recipient_structure(
            "Hopital Pending",
            destination=destination,
            validation_status=ShipmentValidationStatus.PENDING,
        )
        pending_recipient = self._authorize_recipient_contact(
            shipper=shipper,
            recipient_org=pending_recipient_org,
            person_name="Diane Pending",
            is_default=True,
        )

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_contact.id),
                "recipient_contact": str(pending_recipient.id),
                "correspondent_contact": str(correspondent.id),
                "carton_count": "1",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["recipient_contact"],
            [
                "Destinataire invalide: ce contact n'est pas disponible pour la destination sélectionnée."
            ],
        )

    def test_scan_shipment_form_rejects_recipient_when_shipper_link_is_inactive(self):
        destination, correspondent = self._create_destination_with_correspondent("DKR")
        shipper, shipper_contact = self._create_shipper("ASF Dakar")
        recipient_org, _recipient_structure = self._create_recipient_structure(
            "Hopital Dakar",
            destination=destination,
        )
        inactive_link_recipient = self._authorize_recipient_contact(
            shipper=shipper,
            recipient_org=recipient_org,
            person_name="Ibrahim Link",
            is_default=True,
            link_active=False,
        )

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_contact.id),
                "recipient_contact": str(inactive_link_recipient.id),
                "correspondent_contact": str(correspondent.id),
                "carton_count": "1",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["recipient_contact"],
            [
                "Destinataire invalide: ce contact n'est pas disponible pour la destination sélectionnée."
            ],
        )

    def test_scan_shipment_form_rejects_recipient_when_authorized_contact_is_inactive(self):
        destination, correspondent = self._create_destination_with_correspondent("NIM")
        shipper, shipper_contact = self._create_shipper("ASF Niamey")
        recipient_org, _recipient_structure = self._create_recipient_structure(
            "Hopital Niamey",
            destination=destination,
        )
        inactive_authorization_recipient = self._authorize_recipient_contact(
            shipper=shipper,
            recipient_org=recipient_org,
            person_name="Awa Authorization",
            is_default=True,
            authorization_active=False,
        )

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_contact.id),
                "recipient_contact": str(inactive_authorization_recipient.id),
                "correspondent_contact": str(correspondent.id),
                "carton_count": "1",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["recipient_contact"],
            [
                "Destinataire invalide: ce contact n'est pas disponible pour la destination sélectionnée."
            ],
        )

    def test_scan_shipment_form_rejects_shipper_without_validated_active_shipment_party(self):
        destination, correspondent = self._create_destination_with_correspondent("CMN")
        shipper_org = self._create_organization("Shipper Pending")
        shipper_contact = self._create_person("Paul Pending", organization=shipper_org)
        ShipmentShipper.objects.create(
            organization=shipper_org,
            default_contact=shipper_contact,
            validation_status=ShipmentValidationStatus.PENDING,
            is_active=True,
        )

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_contact.id),
                "recipient_contact": "",
                "correspondent_contact": str(correspondent.id),
                "carton_count": "1",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["shipper_contact"],
            ["Expéditeur invalide: ce choix n'est plus disponible."],
        )
