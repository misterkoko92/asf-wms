import re
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms.models import (
    Carton,
    CartonFormat,
    CartonItem,
    CartonStatus,
    Destination,
    Location,
    Product,
    ProductCategory,
    ProductLot,
    ProductLotStatus,
    RecipientProductPreference,
    Shipment,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
    ShipmentWorkflowProjection,
    Warehouse,
)


class ScanAdminShipmentPartiesViewTests(TestCase):
    def _normalize_html(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="scan-shipment-parties-superuser",
            password="pass1234",  # pragma: allowlist secret
            email="scan-shipment-parties-superuser@example.com",
        )
        self.correspondent_org = Contact.objects.create(
            name="Correspondant Bamako",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=self.correspondent_org,
            is_active=True,
        )
        self.shipper_org = Contact.objects.create(
            name="Shipper Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.shipper_person = Contact.objects.create(
            name="Alice Shipper",
            first_name="Alice",
            last_name="Shipper",
            contact_type=ContactType.PERSON,
            organization=self.shipper_org,
            is_active=True,
        )
        self.shipper = ShipmentShipper.objects.create(
            organization=self.shipper_org,
            default_contact=self.shipper_person,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        self.recipient_org = Contact.objects.create(
            name="Hopital Bamako",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=self.recipient_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
            is_correspondent=True,
        )
        self.recipient_person = Contact.objects.create(
            name="Dr Truc",
            first_name="Dr",
            last_name="Truc",
            contact_type=ContactType.PERSON,
            organization=self.recipient_org,
            is_active=True,
        )
        self.recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=self.recipient_organization,
            contact=self.recipient_person,
            is_active=True,
        )
        self.link = ShipmentShipperRecipientLink.objects.create(
            shipper=self.shipper,
            recipient_organization=self.recipient_organization,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=self.link,
            recipient_contact=self.recipient_contact,
            is_default=True,
            is_active=True,
        )
        self.product = Product.objects.create(
            sku="SCAN-RECIP-PREF-001",
            name="Compresses scan",
            brand="ASF",
            qr_code_image="qr_codes/scan_recip_pref_001.png",
        )
        self.other_product = Product.objects.create(
            sku="SCAN-RECIP-PREF-002",
            name="Bandages scan",
            brand="ASF",
            qr_code_image="qr_codes/scan_recip_pref_002.png",
        )

    def _detail_url(self, recipient_organization=None):
        recipient_organization = recipient_organization or self.recipient_organization
        return reverse(
            "scan:scan_admin_recipient_organization_detail",
            kwargs={"recipient_organization_id": recipient_organization.id},
        )

    def test_scan_admin_contacts_renders_shipment_party_cockpit(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_admin_contacts"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pilotage contacts expédition")
        self.assertContains(response, "Expéditeurs")
        self.assertContains(response, "Structures destinataires")
        self.assertContains(response, "Correspondants d'escale")
        self.assertContains(response, "Définir le référent destinataire par défaut")
        normalized_html = self._normalize_html(response.content.decode("utf-8"))
        self.assertIn(
            'name="action" value="set_default_authorized_recipient_contact"',
            normalized_html,
        )
        self.assertIn(
            'name="action" value="set_stopover_correspondent_recipient_organization"',
            normalized_html,
        )
        self.assertIn(
            'name="action" value="merge_shipment_recipient_organizations"',
            normalized_html,
        )
        self.assertEqual(response.context["cockpit_mode"], "shipment_parties")
        self.assertEqual(
            [shipper.id for shipper in response.context["cockpit_shipment_shippers"]],
            [self.shipper.id],
        )
        self.assertEqual(
            [
                recipient.id
                for recipient in response.context["cockpit_shipment_recipient_organizations"]
            ],
            [self.recipient_organization.id],
        )
        self.assertEqual(
            [link.id for link in response.context["cockpit_shipment_links"]],
            [self.link.id],
        )
        self.assertContains(response, self._detail_url())
        self.assertContains(response, "Ouvrir")

    def test_scan_admin_recipient_detail_shows_current_preferences(self):
        self.client.force_login(self.superuser)
        preference = RecipientProductPreference.objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="requested",
            quantity_target=8,
            period_unit="week",
            source="scan_admin",
            created_by=self.superuser,
            updated_by=self.superuser,
        )

        response = self.client.get(self._detail_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["recipient_organization"], self.recipient_organization)
        self.assertEqual(len(response.context["recipient_product_rows"]), 2)
        self.assertContains(response, "Préférences produits")
        self.assertContains(response, self.product.name)
        self.assertContains(response, preference.get_status_display())
        self.assertContains(response, "Enregistrer la ligne")
        self.assertContains(
            response,
            'class="form-control recipient-preference-input--quantity ui-number-input-compact"',
        )
        self.assertContains(response, 'id="id_preference_q"')
        self.assertContains(response, 'id="id_preference_sort"')
        self.assertContains(response, 'id="recipient-preference-category-l1"')
        self.assertContains(response, 'id="id_preference_category"')
        self.assertContains(response, 'name="preference_category"')

    def test_scan_admin_recipient_detail_shows_units_per_carton_estimate(self):
        self.client.force_login(self.superuser)
        CartonFormat.objects.create(
            name="Carton standard",
            length_cm=40,
            width_cm=30,
            height_cm=20,
            max_weight_g=8000,
            is_default=True,
        )
        self.product.weight_g = 500
        self.product.volume_cm3 = 1000
        self.product.save(update_fields=["weight_g", "volume_cm3"])

        response = self.client.get(self._detail_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Qté par colis (estimation)")
        self.assertContains(response, 'class="recipient-preference-col--estimate">16</td>')
        self.assertContains(response, 'class="recipient-preference-col--estimate">--</td>')

    def test_scan_admin_recipient_detail_filters_and_sorts_catalog_rows(self):
        self.client.force_login(self.superuser)
        CartonFormat.objects.create(
            name="Carton standard",
            length_cm=40,
            width_cm=30,
            height_cm=20,
            max_weight_g=8000,
            is_default=True,
        )
        category_root = ProductCategory.objects.create(name="Medical")
        category_child = ProductCategory.objects.create(name="Dressings", parent=category_root)
        category_other = ProductCategory.objects.create(name="Equipment")
        self.product.name = "Compresses scan detail"
        self.product.brand = "Zulu"
        self.product.category = category_child
        self.product.weight_g = 500
        self.product.volume_cm3 = 1000
        self.product.save(update_fields=["name", "brand", "category", "weight_g", "volume_cm3"])
        self.other_product.name = "Bandages scan detail"
        self.other_product.brand = "Alpha"
        self.other_product.category = category_other
        self.other_product.weight_g = 1000
        self.other_product.volume_cm3 = 2000
        self.other_product.save(
            update_fields=["name", "brand", "category", "weight_g", "volume_cm3"]
        )
        third_product = Product.objects.create(
            sku="SCAN-RECIP-PREF-003",
            name="Compresses scan extra",
            brand="Bravo",
            category=category_child,
            qr_code_image="qr_codes/scan_recip_pref_003.png",
        )

        filtered_response = self.client.get(
            self._detail_url(),
            {
                "preference_q": "Compresses scan",
                "preference_category": str(category_root.id),
                "preference_sort": "brand",
            },
        )

        self.assertEqual(filtered_response.status_code, 200)
        self.assertEqual(
            [row["product"].id for row in filtered_response.context["recipient_product_rows"]],
            [third_product.id, self.product.id],
        )
        self.assertEqual(filtered_response.context["preference_query"], "Compresses scan")
        self.assertEqual(
            filtered_response.context["preference_category_id"],
            str(category_root.id),
        )
        self.assertEqual(filtered_response.context["preference_sort"], "brand")

        estimate_response = self.client.get(
            self._detail_url(),
            {"preference_sort": "units_per_carton_estimate"},
        )

        self.assertEqual(estimate_response.status_code, 200)
        self.assertEqual(
            [row["product"].id for row in estimate_response.context["recipient_product_rows"]],
            [self.other_product.id, self.product.id, third_product.id],
        )

    def test_scan_admin_recipient_detail_can_create_update_and_clear_preference(self):
        self.client.force_login(self.superuser)

        create_response = self.client.post(
            self._detail_url(),
            {
                "action": "save_recipient_preference",
                "product_id": str(self.product.id),
                "status": "allowed",
                "quantity_target": "15",
                "period_unit": "month",
                "notes": "Stock utile",
            },
        )

        self.assertEqual(create_response.status_code, 302)
        preference = self.recipient_organization.product_preferences.get(product=self.product)
        self.assertEqual(preference.status, "allowed")
        self.assertEqual(preference.quantity_target, 15)
        self.assertEqual(preference.period_unit, "month")
        self.assertEqual(preference.source, "scan_admin")
        self.assertEqual(preference.updated_by, self.superuser)

        update_response = self.client.post(
            self._detail_url(),
            {
                "action": "save_recipient_preference",
                "product_id": str(self.product.id),
                "status": "refused",
                "quantity_target": "",
                "period_unit": "",
                "notes": "Ne plus livrer",
            },
        )

        self.assertEqual(update_response.status_code, 302)
        preference.refresh_from_db()
        self.assertEqual(preference.status, "refused")
        self.assertIsNone(preference.quantity_target)
        self.assertEqual(preference.notes, "Ne plus livrer")

        delete_response = self.client.post(
            self._detail_url(),
            {
                "action": "save_recipient_preference",
                "product_id": str(self.product.id),
                "status": "unspecified",
                "quantity_target": "15",
                "period_unit": "month",
                "notes": "Retirer la règle",
            },
        )

        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(self.recipient_organization.product_preferences.exists())

    def test_scan_admin_recipient_detail_post_preserves_filter_querystring(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            self._detail_url(),
            {
                "action": "save_recipient_preference",
                "product_id": str(self.product.id),
                "status": "allowed",
                "quantity_target": "15",
                "period_unit": "month",
                "notes": "Stock utile",
                "preference_q": "Compresses",
                "preference_category": "17",
                "preference_sort": "brand",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            (
                f"{self._detail_url()}"
                "?preference_q=Compresses&preference_category=17&preference_sort=brand"
            ),
        )

    def test_scan_admin_recipient_detail_uses_shared_preference_use_case(self):
        self.client.force_login(self.superuser)

        with mock.patch(
            "wms.views_scan_admin.save_recipient_product_preference",
            create=True,
            return_value=mock.Mock(),
        ) as save_preference:
            response = self.client.post(
                self._detail_url(),
                {
                    "action": "save_recipient_preference",
                    "product_id": str(self.product.id),
                    "status": "allowed",
                    "quantity_target": "15",
                    "period_unit": "month",
                    "notes": "Stock utile",
                },
            )

        self.assertEqual(response.status_code, 302)
        save_preference.assert_called_once()
        self.assertEqual(
            save_preference.call_args.kwargs["recipient_organization"],
            self.recipient_organization,
        )
        self.assertEqual(save_preference.call_args.kwargs["product"], self.product)
        self.assertEqual(save_preference.call_args.kwargs["status"], "allowed")
        self.assertEqual(save_preference.call_args.kwargs["quantity_target"], 15)

    def test_scan_admin_recipient_detail_shows_preference_coverage_in_product_table(self):
        self.client.force_login(self.superuser)
        self.recipient_organization.product_preferences.create(
            product=self.product,
            status="requested",
            quantity_target=10,
            period_unit="week",
            source="scan_admin",
            created_by=self.superuser,
            updated_by=self.superuser,
        )
        warehouse = Warehouse.objects.create(name="Scan Coverage Warehouse")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        delivered_shipment = Shipment.objects.create(
            reference="26SCANCOV01",
            shipper_name=self.shipper_person.name,
            recipient_name=self.recipient_person.name,
            recipient_contact_ref=self.recipient_person,
            correspondent_name=self.correspondent_org.name,
            destination=self.destination,
            destination_address="10 Rue Test",
            destination_country="Mali",
        )
        delivered_carton = Carton.objects.create(
            code="C-SCAN-COV-1",
            status=CartonStatus.SHIPPED,
            shipment=delivered_shipment,
        )
        delivered_lot = ProductLot.objects.create(
            product=self.product,
            lot_code="SCAN-COV-LOT-1",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=50,
            location=location,
        )
        CartonItem.objects.create(
            carton=delivered_carton,
            product_lot=delivered_lot,
            quantity=4,
        )
        ShipmentWorkflowProjection.objects.create(
            shipment=delivered_shipment,
            destination=self.destination,
            reference=delivered_shipment.reference,
            delivered_at=timezone.now() - timedelta(hours=1),
        )
        pipeline_shipment = Shipment.objects.create(
            reference="26SCANCOV02",
            shipper_name=self.shipper_person.name,
            recipient_name=self.recipient_person.name,
            recipient_contact_ref=self.recipient_person,
            correspondent_name=self.correspondent_org.name,
            destination=self.destination,
            destination_address="10 Rue Test",
            destination_country="Mali",
        )
        pipeline_carton = Carton.objects.create(
            code="C-SCAN-COV-2",
            status=CartonStatus.ASSIGNED,
            shipment=pipeline_shipment,
        )
        pipeline_lot = ProductLot.objects.create(
            product=self.product,
            lot_code="SCAN-COV-LOT-2",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=50,
            location=location,
        )
        CartonItem.objects.create(
            carton=pipeline_carton,
            product_lot=pipeline_lot,
            quantity=1,
        )
        ShipmentWorkflowProjection.objects.create(
            shipment=pipeline_shipment,
            destination=self.destination,
            reference=pipeline_shipment.reference,
        )

        response = self.client.get(self._detail_url())

        self.assertEqual(response.status_code, 200)
        row = next(
            row
            for row in response.context["recipient_product_rows"]
            if row["product"].id == self.product.id
        )
        coverage = row["coverage"]
        self.assertEqual(coverage.delivered_quantity, 4)
        self.assertEqual(coverage.pipeline_quantity, 1)
        self.assertEqual(coverage.remaining_need, 5)
        self.assertContains(response, "Reste a servir")

    def test_admin_can_set_default_authorized_recipient_contact(self):
        self.client.force_login(self.superuser)
        other_person = Contact.objects.create(
            name="Dr Machin",
            first_name="Dr",
            last_name="Machin",
            contact_type=ContactType.PERSON,
            organization=self.recipient_org,
            is_active=True,
        )
        other_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=self.recipient_organization,
            contact=other_person,
            is_active=True,
        )
        other_authorization = ShipmentAuthorizedRecipientContact.objects.create(
            link=self.link,
            recipient_contact=other_recipient_contact,
            is_default=False,
            is_active=True,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "set_default_authorized_recipient_contact",
                "link_id": str(self.link.id),
                "recipient_contact_id": str(other_recipient_contact.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        other_authorization.refresh_from_db()
        default_authorization = ShipmentAuthorizedRecipientContact.objects.get(
            link=self.link,
            recipient_contact=self.recipient_contact,
        )
        self.assertTrue(other_authorization.is_default)
        self.assertFalse(default_authorization.is_default)

    def test_admin_can_switch_active_stopover_correspondent(self):
        self.client.force_login(self.superuser)
        other_org = Contact.objects.create(
            name="Hopital Secondaire",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        other_recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=other_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
            is_correspondent=False,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "set_stopover_correspondent_recipient_organization",
                "recipient_organization_id": str(other_recipient_organization.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.recipient_organization.refresh_from_db()
        other_recipient_organization.refresh_from_db()
        self.assertFalse(self.recipient_organization.is_correspondent)
        self.assertTrue(other_recipient_organization.is_correspondent)

    def test_admin_can_merge_recipient_structures(self):
        self.client.force_login(self.superuser)
        source_org = Contact.objects.create(
            name="Hopital Bamako Duplicate",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        source_recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=source_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
            is_correspondent=False,
        )
        source_person = Contact.objects.create(
            name="Dr Machin",
            first_name="Dr",
            last_name="Machin",
            contact_type=ContactType.PERSON,
            organization=source_org,
            is_active=True,
        )
        source_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=source_recipient_organization,
            contact=source_person,
            is_active=True,
        )
        source_link = ShipmentShipperRecipientLink.objects.create(
            shipper=self.shipper,
            recipient_organization=source_recipient_organization,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=source_link,
            recipient_contact=source_recipient_contact,
            is_default=False,
            is_active=True,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "merge_shipment_recipient_organizations",
                "source_recipient_organization_id": str(source_recipient_organization.id),
                "target_recipient_organization_id": str(self.recipient_organization.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        source_recipient_organization.refresh_from_db()
        source_org.refresh_from_db()
        self.assertFalse(source_recipient_organization.is_active)
        self.assertFalse(source_org.is_active)
        migrated_contact = ShipmentRecipientContact.objects.get(contact=source_person)
        self.assertEqual(migrated_contact.recipient_organization_id, self.recipient_organization.id)
        self.assertEqual(migrated_contact.contact.organization_id, self.recipient_org.id)
        self.assertFalse(ShipmentShipperRecipientLink.objects.filter(pk=source_link.pk).exists())
        self.assertTrue(
            ShipmentAuthorizedRecipientContact.objects.filter(
                link=self.link,
                recipient_contact=migrated_contact,
                is_active=True,
            ).exists()
        )

    def test_scan_admin_contacts_destination_filter_scopes_cockpit_and_correspondents(self):
        self.client.force_login(self.superuser)
        other_correspondent_org = Contact.objects.create(
            name="Correspondant Dakar",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        other_destination = Destination.objects.create(
            city="Dakar",
            iata_code="DKR",
            country="Senegal",
            correspondent_contact=other_correspondent_org,
            is_active=True,
        )
        other_shipper_org = Contact.objects.create(
            name="Shipper Dakar",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        other_shipper_person = Contact.objects.create(
            name="Jean Dakar",
            first_name="Jean",
            last_name="Dakar",
            contact_type=ContactType.PERSON,
            organization=other_shipper_org,
            is_active=True,
        )
        other_shipper = ShipmentShipper.objects.create(
            organization=other_shipper_org,
            default_contact=other_shipper_person,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        other_recipient_org = Contact.objects.create(
            name="Hopital Dakar",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        other_recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=other_recipient_org,
            destination=other_destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
            is_correspondent=True,
        )
        other_recipient_person = Contact.objects.create(
            name="Dr Dakar",
            first_name="Dr",
            last_name="Dakar",
            contact_type=ContactType.PERSON,
            organization=other_recipient_org,
            is_active=True,
        )
        other_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=other_recipient_organization,
            contact=other_recipient_person,
            is_active=True,
        )
        other_link = ShipmentShipperRecipientLink.objects.create(
            shipper=other_shipper,
            recipient_organization=other_recipient_organization,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=other_link,
            recipient_contact=other_recipient_contact,
            is_default=True,
            is_active=True,
        )

        response = self.client.get(
            reverse("scan:scan_admin_contacts"),
            {"destination_id": str(self.destination.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [shipper.id for shipper in response.context["cockpit_shipment_shippers"]],
            [self.shipper.id],
        )
        self.assertEqual(
            [
                recipient.id
                for recipient in response.context["cockpit_shipment_recipient_organizations"]
            ],
            [self.recipient_organization.id],
        )
        self.assertEqual(
            [link.id for link in response.context["cockpit_shipment_links"]],
            [self.link.id],
        )
        self.assertEqual(
            [contact.id for contact in response.context["correspondents"]],
            [self.correspondent_org.id],
        )
