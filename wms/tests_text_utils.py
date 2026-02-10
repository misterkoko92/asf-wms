from django.test import SimpleTestCase

from .text_utils import normalize_category_name, normalize_title, normalize_upper


class TextUtilsTests(SimpleTestCase):
    def test_normalize_upper_handles_none_and_blank(self):
        self.assertIsNone(normalize_upper(None))
        self.assertEqual(normalize_upper("   "), "")
        self.assertEqual(normalize_upper(" abc "), "ABC")

    def test_normalize_title_capitalizes_each_word(self):
        self.assertEqual(normalize_title("gants latex m"), "Gants Latex M")
        self.assertEqual(normalize_title("masques chirurgicaux"), "Masques Chirurgicaux")

    def test_normalize_title_keeps_separators(self):
        self.assertEqual(normalize_title("set-de perfusion"), "Set-De Perfusion")
        self.assertEqual(normalize_title("masques/ffp2"), "Masques/Ffp2")
        self.assertEqual(normalize_title("set--de"), "Set--De")

    def test_normalize_title_handles_none_blank_and_non_alpha_prefix(self):
        self.assertIsNone(normalize_title(None))
        self.assertEqual(normalize_title("   "), "")
        self.assertEqual(normalize_title("3m masque"), "3m Masque")

    def test_normalize_category_root_is_upper(self):
        self.assertEqual(normalize_category_name("medical supply", is_root=True), "MEDICAL SUPPLY")

    def test_normalize_category_keeps_acronyms(self):
        self.assertEqual(normalize_category_name("epi protection"), "EPI Protection")
        self.assertEqual(normalize_category_name("pca kit"), "PCA Kit")
