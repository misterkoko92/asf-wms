from types import SimpleNamespace

from django.test import SimpleTestCase

from wms.forms_scan_design import ScanDesignSettingsForm
from wms.views_scan_design import (
    _empty_preview_values,
    _preview_values_from_post,
)


class ScanDesignHelpersTests(SimpleTestCase):
    def test_empty_preview_values_contains_all_preview_fields(self):
        preview_values = _empty_preview_values()

        self.assertEqual(set(preview_values.keys()), set(ScanDesignSettingsForm.PREVIEW_FIELDS))
        self.assertTrue(all(value == "" for value in preview_values.values()))

    def test_preview_values_from_post_prefers_cleaned_non_empty_values(self):
        form = SimpleNamespace(
            cleaned_data={
                "design_color_primary": "#112233",
                "design_font_h1": "",
            }
        )
        post_data = {
            "design_color_primary": "#abcdef",
            "design_font_h1": "Manrope",
        }

        preview_values = _preview_values_from_post(form, post_data)

        self.assertEqual(preview_values["design_color_primary"], "#112233")
        self.assertEqual(preview_values["design_font_h1"], "Manrope")
