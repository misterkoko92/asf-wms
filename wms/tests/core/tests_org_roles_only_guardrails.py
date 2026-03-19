from pathlib import Path

from django.test import SimpleTestCase

REPO_ROOT = Path(__file__).resolve().parents[3]


class OrgRolesOnlyGuardrailsTests(SimpleTestCase):
    def test_known_runtime_files_do_not_keep_legacy_contact_symbols(self):
        forbidden_patterns_by_file = {
            "contacts/models.py": [
                "class ContactTag",
                "destination = models.ForeignKey(",
                "destinations = models.ManyToManyField(",
                "linked_shippers = models.ManyToManyField(",
                "tags = models.ManyToManyField(",
            ],
            "contacts/destination_scope.py": [
                "contact.destinations",
                "contact.destination_id",
            ],
            "contacts/correspondent_recipient_promotion.py": [
                "ContactTag",
                "TAG_CORRESPONDENT",
                "TAG_RECIPIENT",
                "contact_destination_ids",
                "set_contact_destination_scope",
            ],
            "wms/contact_filters.py": [
                "filter_contacts_for_destination",
                "filter_recipients_for_shipper",
                "contacts_with_tags(",
            ],
            "wms/view_utils.py": [
                "contacts_with_tags(",
            ],
            "wms/portal_recipient_sync.py": [
                "_find_legacy_synced_contact",
                "_find_synced_contact_by_marker",
                "PORTAL_RECIPIENT_SOURCE_PREFIX",
                "_source_marker(",
                "notes__startswith",
            ],
            "wms/import_services_contacts.py": [
                "ContactTag",
                "build_contact_tags",
                "DESTINATIONS_KEYS",
                "LINKED_SHIPPERS_KEYS",
            ],
            "wms/scan_import_handlers.py": [
                "ContactTag",
                '"contact_tags"',
            ],
            "wms/exports.py": [
                '"destinations"',
                '"linked_shippers"',
            ],
            "wms/admin_organization_roles_review.py": [
                "legacy_contact",
                "linked_shippers",
                "contacts_with_tags(",
            ],
            "wms/models_domain/portal.py": [
                "legacy_contact = models.ForeignKey(",
            ],
        }

        violations = []
        for relative_path, patterns in forbidden_patterns_by_file.items():
            file_path = REPO_ROOT / relative_path
            if not file_path.exists():
                continue
            contents = file_path.read_text(encoding="utf-8")
            for pattern in patterns:
                if pattern in contents:
                    violations.append(f"{relative_path}: {pattern}")

        self.assertEqual(
            violations,
            [],
            "Legacy contact runtime symbols still present:\n- " + "\n- ".join(violations),
        )
