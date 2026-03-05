from django.test import SimpleTestCase

from contacts import views


class ContactsViewsModuleTests(SimpleTestCase):
    def test_module_import_exposes_render_shortcut(self):
        self.assertTrue(callable(views.render))
