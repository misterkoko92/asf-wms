from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms.models import (
    AssociationProfile,
    AssociationRecipient,
    Destination,
    PortalAccessGrant,
    PortalAccessRole,
    Product,
    ProductCategory,
    RecipientProductPreference,
    RecipientProductPreferencePeriodUnit,
    RecipientProductPreferenceSource,
    RecipientProductPreferenceStatus,
    Shipment,
    ShipmentAuthorizedRecipientContact,
    ShipmentPreferenceOverride,
    ShipmentPreferenceOverrideAction,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from wms.parties.rebuild import (
    _duplicate_recipient_organization_scopes,
    _ensure_shipper_portal_grants,
    _merge_duplicate_product_preferences,
    _merge_duplicate_recipient_contacts,
    _merge_duplicate_recipient_organization_scopes,
    _merge_duplicate_shipper_links,
    _projection_candidate_for_link,
    _reassign_recipient_grants,
    _recipient_contact_for_projection,
    _refresh_legacy_projections,
    rebuild_recipient_party_graph,
)


class RecipientPartyRebuildTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.reviewer = self.user_model.objects.create_user(
            username="recipient-rebuild-reviewer",
            password="pass1234",  # pragma: allowlist secret
        )
        self.shipper_contact = self._create_org("Rebuild Association")
        self.shipper = self._create_shipper(self.shipper_contact, referent_label="Assoc")
        self.destination_primary = self._create_destination("Bamako", "BKO")
        self.destination_secondary = self._create_destination("Kayes", "KYS")

    def _create_user(self, username):
        return self.user_model.objects.create_user(
            username=username,
            password="pass1234",  # pragma: allowlist secret
        )

    def _create_org(self, name, **kwargs):
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=kwargs.pop("is_active", True),
            **kwargs,
        )

    def _create_person(self, organization, *, first_name, last_name, **kwargs):
        return Contact.objects.create(
            name=f"{first_name} {last_name}",
            first_name=first_name,
            last_name=last_name,
            contact_type=ContactType.PERSON,
            organization=organization,
            is_active=kwargs.pop("is_active", True),
            **kwargs,
        )

    def _create_destination(self, city, iata_code):
        correspondent = Contact.objects.create(
            name=f"{city} Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        return Destination.objects.create(
            city=city,
            iata_code=iata_code,
            country="Mali",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _create_shipper(self, organization, *, referent_label):
        referent = self._create_person(
            organization,
            first_name=referent_label,
            last_name="Referent",
        )
        return ShipmentShipper.objects.create(
            organization=organization,
            default_contact=referent,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

    def _create_recipient_organization(
        self,
        organization,
        destination,
        *,
        is_active=True,
        is_correspondent=False,
        validation_status=ShipmentValidationStatus.VALIDATED,
    ):
        return ShipmentRecipientOrganization.objects.create(
            organization=organization,
            destination=destination,
            validation_status=validation_status,
            is_active=is_active,
            is_correspondent=is_correspondent,
        )

    def _create_product(self, name, *, category=None):
        return Product.objects.create(
            name=name,
            category=category,
        )

    def _create_shipment(self, recipient_organization):
        return Shipment.objects.create(
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=recipient_organization.organization.name,
            recipient_contact_ref=recipient_organization.organization,
            destination=recipient_organization.destination,
            destination_address="1 rue du rebuild",
            destination_country=recipient_organization.destination.country,
        )

    def test_duplicate_recipient_organization_scopes_formats_duplicate_rows(self):
        manager = mock.Mock()
        manager.values.return_value.annotate.return_value.filter.return_value.order_by.return_value = [
            {
                "organization_id": 12,
                "organization__name": "Hopital Test",
                "destination_id": 34,
                "destination__city": "Bamako",
                "destination__iata_code": "BKO",
                "destination__country": "Mali",
            }
        ]
        manager.filter.return_value.order_by.return_value.values_list.return_value = [44, 45]

        with mock.patch("wms.parties.rebuild.ShipmentRecipientOrganization.objects", manager):
            duplicates = _duplicate_recipient_organization_scopes()

        self.assertEqual(
            duplicates,
            [
                {
                    "organization_id": 12,
                    "organization_name": "Hopital Test",
                    "destination_id": 34,
                    "destination_label": "Bamako (BKO) - Mali",
                    "recipient_organization_ids": [44, 45],
                }
            ],
        )

    def test_ensure_shipper_portal_grants_creates_missing_and_reactivates_existing(self):
        create_user = self._create_user("recipient-rebuild-create")
        create_contact = self._create_org("Rebuild Grant Create")
        AssociationProfile.objects.create(user=create_user, contact=create_contact)
        create_shipper = self._create_shipper(create_contact, referent_label="Create")

        reactivate_user = self._create_user("recipient-rebuild-reactivate")
        reactivate_contact = self._create_org("Rebuild Grant Reactivate")
        AssociationProfile.objects.create(user=reactivate_user, contact=reactivate_contact)
        reactivate_shipper = self._create_shipper(reactivate_contact, referent_label="Reactivate")
        PortalAccessGrant.objects.create(
            user=reactivate_user,
            role=PortalAccessRole.SHIPPER_ADMIN,
            shipper=reactivate_shipper,
            is_active=False,
        )

        no_shipper_user = self._create_user("recipient-rebuild-no-shipper")
        no_shipper_contact = self._create_org("Rebuild Grant No Shipper")
        AssociationProfile.objects.create(user=no_shipper_user, contact=no_shipper_contact)

        self.assertEqual(_ensure_shipper_portal_grants(apply=False), 1)
        self.assertFalse(
            PortalAccessGrant.objects.filter(
                user=create_user,
                shipper=create_shipper,
            ).exists()
        )

        self.assertEqual(_ensure_shipper_portal_grants(apply=True), 1)
        self.assertTrue(
            PortalAccessGrant.objects.filter(
                user=create_user,
                role=PortalAccessRole.SHIPPER_ADMIN,
                shipper=create_shipper,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            PortalAccessGrant.objects.filter(
                user=reactivate_user,
                role=PortalAccessRole.SHIPPER_ADMIN,
                shipper=reactivate_shipper,
                is_active=True,
            ).exists()
        )

    def test_merge_duplicate_recipient_contacts_moves_unique_and_merges_existing(self):
        organization = self._create_org("Recipient Contact Shared Org")
        target = self._create_recipient_organization(organization, self.destination_primary)
        source = self._create_recipient_organization(organization, self.destination_secondary)
        moved_person = self._create_person(
            organization,
            first_name="Moved",
            last_name="Person",
        )
        duplicate_person = self._create_person(
            organization,
            first_name="Duplicate",
            last_name="Person",
        )
        moved_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=source,
            contact=moved_person,
            is_active=True,
        )
        source_duplicate = ShipmentRecipientContact.objects.create(
            recipient_organization=source,
            contact=duplicate_person,
            is_active=True,
        )
        target_duplicate = ShipmentRecipientContact.objects.create(
            recipient_organization=target,
            contact=duplicate_person,
            is_active=False,
        )

        with mock.patch("wms.parties.rebuild._merge_authorized_contacts") as merge_mock:
            _merge_duplicate_recipient_contacts(source=source, target=target)

        moved_contact.refresh_from_db()
        target_duplicate.refresh_from_db()
        self.assertEqual(moved_contact.recipient_organization, target)
        self.assertTrue(target_duplicate.is_active)
        self.assertFalse(ShipmentRecipientContact.objects.filter(pk=source_duplicate.pk).exists())
        merge_mock.assert_called_once_with(
            source_recipient_contact=mock.ANY,
            target_recipient_contact=target_duplicate,
        )

    def test_merge_duplicate_shipper_links_moves_unique_and_merges_existing(self):
        organization = self._create_org("Recipient Link Shared Org")
        target = self._create_recipient_organization(organization, self.destination_primary)
        source = self._create_recipient_organization(organization, self.destination_secondary)
        unique_shipper = self._create_shipper(
            self._create_org("Unique Link Shipper"),
            referent_label="Unique",
        )
        duplicate_shipper = self._create_shipper(
            self._create_org("Duplicate Link Shipper"),
            referent_label="Duplicate",
        )
        moved_link = ShipmentShipperRecipientLink.objects.create(
            shipper=unique_shipper,
            recipient_organization=source,
            is_active=True,
        )
        source_duplicate_link = ShipmentShipperRecipientLink.objects.create(
            shipper=duplicate_shipper,
            recipient_organization=source,
            is_active=True,
        )
        target_duplicate_link = ShipmentShipperRecipientLink.objects.create(
            shipper=duplicate_shipper,
            recipient_organization=target,
            is_active=False,
        )

        with mock.patch("wms.parties.rebuild._merge_shipper_links") as merge_mock:
            _merge_duplicate_shipper_links(source=source, target=target)

        moved_link.refresh_from_db()
        target_duplicate_link.refresh_from_db()
        self.assertEqual(moved_link.recipient_organization, target)
        self.assertTrue(target_duplicate_link.is_active)
        merge_mock.assert_called_once_with(
            source_link=source_duplicate_link,
            target_link=target_duplicate_link,
        )

    def test_merge_duplicate_product_preferences_moves_unique_and_merges_fields(self):
        organization = self._create_org("Recipient Preference Shared Org")
        target = self._create_recipient_organization(organization, self.destination_primary)
        source = self._create_recipient_organization(organization, self.destination_secondary)
        category = ProductCategory.objects.create(name="Hygiene")
        product = self._create_product("Soap", category=category)
        moved_preference = RecipientProductPreference.objects.create(
            recipient_organization=source,
            category=category,
            status=RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=4,
            period_unit=RecipientProductPreferencePeriodUnit.MONTH,
            notes="Keep this category",
            source=RecipientProductPreferenceSource.PORTAL,
        )
        source_duplicate = RecipientProductPreference.objects.create(
            recipient_organization=source,
            product=product,
            status=RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=10,
            period_unit=RecipientProductPreferencePeriodUnit.WEEK,
            notes="Need soap",
            source=RecipientProductPreferenceSource.PORTAL,
        )
        target_existing = RecipientProductPreference.objects.create(
            recipient_organization=target,
            product=product,
            status=RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=1,
            period_unit=RecipientProductPreferencePeriodUnit.WEEK,
            notes="",
            source=RecipientProductPreferenceSource.SYSTEM,
        )
        RecipientProductPreference.objects.filter(pk=target_existing.pk).update(
            quantity_target=None,
            period_unit="",
            source="",
        )
        target_existing.refresh_from_db()

        _merge_duplicate_product_preferences(source=source, target=target)

        moved_preference.refresh_from_db()
        target_existing.refresh_from_db()
        self.assertEqual(moved_preference.recipient_organization, target)
        self.assertEqual(target_existing.quantity_target, 10)
        self.assertEqual(
            target_existing.period_unit,
            RecipientProductPreferencePeriodUnit.WEEK,
        )
        self.assertEqual(target_existing.notes, "Need soap")
        self.assertEqual(target_existing.source, RecipientProductPreferenceSource.PORTAL)
        self.assertFalse(RecipientProductPreference.objects.filter(pk=source_duplicate.pk).exists())

    def test_reassign_recipient_grants_moves_and_merges_metadata(self):
        organization = self._create_org("Recipient Grant Shared Org")
        target = self._create_recipient_organization(organization, self.destination_primary)
        source = self._create_recipient_organization(organization, self.destination_secondary)
        moved_user = self._create_user("recipient-grant-moved")
        merged_user = self._create_user("recipient-grant-merged")
        moved_grant = PortalAccessGrant.objects.create(
            user=moved_user,
            role=PortalAccessRole.RECIPIENT_ADMIN,
            recipient_organization=source,
        )
        source_merged_grant = PortalAccessGrant.objects.create(
            user=merged_user,
            role=PortalAccessRole.RECIPIENT_ADMIN,
            recipient_organization=source,
            is_active=True,
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )
        target_merged_grant = PortalAccessGrant.objects.create(
            user=merged_user,
            role=PortalAccessRole.RECIPIENT_ADMIN,
            recipient_organization=target,
            is_active=False,
            reviewed_by=None,
            reviewed_at=None,
        )

        reassigned = _reassign_recipient_grants(source=source, target=target)

        moved_grant.refresh_from_db()
        target_merged_grant.refresh_from_db()
        self.assertEqual(reassigned, 2)
        self.assertEqual(moved_grant.recipient_organization, target)
        self.assertTrue(target_merged_grant.is_active)
        self.assertEqual(target_merged_grant.reviewed_by, self.reviewer)
        self.assertIsNotNone(target_merged_grant.reviewed_at)
        self.assertFalse(PortalAccessGrant.objects.filter(pk=source_merged_grant.pk).exists())

    def test_merge_duplicate_recipient_organization_scopes_updates_target_and_moves_override(self):
        organization = self._create_org("Recipient Scope Shared Org")
        target = self._create_recipient_organization(
            organization,
            self.destination_primary,
            is_active=False,
            is_correspondent=False,
            validation_status=ShipmentValidationStatus.PENDING,
        )
        source = self._create_recipient_organization(
            organization,
            self.destination_secondary,
            is_active=True,
            is_correspondent=True,
            validation_status=ShipmentValidationStatus.VALIDATED,
        )
        product = self._create_product("Scope Soap")
        shipment = self._create_shipment(source)
        override = ShipmentPreferenceOverride.objects.create(
            shipment=shipment,
            recipient_organization=source,
            product=product,
            preference_status_snapshot=RecipientProductPreferenceStatus.REFUSED,
            action=ShipmentPreferenceOverrideAction.OVERRIDE_REFUSAL,
            reason="Manual review",
            created_by=self.reviewer,
        )

        with (
            mock.patch("wms.parties.rebuild._merge_duplicate_recipient_contacts") as contacts_mock,
            mock.patch("wms.parties.rebuild._merge_duplicate_shipper_links") as links_mock,
            mock.patch("wms.parties.rebuild._merge_duplicate_product_preferences") as prefs_mock,
            mock.patch(
                "wms.parties.rebuild._reassign_recipient_grants", return_value=3
            ) as grants_mock,
        ):
            merged_count, reassigned_count = _merge_duplicate_recipient_organization_scopes(
                [
                    {"recipient_organization_ids": [target.id]},
                    {"recipient_organization_ids": [target.id, source.id]},
                ]
            )

        target.refresh_from_db()
        override.refresh_from_db()
        self.assertEqual(merged_count, 1)
        self.assertEqual(reassigned_count, 3)
        self.assertTrue(target.is_active)
        self.assertTrue(target.is_correspondent)
        self.assertEqual(target.validation_status, ShipmentValidationStatus.VALIDATED)
        self.assertEqual(override.recipient_organization, target)
        self.assertFalse(ShipmentRecipientOrganization.objects.filter(pk=source.pk).exists())
        self.assertEqual(contacts_mock.call_count, 1)
        self.assertEqual(links_mock.call_count, 1)
        self.assertEqual(prefs_mock.call_count, 1)
        self.assertEqual(grants_mock.call_count, 1)
        self.assertEqual(
            contacts_mock.call_args.kwargs["source"].destination_id,
            self.destination_secondary.id,
        )
        self.assertEqual(contacts_mock.call_args.kwargs["target"].pk, target.pk)
        self.assertEqual(
            links_mock.call_args.kwargs["source"].destination_id,
            self.destination_secondary.id,
        )
        self.assertEqual(links_mock.call_args.kwargs["target"].pk, target.pk)
        self.assertEqual(
            prefs_mock.call_args.kwargs["source"].destination_id,
            self.destination_secondary.id,
        )
        self.assertEqual(prefs_mock.call_args.kwargs["target"].pk, target.pk)
        self.assertEqual(
            grants_mock.call_args.kwargs["source"].destination_id,
            self.destination_secondary.id,
        )
        self.assertEqual(grants_mock.call_args.kwargs["target"].pk, target.pk)

    def test_recipient_contact_for_projection_prefers_default_then_falls_back_to_first_active(self):
        organization = self._create_org("Projection Recipient Org")
        recipient_organization = self._create_recipient_organization(
            organization,
            self.destination_primary,
        )
        first_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_organization,
            contact=self._create_person(
                organization,
                first_name="Aicha",
                last_name="Diallo",
            ),
            is_active=True,
        )
        second_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_organization,
            contact=self._create_person(
                organization,
                first_name="Fatou",
                last_name="Traore",
            ),
            is_active=True,
        )
        link = ShipmentShipperRecipientLink.objects.create(
            shipper=self.shipper,
            recipient_organization=recipient_organization,
            is_active=True,
        )
        default_authorization = ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=second_contact,
            is_default=True,
            is_active=True,
        )

        self.assertEqual(_recipient_contact_for_projection(link), second_contact)

        default_authorization.is_active = False
        default_authorization.save(update_fields=["is_active"])

        self.assertEqual(_recipient_contact_for_projection(link), first_contact)

    def test_projection_candidate_for_link_covers_exact_name_stale_and_fallback_paths(self):
        recipient_org_contact = self._create_org("Projection Candidate Recipient")
        recipient_organization = self._create_recipient_organization(
            recipient_org_contact,
            self.destination_primary,
        )
        link = ShipmentShipperRecipientLink.objects.create(
            shipper=self.shipper,
            recipient_organization=recipient_organization,
            is_active=True,
        )

        exact = AssociationRecipient.objects.create(
            association_contact=self.shipper_contact,
            synced_contact=recipient_org_contact,
            destination=self.destination_primary,
            name="Exact Projection",
            structure_name="Exact Projection",
            city="Paris",
            country="France",
        )
        candidate, can_refresh = _projection_candidate_for_link(link)
        self.assertEqual((candidate, can_refresh), (exact, True))

        AssociationRecipient.objects.all().delete()
        name_match = AssociationRecipient.objects.create(
            association_contact=self.shipper_contact,
            synced_contact=None,
            destination=self.destination_primary,
            name="Name Match",
            structure_name=recipient_org_contact.name.upper(),
            city="Paris",
            country="France",
        )
        candidate, can_refresh = _projection_candidate_for_link(link)
        self.assertEqual((candidate, can_refresh), (name_match, True))

        AssociationRecipient.objects.all().delete()
        stale_contact = self._create_org("Projection Candidate Stale", is_active=False)
        stale = AssociationRecipient.objects.create(
            association_contact=self.shipper_contact,
            synced_contact=stale_contact,
            destination=self.destination_primary,
            name="Stale Match",
            structure_name="No Name Match",
            city="Paris",
            country="France",
        )
        candidate, can_refresh = _projection_candidate_for_link(link)
        self.assertEqual((candidate, can_refresh), (stale, True))

        AssociationRecipient.objects.all().delete()
        candidate, can_refresh = _projection_candidate_for_link(link)
        self.assertEqual((candidate, can_refresh), (None, True))

        fallback = AssociationRecipient.objects.create(
            association_contact=self.shipper_contact,
            synced_contact=None,
            destination=self.destination_primary,
            name="Fallback Projection",
            structure_name="Fallback Projection",
            city="Paris",
            country="France",
        )
        candidate, can_refresh = _projection_candidate_for_link(link)
        self.assertEqual((candidate, can_refresh), (fallback, True))

        AssociationRecipient.objects.create(
            association_contact=self.shipper_contact,
            synced_contact=None,
            destination=self.destination_primary,
            name="Ambiguous Projection",
            structure_name="Another Projection",
            city="Paris",
            country="France",
        )
        candidate, can_refresh = _projection_candidate_for_link(link)
        self.assertEqual((candidate, can_refresh), (None, False))

    def test_refresh_legacy_projections_dry_run_skips_non_refreshable_links(self):
        empty_org = self._create_org("Projection Empty Org")
        empty_recipient = self._create_recipient_organization(
            empty_org,
            self.destination_primary,
        )
        ShipmentShipperRecipientLink.objects.create(
            shipper=self.shipper,
            recipient_organization=empty_recipient,
            is_active=True,
        )

        ambiguous_org = self._create_org("Projection Ambiguous Org")
        ambiguous_recipient = self._create_recipient_organization(
            ambiguous_org,
            self.destination_primary,
        )
        ambiguous_person = self._create_person(
            ambiguous_org,
            first_name="Ambiguous",
            last_name="Person",
        )
        ShipmentRecipientContact.objects.create(
            recipient_organization=ambiguous_recipient,
            contact=ambiguous_person,
            is_active=True,
        )
        ambiguous_link = ShipmentShipperRecipientLink.objects.create(
            shipper=self.shipper,
            recipient_organization=ambiguous_recipient,
            is_active=True,
        )
        AssociationRecipient.objects.create(
            association_contact=self.shipper_contact,
            synced_contact=None,
            destination=self.destination_primary,
            name="Ambiguous One",
            structure_name="Ambiguous One",
            city="Paris",
            country="France",
        )
        AssociationRecipient.objects.create(
            association_contact=self.shipper_contact,
            synced_contact=None,
            destination=self.destination_primary,
            name="Ambiguous Two",
            structure_name="Ambiguous Two",
            city="Paris",
            country="France",
        )

        exact_org = self._create_org("Projection Exact Org")
        exact_org.addresses.create(
            address_line1="1 rue du refresh",
            city="Bamako",
            country="Mali",
            is_default=True,
        )
        exact_recipient = self._create_recipient_organization(
            exact_org,
            self.destination_primary,
        )
        exact_person = self._create_person(
            exact_org,
            first_name="Exact",
            last_name="Person",
            email="exact.person@example.org",
            phone="0102030405",
        )
        ShipmentRecipientContact.objects.create(
            recipient_organization=exact_recipient,
            contact=exact_person,
            is_active=True,
        )
        exact_link = ShipmentShipperRecipientLink.objects.create(
            shipper=self.shipper,
            recipient_organization=exact_recipient,
            is_active=True,
        )
        AssociationRecipient.objects.create(
            association_contact=self.shipper_contact,
            synced_contact=exact_org,
            destination=self.destination_primary,
            name="Exact Refresh",
            structure_name=exact_org.name,
            city="Paris",
            country="France",
        )

        refreshed = _refresh_legacy_projections(apply=False)

        self.assertEqual(refreshed, 1)
        self.assertIsNotNone(_recipient_contact_for_projection(exact_link))

    def test_rebuild_recipient_party_graph_dry_run_summarizes_helper_results(self):
        duplicate_scopes = [
            {"recipient_organization_ids": [1, 2]},
            {"recipient_organization_ids": [3]},
        ]
        with (
            mock.patch(
                "wms.parties.rebuild._duplicate_recipient_organization_scopes",
                return_value=duplicate_scopes,
            ),
            mock.patch(
                "wms.parties.rebuild.ShipmentRecipientOrganization.objects.count",
                return_value=7,
            ),
            mock.patch(
                "wms.parties.rebuild._ensure_shipper_portal_grants",
                return_value=4,
            ) as grants_mock,
            mock.patch(
                "wms.parties.rebuild._refresh_legacy_projections",
                return_value=6,
            ) as projections_mock,
        ):
            summary = rebuild_recipient_party_graph(apply=False)

        self.assertEqual(summary["mode"], "DRY RUN")
        self.assertEqual(summary["recipient_organizations_scanned"], 7)
        self.assertEqual(summary["duplicate_scopes"], duplicate_scopes)
        self.assertEqual(summary["recipient_organizations_merged"], 1)
        self.assertEqual(summary["shipper_grants_created"], 4)
        self.assertEqual(summary["legacy_projections_refreshed"], 6)
        grants_mock.assert_called_once_with(apply=False)
        projections_mock.assert_called_once_with(apply=False)
