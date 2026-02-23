from django.test import SimpleTestCase

from api.v1.serializers import UiPrintTemplateMutationSerializer


class UiSerializerContractTests(SimpleTestCase):
    def test_print_template_mutation_defaults_to_save_with_empty_layout(self):
        serializer = UiPrintTemplateMutationSerializer(data={})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["action"], "save")
        self.assertEqual(serializer.validated_data["layout"], {})

    def test_print_template_mutation_accepts_object_layout(self):
        serializer = UiPrintTemplateMutationSerializer(
            data={
                "action": "save",
                "layout": {"blocks": [{"id": "b1", "type": "text"}]},
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["action"], "save")
        self.assertEqual(serializer.validated_data["layout"]["blocks"][0]["id"], "b1")

    def test_print_template_mutation_rejects_non_object_layout(self):
        serializer = UiPrintTemplateMutationSerializer(
            data={
                "action": "save",
                "layout": ["invalid"],
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("layout", serializer.errors)

    def test_print_template_reset_forces_empty_layout(self):
        serializer = UiPrintTemplateMutationSerializer(
            data={
                "action": "reset",
                "layout": {"blocks": [{"id": "ignored"}]},
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["action"], "reset")
        self.assertEqual(serializer.validated_data["layout"], {})
