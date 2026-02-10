from unittest import mock

from django.test import TestCase

from wms import print_utils


class PrintUtilsTests(TestCase):
    def test_chunked_splits_items_by_size(self):
        self.assertEqual(
            print_utils.chunked([1, 2, 3, 4, 5], 2),
            [[1, 2], [3, 4], [5]],
        )
        self.assertEqual(print_utils.chunked([], 3), [])

    def test_extract_block_style_handles_missing_or_invalid_layout(self):
        self.assertEqual(print_utils.extract_block_style(None, "product_label"), {})
        self.assertEqual(print_utils.extract_block_style({"blocks": []}, "product_label"), {})
        self.assertEqual(
            print_utils.extract_block_style(
                {"blocks": [{"type": "product_label", "style": {"a": 1}}]},
                "product_label",
            ),
            {"a": 1},
        )
        self.assertEqual(
            print_utils.extract_block_style(
                {"blocks": [{"type": "product_label"}]},
                "product_label",
            ),
            {},
        )

    def test_build_label_pages_renders_blocks_and_extracts_style(self):
        layout = {
            "blocks": [
                {"type": "product_label", "style": {"page_margin": "5mm"}},
            ]
        }
        contexts = [{"sku": "A"}, {"sku": "B"}, {"sku": "C"}]

        with mock.patch(
            "wms.print_utils.render_layout_from_layout",
            side_effect=[["A"], ["B"], ["C"]],
        ) as render_mock:
            pages, page_style = print_utils.build_label_pages(
                layout,
                contexts,
                block_type="product_label",
                labels_per_page=2,
            )

        self.assertEqual(render_mock.call_count, 3)
        self.assertEqual(
            pages,
            [
                [{"blocks": ["A"]}, {"blocks": ["B"]}],
                [{"blocks": ["C"]}],
            ],
        )
        self.assertEqual(page_style, {"page_margin": "5mm"})
