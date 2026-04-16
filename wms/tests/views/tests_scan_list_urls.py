from django.http import QueryDict
from django.test import SimpleTestCase

from wms.scan_list_urls import build_scan_list_url


class ScanListUrlTests(SimpleTestCase):
    def test_build_scan_list_url_preserves_filters_and_replaces_page(self):
        params = QueryDict("q=compresse&type=association&page=3", mutable=True)

        self.assertEqual(
            build_scan_list_url("/scan/receipts/", params, page=2),
            "/scan/receipts/?q=compresse&type=association&page=2",
        )

    def test_build_scan_list_url_drops_page_when_target_is_first_page(self):
        params = QueryDict("q=compresse&sort=name&page=4", mutable=True)

        self.assertEqual(
            build_scan_list_url("/scan/receipts/", params, page=1),
            "/scan/receipts/?q=compresse&sort=name",
        )

    def test_build_scan_list_url_can_reset_specific_keys(self):
        params = QueryDict("q=compresse&sort=name&page=4", mutable=True)

        self.assertEqual(
            build_scan_list_url(
                "/scan/receipts/",
                params,
                reset_keys={"q", "sort", "page"},
            ),
            "/scan/receipts/",
        )
