from types import SimpleNamespace
from unittest import mock

from django.test import TestCase

from contacts.asf_ids import build_generated_asf_id


class ContactAsfIdsTests(TestCase):
    def test_build_generated_asf_id_uses_reserved_namespace(self):
        self.assertEqual(build_generated_asf_id(1), "ASF-C-00000001")
        self.assertEqual(build_generated_asf_id(42), "ASF-C-00000042")

    def test_build_generated_asf_id_uses_installation_reference_prefix(self):
        installation = SimpleNamespace(
            references=SimpleNamespace(contact_identifier_generated_prefix="FBN-C")
        )

        with mock.patch(
            "contacts.asf_ids.get_installation_config",
            return_value=installation,
        ):
            self.assertEqual(build_generated_asf_id(1), "FBN-C-00000001")

    def test_build_generated_asf_id_rejects_invalid_installation_prefixes(self):
        invalid_prefixes = ["", "ASF C", " ASF-C", "ASF-C ", "-ASF-C", "ASF-C-"]

        for invalid_prefix in invalid_prefixes:
            installation = SimpleNamespace(
                references=SimpleNamespace(contact_identifier_generated_prefix=invalid_prefix)
            )
            with self.subTest(prefix=invalid_prefix):
                with mock.patch(
                    "contacts.asf_ids.get_installation_config",
                    return_value=installation,
                ):
                    with self.assertRaises(ValueError):
                        build_generated_asf_id(1)

    def test_build_generated_asf_id_rejects_missing_pk(self):
        with self.assertRaises(ValueError):
            build_generated_asf_id(None)
