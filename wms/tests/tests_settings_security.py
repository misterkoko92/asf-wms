from django.test import SimpleTestCase

from asf_wms import settings as project_settings


class SettingsSecurityTests(SimpleTestCase):
    def test_is_secure_secret_key_rejects_empty(self):
        self.assertFalse(project_settings._is_secure_secret_key(""))

    def test_is_secure_secret_key_rejects_django_prefix(self):
        insecure = "django-insecure-" + "a" * 60
        self.assertFalse(project_settings._is_secure_secret_key(insecure))

    def test_is_secure_secret_key_rejects_short_values(self):
        self.assertFalse(project_settings._is_secure_secret_key("short-secret"))

    def test_is_secure_secret_key_rejects_low_entropy_values(self):
        self.assertFalse(project_settings._is_secure_secret_key("a" * 80))

    def test_is_secure_secret_key_accepts_strong_value(self):
        secure = "S3cure-Key-For-ASF-WMS-Deploy-0123456789-abcdefghijklmnopqrstuvwxyz"
        self.assertTrue(project_settings._is_secure_secret_key(secure))
