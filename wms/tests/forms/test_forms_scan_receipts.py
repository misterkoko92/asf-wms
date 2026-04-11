from decimal import Decimal

from django.http import QueryDict
from django.test import TestCase

from wms.forms import ScanIncompleteProductBulkUpdateForm
from wms.models import Location, Product, ProductCategory, Warehouse


class ScanIncompleteProductBulkUpdateFormTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(name="Mask", is_incomplete=True)
        self.other_product = Product.objects.create(name="Gloves", is_incomplete=True)
        self.category = ProductCategory.objects.create(name="Medical")
        warehouse = Warehouse.objects.create(name="Main", code="MAIN")
        self.location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )

    def _build_data(self, **overrides):
        data = QueryDict("", mutable=True)
        data["field_name"] = "brand"
        data["field_value"] = "ASF"
        data.setlist("selected_product_ids", [str(self.product.id)])
        for key, value in overrides.items():
            if key == "selected_product_ids":
                data.setlist(key, value)
            else:
                data[key] = value
        return data

    def test_requires_selected_products(self):
        form = ScanIncompleteProductBulkUpdateForm(
            data=self._build_data(selected_product_ids=[]),
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            "Sélectionnez au moins un produit incomplet.",
            form.non_field_errors(),
        )

    def test_rejects_selected_product_outside_queryset(self):
        form = ScanIncompleteProductBulkUpdateForm(
            data=self._build_data(),
            product_queryset=Product.objects.filter(pk=self.other_product.pk),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Produit sélectionné invalide.", form.non_field_errors())

    def test_rejects_identifier_bulk_update_for_multiple_products(self):
        form = ScanIncompleteProductBulkUpdateForm(
            data=self._build_data(
                field_name="ean",
                field_value="1234567890123",
                selected_product_ids=[str(self.product.id), str(self.other_product.id)],
            ),
            product_queryset=Product.objects.filter(
                pk__in=[self.product.pk, self.other_product.pk]
            ),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("EAN ne peut pas être appliqué en masse.", form.errors["field_name"])

    def test_resolves_category_from_raw_value(self):
        form = ScanIncompleteProductBulkUpdateForm(
            data=self._build_data(
                field_name="category",
                field_value=str(self.category.id),
            ),
            product_queryset=Product.objects.filter(pk=self.product.pk),
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["selected_product_ids"], [self.product.id])
        self.assertEqual(form.cleaned_data["resolved_value"], self.category)

    def test_rejects_unknown_category_raw_value(self):
        form = ScanIncompleteProductBulkUpdateForm(
            data=self._build_data(
                field_name="category",
                field_value="999999",
            ),
            product_queryset=Product.objects.filter(pk=self.product.pk),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Valeur invalide pour Catégorie.", form.errors["field_value"])

    def test_resolves_location_from_raw_value(self):
        form = ScanIncompleteProductBulkUpdateForm(
            data=self._build_data(
                field_name="default_location",
                field_value=str(self.location.id),
            ),
            product_queryset=Product.objects.filter(pk=self.product.pk),
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["resolved_value"], self.location)

    def test_rejects_invalid_boolean_value(self):
        form = ScanIncompleteProductBulkUpdateForm(
            data=self._build_data(
                field_name="perishable",
                field_value="not-a-bool",
            ),
            product_queryset=Product.objects.filter(pk=self.product.pk),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Valeur booléenne invalide.", form.errors["field_value"])

    def test_parses_boolean_decimal_and_integer_values(self):
        boolean_form = ScanIncompleteProductBulkUpdateForm(
            data=self._build_data(
                field_name="quarantine_default",
                field_value_boolean="false",
                field_value="",
            ),
            product_queryset=Product.objects.filter(pk=self.product.pk),
        )
        decimal_form = ScanIncompleteProductBulkUpdateForm(
            data=self._build_data(
                field_name="pu_ht",
                field_value="12.50",
            ),
            product_queryset=Product.objects.filter(pk=self.product.pk),
        )
        integer_form = ScanIncompleteProductBulkUpdateForm(
            data=self._build_data(
                field_name="weight_g",
                field_value="15",
            ),
            product_queryset=Product.objects.filter(pk=self.product.pk),
        )

        self.assertTrue(boolean_form.is_valid())
        self.assertFalse(boolean_form.cleaned_data["resolved_value"])
        self.assertTrue(decimal_form.is_valid())
        self.assertEqual(decimal_form.cleaned_data["resolved_value"], Decimal("12.50"))
        self.assertTrue(integer_form.is_valid())
        self.assertEqual(integer_form.cleaned_data["resolved_value"], 15)
