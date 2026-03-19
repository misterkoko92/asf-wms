from django.test import SimpleTestCase
from django.urls import NoReverseMatch, reverse


class BootstrapOnlyUiRoutingTests(SimpleTestCase):
    def test_ui_mode_routes_are_not_exposed(self):
        with self.assertRaises(NoReverseMatch):
            reverse("ui_mode_set")

        with self.assertRaises(NoReverseMatch):
            reverse("ui_mode_set_mode", args=["legacy"])

    def test_next_frontend_routes_are_not_exposed(self):
        with self.assertRaises(NoReverseMatch):
            reverse("next_frontend_root")

        with self.assertRaises(NoReverseMatch):
            reverse("next_frontend", args=["scan/dashboard"])

        with self.assertRaises(NoReverseMatch):
            reverse("frontend_log_event")
