from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

ASF_ORG_FULL_NAME = "Aviation Sans Frontieres"
ASF_ORG_SHORT_NAME = "ASF"
ASF_APPLICATION_DISPLAY_NAME = "ASF-WMS"
ASF_PRODUCT_DISPLAY_NAME = "ASF WMS"
ASF_ORG_BRAND_NAME = "ASF"
ASF_CONTACT_EMAIL = "messmed@aviation-sans-frontieres-fr.org"
ASF_SKU_PREFIX = "ASF"
ASF_CONTACT_IDENTIFIER_GENERATED_PREFIX = "ASF-C"
ASF_CONTACT_IDENTIFIER_LABEL = "ASF ID"
ASF_TRACKING_CONTACT_IDENTIFIER_LABEL = "ID ASF"
ASF_EMAIL_SUBJECT_PREFIX = "ASF WMS -"
ASF_EMAIL_SENDER_NAME = "ASF WMS"
ASF_PRINT_HTML_FOOTER_PUBLIC_CONTACT_LINE = (
    "https://aviation-sans-frontieres.org/messmed // " "messmed@aviation-sans-frontières-fr.org"
)
ASF_PRINT_HTML_FOOTER_HEADQUARTERS_LINE = (
    "Siège: Bat 293, Porte 1150, Orly Fret 768 - "
    "94398 Orly Aérogare Cedex - Tel: (33) 1 49 75 74 36"
)
ASF_PRINT_HTML_FOOTER_WAREHOUSE_LINE = (
    "Magasin: Bat. 7200, Porte 2D520, rue de la Remise - "
    "95700 ROISSY en France - Tél: (33) 1 74 25 03 22"
)
ASF_PRINT_HTML_FOOTER_LEGAL_NOTICE_LINE = (
    "Association reconnue d'utilité publique par décret du 12 novembre 1993"
)
_MISSING_SETTING = object()

_PLACEHOLDER_VALUES = {
    "",
    "contact@example.com",
    "no-reply@example.com",
    "ORG_NAME",
    "ORG_SHORT_NAME",
    "ORG_CONTACT",
}


@dataclass(frozen=True)
class InstallationIdentity:
    organization_full_name: str
    organization_short_name: str
    application_display_name: str
    contact_email: str
    sku_prefix: str
    contact_reference_prefix: str
    product_display_name: str
    organization_brand_name: str


@dataclass(frozen=True)
class InstallationVocabulary:
    organization_label: str
    partner_label: str
    portal_partner_label: str
    volunteer_label: str
    shipper_label: str
    recipient_label: str


@dataclass(frozen=True)
class InstallationFeatureFlags:
    """Installation-level feature flags have two intentional categories.

    Module-level flags (portal, planning, billing) are direct declarations that
    a product module is part of the installation. They are not derived from an
    integration descriptor.

    Capability-derived flags (email, document scan, print pack, external flight
    provider) must stay aligned with their matching IntegrationDescriptor.enabled
    value. get_installation_config() enforces this by deriving them at
    construction time. Preserve the distinction: new module flags do not require
    descriptors, while new capability-derived flags require both a descriptor and
    construction-time derivation.
    """

    portal_enabled: bool
    planning_enabled: bool
    billing_enabled: bool
    print_pack_enabled: bool
    document_scan_enabled: bool
    external_flight_provider_enabled: bool
    email_enabled: bool


@dataclass(frozen=True)
class IntegrationDescriptor:
    capability: str
    provider: str
    enabled: bool


@dataclass(frozen=True)
class InstallationIntegrations:
    email: IntegrationDescriptor
    pdf_conversion: IntegrationDescriptor
    document_scan: IntegrationDescriptor
    flight_provider: IntegrationDescriptor
    local_helper: IntegrationDescriptor


@dataclass(frozen=True)
class InstallationNotifications:
    email_subject_prefix: str
    email_sender_name: str


@dataclass(frozen=True)
class InstallationPrint:
    html_footer_public_contact_line: str
    html_footer_headquarters_line: str
    html_footer_warehouse_line: str
    html_footer_legal_notice_line: str


@dataclass(frozen=True)
class InstallationReferences:
    contact_identifier_generated_prefix: str
    contact_identifier_label: str
    tracking_contact_identifier_label: str


@dataclass(frozen=True)
class InstallationConfig:
    identity: InstallationIdentity
    vocabulary: InstallationVocabulary
    features: InstallationFeatureFlags
    integrations: InstallationIntegrations
    notifications: InstallationNotifications
    references: InstallationReferences
    print: InstallationPrint


def get_installation_config() -> InstallationConfig:
    """Return the current read-only installation configuration snapshot."""

    identity = _build_identity()
    integrations = _build_integrations()

    return InstallationConfig(
        identity=identity,
        vocabulary=InstallationVocabulary(
            organization_label="organisation",
            partner_label="partenaire",
            portal_partner_label="association",
            volunteer_label="benevole",
            shipper_label="expediteur",
            recipient_label="destinataire",
        ),
        features=InstallationFeatureFlags(
            portal_enabled=True,
            planning_enabled=True,
            billing_enabled=True,
            print_pack_enabled=integrations.pdf_conversion.enabled,
            document_scan_enabled=integrations.document_scan.enabled,
            external_flight_provider_enabled=integrations.flight_provider.enabled,
            email_enabled=integrations.email.enabled,
        ),
        integrations=integrations,
        notifications=InstallationNotifications(
            email_subject_prefix=ASF_EMAIL_SUBJECT_PREFIX,
            email_sender_name=_setting_text("BREVO_SENDER_NAME", ASF_EMAIL_SENDER_NAME),
        ),
        references=InstallationReferences(
            contact_identifier_generated_prefix=_raw_setting_text(
                "CONTACT_IDENTIFIER_GENERATED_PREFIX",
                ASF_CONTACT_IDENTIFIER_GENERATED_PREFIX,
            ),
            contact_identifier_label=_raw_setting_text(
                "CONTACT_IDENTIFIER_LABEL",
                ASF_CONTACT_IDENTIFIER_LABEL,
            ),
            tracking_contact_identifier_label=_raw_setting_text(
                "TRACKING_CONTACT_IDENTIFIER_LABEL",
                ASF_TRACKING_CONTACT_IDENTIFIER_LABEL,
            ),
        ),
        print=InstallationPrint(
            html_footer_public_contact_line=_setting_text(
                "PRINT_HTML_FOOTER_PUBLIC_CONTACT_LINE",
                ASF_PRINT_HTML_FOOTER_PUBLIC_CONTACT_LINE,
            ),
            html_footer_headquarters_line=_setting_text(
                "PRINT_HTML_FOOTER_HEADQUARTERS_LINE",
                ASF_PRINT_HTML_FOOTER_HEADQUARTERS_LINE,
            ),
            html_footer_warehouse_line=_setting_text(
                "PRINT_HTML_FOOTER_WAREHOUSE_LINE",
                ASF_PRINT_HTML_FOOTER_WAREHOUSE_LINE,
            ),
            html_footer_legal_notice_line=_setting_text(
                "PRINT_HTML_FOOTER_LEGAL_NOTICE_LINE",
                ASF_PRINT_HTML_FOOTER_LEGAL_NOTICE_LINE,
            ),
        ),
    )


def _build_identity() -> InstallationIdentity:
    sku_prefix = _setting_text("SKU_PREFIX", ASF_SKU_PREFIX)
    contact_email = _first_setting_text(
        "ORG_CONTACT",
        "BREVO_REPLY_TO_EMAIL",
        "BREVO_SENDER_EMAIL",
        "DEFAULT_FROM_EMAIL",
        default=ASF_CONTACT_EMAIL,
    )

    return InstallationIdentity(
        organization_full_name=_setting_text("ORG_NAME", ASF_ORG_FULL_NAME),
        organization_short_name=_setting_text("ORG_SHORT_NAME", ASF_ORG_SHORT_NAME),
        application_display_name=_setting_text(
            "APPLICATION_DISPLAY_NAME",
            ASF_APPLICATION_DISPLAY_NAME,
        ),
        contact_email=contact_email,
        sku_prefix=sku_prefix,
        contact_reference_prefix=_setting_text(
            "CONTACT_REFERENCE_PREFIX",
            sku_prefix,
        ),
        product_display_name=_setting_text(
            "PRODUCT_DISPLAY_NAME",
            ASF_PRODUCT_DISPLAY_NAME,
        ),
        organization_brand_name=_setting_text(
            "ORG_BRAND_NAME",
            ASF_ORG_BRAND_NAME,
        ),
    )


def _build_integrations() -> InstallationIntegrations:
    email_provider = _email_provider()
    pdf_provider = _pdf_conversion_provider()
    document_scan_provider = _setting_text("DOCUMENT_SCAN_BACKEND", "clamav").lower()
    flight_provider = _setting_text("PLANNING_FLIGHT_API_PROVIDER", "airfrance_klm")

    return InstallationIntegrations(
        email=IntegrationDescriptor(
            capability="email",
            provider=email_provider,
            enabled=True,
        ),
        pdf_conversion=IntegrationDescriptor(
            capability="pdf_conversion",
            provider=pdf_provider,
            enabled=True,
        ),
        document_scan=IntegrationDescriptor(
            capability="document_scan",
            provider=document_scan_provider,
            enabled=document_scan_provider not in {"", "disabled"},
        ),
        flight_provider=IntegrationDescriptor(
            capability="external_flight_provider",
            provider=flight_provider,
            enabled=bool(flight_provider),
        ),
        local_helper=IntegrationDescriptor(
            capability="local_helper",
            provider=_setting_text("LOCAL_HELPER_PROVIDER", "planning_comm_helper"),
            enabled=True,
        ),
    )


def _email_provider() -> str:
    return "brevo_with_smtp_fallback"


def _pdf_conversion_provider() -> str:
    return "microsoft_graph"


def _first_setting_text(*names: str, default: str) -> str:
    for name in names:
        value = _setting_text(name, "")
        if value:
            return value
    return default


def _setting_text(name: str, default: str) -> str:
    value = getattr(settings, name, default)
    if value is None:
        return default
    text = str(value).strip()
    if text in _PLACEHOLDER_VALUES:
        return default
    return text


def _raw_setting_text(name: str, default: str) -> str:
    value = getattr(settings, name, _MISSING_SETTING)
    if value is _MISSING_SETTING:
        return default
    return str(value)


__all__ = [
    "InstallationConfig",
    "InstallationFeatureFlags",
    "InstallationIdentity",
    "InstallationIntegrations",
    "InstallationNotifications",
    "InstallationPrint",
    "InstallationReferences",
    "InstallationVocabulary",
    "IntegrationDescriptor",
    "get_installation_config",
]
