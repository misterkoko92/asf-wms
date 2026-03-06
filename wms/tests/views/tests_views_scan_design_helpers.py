from types import SimpleNamespace

from django.test import SimpleTestCase

from wms.forms_scan_design import ScanDesignSettingsForm
from wms.views_scan_design import (
    _empty_preview_values,
    _preview_values_from_post,
    _resolve_selected_style_preset,
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

    def test_resolve_selected_style_preset_falls_back_to_default(self):
        runtime_settings = SimpleNamespace(design_selected_preset="missing")
        preset_map = {
            "wms-default": {"key": "wms-default"},
            "wms-rect": {"key": "wms-rect"},
        }

        selected = _resolve_selected_style_preset(runtime_settings, preset_map)

        self.assertEqual(selected, "wms-default")

    def test_resolve_selected_style_preset_falls_back_to_first_when_no_default(self):
        runtime_settings = SimpleNamespace(design_selected_preset="missing")
        preset_map = {
            "custom-a": {"key": "custom-a"},
            "custom-b": {"key": "custom-b"},
        }

        selected = _resolve_selected_style_preset(runtime_settings, preset_map)

        self.assertEqual(selected, "custom-a")
