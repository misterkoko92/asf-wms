from django.test import SimpleTestCase


class V32RuntimeImportsTests(SimpleTestCase):
    def test_v32_runtime_packages_import(self):
        from wms import events, jobs

        self.assertIsNotNone(events)
        self.assertIsNotNone(jobs)
