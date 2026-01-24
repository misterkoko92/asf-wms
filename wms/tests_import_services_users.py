from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.import_services import import_users


class ImportUsersTests(TestCase):
    def test_import_users_requires_password_for_new_user(self):
        rows = [{"username": "alice"}]
        created, updated, errors = import_users(rows, default_password="")
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(len(errors), 1)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_import_users_uses_default_password(self):
        rows = [{"username": "bob", "email": "bob@example.com"}]
        created, updated, errors = import_users(rows, default_password="Default123")
        self.assertEqual(errors, [])
        self.assertEqual(created, 1)
        user = get_user_model().objects.get(username="bob")
        self.assertTrue(user.check_password("Default123"))

    def test_import_users_updates_existing_user(self):
        user = get_user_model().objects.create_user(
            username="carol", password="OldPass"
        )
        rows = [{"username": "carol", "is_staff": "oui"}]
        created, updated, errors = import_users(rows, default_password="")
        self.assertEqual(errors, [])
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertTrue(user.check_password("OldPass"))

    def test_import_users_sets_password_when_provided(self):
        get_user_model().objects.create_user(username="dave", password="OldPass")
        rows = [{"username": "dave", "password": "NewPass"}]
        created, updated, errors = import_users(rows, default_password="")
        self.assertEqual(errors, [])
        self.assertEqual(created, 0)
        user = get_user_model().objects.get(username="dave")
        self.assertTrue(user.check_password("NewPass"))
