from datetime import date, datetime

from django.template import Context, Template
from django.test import SimpleTestCase


class WmsDatesTemplateTagsTests(SimpleTestCase):
    def test_scan_date_short_formats_date(self):
        html = Template("{% load wms_dates %}{{ value|scan_date_short }}").render(
            Context({"value": date(2026, 4, 16)})
        )

        self.assertEqual(html, "16/04/26")

    def test_scan_datetime_short_formats_datetime(self):
        html = Template("{% load wms_dates %}{{ value|scan_datetime_short }}").render(
            Context({"value": datetime(2026, 4, 16, 14, 5)})
        )

        self.assertEqual(html, "16/04/26 14h05")

    def test_scan_date_weekday_short_formats_weekday_prefix(self):
        html = Template("{% load wms_dates %}{{ value|scan_date_weekday_short }}").render(
            Context({"value": date(2026, 4, 16)})
        )

        self.assertEqual(html, "Jeu 16/04/26")
