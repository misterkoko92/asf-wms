from unittest import mock

from django.test import TestCase

from wms.models import PrintTemplate
from wms import print_renderer


class PrintRendererTests(TestCase):
    def test_render_template_string_renders_context(self):
        rendered = print_renderer._render_template_string(
            "Ref {{ shipment_ref }}",
            {"shipment_ref": "SHP-001"},
        )
        self.assertEqual(rendered, "Ref SHP-001")

    def test_build_style_builds_css_rules_and_handles_empty(self):
        self.assertEqual(print_renderer._build_style(None), "")

        style = print_renderer._build_style(
            {
                "border": True,
                "padding": "2mm",
                "align": "center",
                "font_size": "12pt",
                "line_height": "1.4",
                "color": "#111",
                "background": "#eee",
                "font_weight": "700",
            }
        )
        self.assertIn("border:1px solid #000;", style)
        self.assertIn("padding:2mm;", style)
        self.assertIn("text-align:center;", style)
        self.assertIn("font-size:12pt;", style)
        self.assertIn("line-height:1.4;", style)
        self.assertIn("color:#111;", style)
        self.assertIn("background:#eee;", style)
        self.assertIn("font-weight:700;", style)

    def test_render_text_block_defaults_to_div_and_renders_template(self):
        html = print_renderer._render_text_block(
            {
                "type": "text",
                "text": "Bonjour {{ name }}",
                "style": {"padding": "1mm"},
            },
            {"name": "ASF"},
        )
        self.assertIn("<div", html)
        self.assertIn("Bonjour ASF", html)
        self.assertIn('style="padding:1mm;"', html)

        html_with_tag = print_renderer._render_text_block(
            {"type": "text", "tag": "h1", "text": "Titre"},
            {},
        )
        self.assertIn("<h1", html_with_tag)
        self.assertIn("</h1>", html_with_tag)

    def test_render_text_block_invalid_tag_falls_back_to_div(self):
        html = print_renderer._render_text_block(
            {"type": "text", "tag": "script", "text": "Titre"},
            {},
        )
        self.assertIn("<div", html)
        self.assertNotIn("<script", html)

    def test_render_block_summary_triplet(self):
        with mock.patch(
            "wms.print_renderer.render_to_string",
            return_value="summary",
        ) as render_mock:
            result = print_renderer._render_block(
                {"type": "summary_triplet"},
                {"k": "v"},
            )
        self.assertEqual(result, "summary")
        render_mock.assert_called_once_with("print/blocks/summary_triplet.html", {"k": "v"})

    def test_render_block_text_delegates_to_text_renderer(self):
        with mock.patch(
            "wms.print_renderer._render_text_block",
            return_value="text-block",
        ) as text_block_mock:
            result = print_renderer._render_block(
                {"type": "text", "text": "Hello"},
                {"name": "ASF"},
            )
        self.assertEqual(result, "text-block")
        text_block_mock.assert_called_once_with(
            {"type": "text", "text": "Hello"},
            {"name": "ASF"},
        )

    def test_render_block_contacts_row_sets_defaults(self):
        block = {
            "type": "contacts_row",
            "labels": {"company": "Organisation"},
            "style": {"padding": "2mm"},
        }
        with mock.patch(
            "wms.print_renderer.render_to_string",
            return_value="contacts",
        ) as render_mock:
            result = print_renderer._render_block(block, {"shipment_ref": "SHP-001"})
        self.assertEqual(result, "contacts")
        template_name, payload = render_mock.call_args.args
        self.assertEqual(template_name, "print/blocks/contacts_row.html")
        self.assertEqual(payload["block"]["title_shipper"], "EXPEDITEUR")
        self.assertTrue(payload["block"]["show_email"])
        self.assertEqual(payload["labels"]["company"], "Organisation")
        self.assertEqual(payload["labels"]["person"], "Nom")
        self.assertEqual(payload["style"], {"padding": "2mm"})
        self.assertEqual(payload["shipment_ref"], "SHP-001")

    def test_render_block_signatures(self):
        with mock.patch(
            "wms.print_renderer.render_to_string",
            return_value="sig",
        ) as render_mock:
            result = print_renderer._render_block(
                {"type": "signatures"},
                {"x": 1},
            )
        self.assertEqual(result, "sig")
        template_name, payload = render_mock.call_args.args
        self.assertEqual(template_name, "print/blocks/signatures.html")
        self.assertEqual(payload["block"]["type"], "signatures")
        self.assertEqual(payload["x"], 1)

    def test_render_block_table_items_aggregate_mode_replaces_item_rows(self):
        with mock.patch(
            "wms.print_renderer.render_to_string",
            return_value="items",
        ) as render_mock:
            result = print_renderer._render_block(
                {"type": "table_items", "mode": "aggregate"},
                {"aggregate_rows": [{"sku": "A"}], "item_rows": [{"sku": "OLD"}]},
            )
        self.assertEqual(result, "items")
        template_name, payload = render_mock.call_args.args
        self.assertEqual(template_name, "print/blocks/table_items.html")
        self.assertEqual(payload["item_rows"], [{"sku": "A"}])

    def test_render_block_table_items_without_aggregate_rows_keeps_context(self):
        with mock.patch(
            "wms.print_renderer.render_to_string",
            return_value="items",
        ) as render_mock:
            result = print_renderer._render_block(
                {"type": "table_items", "mode": "aggregate"},
                {"item_rows": [{"sku": "OLD"}]},
            )
        self.assertEqual(result, "items")
        _, payload = render_mock.call_args.args
        self.assertEqual(payload["item_rows"], [{"sku": "OLD"}])

    def test_render_block_renders_specialized_templates(self):
        block_types = [
            ("table_cartons", "print/blocks/table_cartons.html"),
            ("label_city", "print/blocks/label_city.html"),
            ("label_iata", "print/blocks/label_iata.html"),
            ("label_footer", "print/blocks/label_footer.html"),
            ("product_label", "print/blocks/product_label.html"),
            ("product_qr_label", "print/blocks/product_qr_label.html"),
        ]
        for block_type, template_name in block_types:
            with self.subTest(block_type=block_type):
                with mock.patch(
                    "wms.print_renderer.render_to_string",
                    return_value="ok",
                ) as render_mock:
                    result = print_renderer._render_block(
                        {"type": block_type, "style": {"padding": "1mm"}},
                        {"shipment_ref": "SHP"},
                    )
                self.assertEqual(result, "ok")
                called_template = render_mock.call_args.args[0]
                self.assertEqual(called_template, template_name)

    def test_render_block_unknown_type_returns_empty_string(self):
        self.assertEqual(
            print_renderer._render_block({"type": "unknown"}, {}),
            "",
        )

    def test_normalize_layout_handles_invalid_inputs(self):
        self.assertEqual(print_renderer._normalize_layout(None), {"blocks": []})
        self.assertEqual(print_renderer._normalize_layout({"blocks": "bad"}), {"blocks": []})
        self.assertEqual(
            print_renderer._normalize_layout({"blocks": [{"type": "text"}]}),
            {"blocks": [{"type": "text"}]},
        )

    def test_get_default_layout_returns_template_or_empty_layout(self):
        shipment_layout = print_renderer.get_default_layout("shipment_note")
        self.assertIsInstance(shipment_layout, dict)
        self.assertIn("blocks", shipment_layout)

        missing_layout = print_renderer.get_default_layout("unknown-doc")
        self.assertEqual(missing_layout, {"blocks": []})

    def test_get_template_layout_returns_override_only_when_non_empty(self):
        self.assertIsNone(print_renderer.get_template_layout("shipment_note"))

        PrintTemplate.objects.create(doc_type="shipment_note", layout={})
        self.assertIsNone(print_renderer.get_template_layout("shipment_note"))

        override = {"blocks": [{"type": "text"}]}
        template = PrintTemplate.objects.get(doc_type="shipment_note")
        template.layout = override
        template.save(update_fields=["layout"])
        self.assertEqual(print_renderer.get_template_layout("shipment_note"), override)

    def test_resolve_layout_prefers_template_override(self):
        override = {"blocks": [{"type": "text"}]}
        PrintTemplate.objects.create(doc_type="shipment_note", layout=override)
        self.assertEqual(print_renderer.resolve_layout("shipment_note"), override)

    def test_resolve_layout_falls_back_to_default(self):
        layout = print_renderer.resolve_layout("shipment_label")
        self.assertIsInstance(layout, dict)
        self.assertIn("blocks", layout)

    def test_render_layout_from_layout_skips_empty_blocks(self):
        with mock.patch(
            "wms.print_renderer._render_block",
            side_effect=["first", "", "third"],
        ) as render_block_mock:
            rendered = print_renderer.render_layout_from_layout(
                {"blocks": [{"type": "a"}, {"type": "b"}, {"type": "c"}]},
                {"x": 1},
            )
        self.assertEqual(rendered, ["first", "third"])
        self.assertEqual(render_block_mock.call_count, 3)

    def test_render_layout_uses_resolved_layout(self):
        with mock.patch(
            "wms.print_renderer.resolve_layout",
            return_value={"blocks": [{"type": "text"}]},
        ) as resolve_mock:
            with mock.patch(
                "wms.print_renderer.render_layout_from_layout",
                return_value=["rendered"],
            ) as render_from_layout_mock:
                output = print_renderer.render_layout("shipment_note", {"k": "v"})
        self.assertEqual(output, ["rendered"])
        resolve_mock.assert_called_once_with("shipment_note")
        render_from_layout_mock.assert_called_once_with({"blocks": [{"type": "text"}]}, {"k": "v"})

    def test_layout_changed_handles_none_and_key_order(self):
        self.assertTrue(print_renderer.layout_changed(None, {"a": 1}))
        self.assertFalse(
            print_renderer.layout_changed(
                {"a": 1, "b": 2},
                {"b": 2, "a": 1},
            )
        )
        self.assertTrue(print_renderer.layout_changed({"a": 1}, {"a": 2}))
