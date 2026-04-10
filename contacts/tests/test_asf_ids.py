from django.test import TestCase

from contacts.asf_ids import build_generated_asf_id


class ContactAsfIdsTests(TestCase):
    def test_build_generated_asf_id_uses_reserved_namespace(self):
        self.assertEqual(build_generated_asf_id(42), "ASF-C-00000042")

    def test_build_generated_asf_id_rejects_missing_pk(self):
        with self.assertRaises(ValueError):
            build_generated_asf_id(None)
