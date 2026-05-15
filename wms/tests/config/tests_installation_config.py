from __future__ import annotations

import dataclasses
import importlib.util
import json
import os
import subprocess
import sys
import typing

from django.test import SimpleTestCase, override_settings


class InstallationConfigTests(SimpleTestCase):
    def test_public_api_exposes_expected_sections_and_attributes(self):
        from wms.config import get_installation_config

        config = get_installation_config()

        self.assertTrue(dataclasses.is_dataclass(config))
        self.assertEqual(
            set(config.__dataclass_fields__),
            {
                "identity",
                "vocabulary",
                "features",
                "integrations",
                "notifications",
                "references",
            },
        )
        self.assertEqual(
            list(config.identity.__dataclass_fields__),
            [
                "organization_full_name",
                "organization_short_name",
                "application_display_name",
                "contact_email",
                "sku_prefix",
                "contact_reference_prefix",
                "product_display_name",
                "organization_brand_name",
            ],
        )
        self.assertEqual(
            set(config.vocabulary.__dataclass_fields__),
            {
                "organization_label",
                "partner_label",
                "portal_partner_label",
                "volunteer_label",
                "shipper_label",
                "recipient_label",
            },
        )
        self.assertEqual(
            set(config.features.__dataclass_fields__),
            {
                "portal_enabled",
                "planning_enabled",
                "billing_enabled",
                "print_pack_enabled",
                "document_scan_enabled",
                "external_flight_provider_enabled",
                "email_enabled",
            },
        )
        self.assertEqual(
            set(config.integrations.__dataclass_fields__),
            {
                "email",
                "pdf_conversion",
                "document_scan",
                "flight_provider",
                "local_helper",
            },
        )
        self.assertEqual(
            set(config.notifications.__dataclass_fields__),
            {"email_subject_prefix", "email_sender_name"},
        )
        self.assertEqual(
            set(config.references.__dataclass_fields__),
            {
                "contact_identifier_generated_prefix",
                "contact_identifier_label",
                "tracking_contact_identifier_label",
            },
        )

    @override_settings(
        ORG_NAME="Aviation Sans Frontieres",
        ORG_SHORT_NAME="ASF",
        SKU_PREFIX="ASF",
        DOCUMENT_SCAN_BACKEND="clamav",
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        BREVO_SENDER_NAME="",
        PLANNING_FLIGHT_API_PROVIDER="airfrance_klm",
        GRAPH_TENANT_ID="",
        GRAPH_CLIENT_ID="",
        GRAPH_CLIENT_SECRET="",
        GRAPH_DRIVE_ID="",
    )
    def test_current_asf_defaults_are_preserved_and_reflect_settings(self):
        from wms.config import get_installation_config

        config = get_installation_config()

        self.assertEqual(config.identity.organization_full_name, "Aviation Sans Frontieres")
        self.assertEqual(config.identity.organization_short_name, "ASF")
        self.assertEqual(config.identity.application_display_name, "ASF-WMS")
        self.assertEqual(config.identity.contact_email, "messmed@aviation-sans-frontieres-fr.org")
        self.assertEqual(config.identity.sku_prefix, "ASF")
        self.assertEqual(config.identity.contact_reference_prefix, "ASF")
        self.assertEqual(config.references.contact_identifier_generated_prefix, "ASF-C")
        self.assertEqual(config.references.contact_identifier_label, "ASF ID")
        self.assertEqual(config.references.tracking_contact_identifier_label, "ID ASF")
        self.assertEqual(config.identity.product_display_name, "ASF WMS")
        self.assertEqual(config.identity.organization_brand_name, "ASF")
        self.assertEqual(config.vocabulary.partner_label, "partenaire")
        self.assertEqual(config.vocabulary.portal_partner_label, "association")
        self.assertEqual(config.vocabulary.volunteer_label, "benevole")
        self.assertEqual(config.notifications.email_subject_prefix, "ASF WMS -")
        self.assertEqual(config.notifications.email_sender_name, "ASF WMS")
        self.assertEqual(config.integrations.email.provider, "brevo_with_smtp_fallback")
        self.assertTrue(config.integrations.email.enabled)
        self.assertEqual(config.integrations.pdf_conversion.provider, "microsoft_graph")
        self.assertTrue(config.integrations.pdf_conversion.enabled)
        self.assertEqual(config.integrations.document_scan.provider, "clamav")
        self.assertEqual(config.integrations.flight_provider.provider, "airfrance_klm")

    def test_public_values_have_stable_expected_types(self):
        from wms.config import get_installation_config

        config = get_installation_config()

        for section_name in ("identity", "vocabulary", "notifications", "references"):
            section = getattr(config, section_name)
            for field_name in section.__dataclass_fields__:
                self.assertIsInstance(getattr(section, field_name), str)

        for field_name in config.features.__dataclass_fields__:
            self.assertIsInstance(getattr(config.features, field_name), bool)

        for field_name in config.integrations.__dataclass_fields__:
            descriptor = getattr(config.integrations, field_name)
            self.assertIsInstance(descriptor.capability, str)
            self.assertIsInstance(descriptor.provider, str)
            self.assertIsInstance(descriptor.enabled, bool)

    def test_configuration_objects_are_read_only(self):
        from wms.config import get_installation_config

        config = get_installation_config()

        with self.assertRaises(dataclasses.FrozenInstanceError):
            config.identity.organization_short_name = "OTHER"

        with self.assertRaises(dataclasses.FrozenInstanceError):
            config.notifications.email_subject_prefix = "OTHER -"

        with self.assertRaises(dataclasses.FrozenInstanceError):
            config.references.contact_identifier_generated_prefix = "OTHER-C"

        with self.assertRaises(dataclasses.FrozenInstanceError):
            config.references.contact_identifier_label = "Contact ref"

        with self.assertRaises(dataclasses.FrozenInstanceError):
            config.references.tracking_contact_identifier_label = "Tracking ref"

    @override_settings(
        CONTACT_IDENTIFIER_GENERATED_PREFIX="FBN-C",
        CONTACT_IDENTIFIER_LABEL="Contact ref.",
        TRACKING_CONTACT_IDENTIFIER_LABEL="Référence suivi",
    )
    def test_references_fields_reflect_installation_overrides(self):
        from wms.config import get_installation_config

        config = get_installation_config()

        self.assertEqual(config.references.contact_identifier_generated_prefix, "FBN-C")
        self.assertEqual(config.references.contact_identifier_label, "Contact ref.")
        self.assertEqual(config.references.tracking_contact_identifier_label, "Référence suivi")

    @override_settings(BREVO_SENDER_NAME=" Client Sender ")
    def test_email_sender_name_reflects_existing_brevo_sender_name_setting(self):
        from wms.config import get_installation_config

        config = get_installation_config()

        self.assertEqual(config.notifications.email_sender_name, "Client Sender")

    @override_settings(BREVO_SENDER_NAME="")
    def test_email_sender_name_falls_back_when_blank(self):
        from wms.config import get_installation_config

        config = get_installation_config()

        self.assertEqual(config.notifications.email_sender_name, "ASF WMS")

    @override_settings(BREVO_SENDER_NAME="   ")
    def test_email_sender_name_falls_back_when_whitespace_only(self):
        from wms.config import get_installation_config

        config = get_installation_config()

        self.assertEqual(config.notifications.email_sender_name, "ASF WMS")

    def test_feature_flags_expose_stable_boolean_defaults(self):
        from wms.config import get_installation_config

        features = get_installation_config().features

        self.assertTrue(features.portal_enabled)
        self.assertTrue(features.planning_enabled)
        self.assertTrue(features.billing_enabled)
        self.assertTrue(features.print_pack_enabled)
        self.assertTrue(features.document_scan_enabled)
        self.assertTrue(features.external_flight_provider_enabled)
        self.assertTrue(features.email_enabled)

    def test_feature_flags_are_coherent_with_integration_descriptors(self):
        from wms.config import get_installation_config

        config = get_installation_config()

        self.assertIs(config.features.email_enabled, config.integrations.email.enabled)
        self.assertIs(
            config.features.document_scan_enabled,
            config.integrations.document_scan.enabled,
        )
        self.assertIs(
            config.features.print_pack_enabled,
            config.integrations.pdf_conversion.enabled,
        )
        self.assertIs(
            config.features.external_flight_provider_enabled,
            config.integrations.flight_provider.enabled,
        )

    def test_import_is_leaf_dependency_without_runtime_modules(self):
        script = """
import json
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "asf_wms.settings")

from wms.config import get_installation_config

get_installation_config()

forbidden_prefixes = (
    "wms.admin",
    "wms.api",
    "wms.apis",
    "wms.application",
    "wms.forms",
    "wms.jobs",
    "wms.models",
    "wms.models_domain",
    "wms.policies",
    "wms.services",
    "wms.views",
)
loaded = sorted(
    name
    for name in sys.modules
    if name in forbidden_prefixes or name.startswith(forbidden_prefixes)
)
print(json.dumps(loaded))
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            env={
                **os.environ,
                "DJANGO_SECRET_KEY": (
                    "local-config-test-key-not-production-"
                    "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                ),
            },
            text=True,
        )

        self.assertEqual(json.loads(result.stdout), [])

    def test_config_package_does_not_create_migrations(self):
        self.assertIsNone(importlib.util.find_spec("wms.config.migrations"))

    def test_import_and_access_do_not_require_database_access(self):
        from wms.config import get_installation_config

        config = get_installation_config()

        self.assertEqual(config.identity.organization_short_name, "ASF")

    @override_settings(
        PRODUCT_DISPLAY_NAME=" Client Operations ",
        ORG_BRAND_NAME=" ClientOrg ",
    )
    def test_shell_identity_fields_reflect_installation_overrides(self):
        from wms.config import get_installation_config

        config = get_installation_config()

        self.assertEqual(config.identity.product_display_name, "Client Operations")
        self.assertEqual(config.identity.organization_brand_name, "ClientOrg")

    def test_public_sentinel_for_expected_shape(self):
        from wms.config.installation import (
            InstallationConfig,
            InstallationFeatureFlags,
            InstallationIdentity,
            InstallationIntegrations,
            InstallationNotifications,
            InstallationReferences,
            InstallationVocabulary,
            IntegrationDescriptor,
            get_installation_config,
        )

        expected = {
            InstallationConfig: {
                "identity": InstallationIdentity,
                "vocabulary": InstallationVocabulary,
                "features": InstallationFeatureFlags,
                "integrations": InstallationIntegrations,
                "notifications": InstallationNotifications,
                "references": InstallationReferences,
            },
            InstallationIdentity: {
                "organization_full_name": str,
                "organization_short_name": str,
                "application_display_name": str,
                "contact_email": str,
                "sku_prefix": str,
                "contact_reference_prefix": str,
                "product_display_name": str,
                "organization_brand_name": str,
            },
            InstallationVocabulary: {
                "organization_label": str,
                "partner_label": str,
                "portal_partner_label": str,
                "volunteer_label": str,
                "shipper_label": str,
                "recipient_label": str,
            },
            InstallationFeatureFlags: {
                "portal_enabled": bool,
                "planning_enabled": bool,
                "billing_enabled": bool,
                "print_pack_enabled": bool,
                "document_scan_enabled": bool,
                "external_flight_provider_enabled": bool,
                "email_enabled": bool,
            },
            IntegrationDescriptor: {
                "capability": str,
                "provider": str,
                "enabled": bool,
            },
            InstallationIntegrations: {
                "email": IntegrationDescriptor,
                "pdf_conversion": IntegrationDescriptor,
                "document_scan": IntegrationDescriptor,
                "flight_provider": IntegrationDescriptor,
                "local_helper": IntegrationDescriptor,
            },
            InstallationNotifications: {
                "email_subject_prefix": str,
                "email_sender_name": str,
            },
            InstallationReferences: {
                "contact_identifier_generated_prefix": str,
                "contact_identifier_label": str,
                "tracking_contact_identifier_label": str,
            },
        }

        for cls, fields in expected.items():
            self.assertEqual(typing.get_type_hints(cls), fields)

        self.assertIsInstance(get_installation_config(), InstallationConfig)
