import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.models import Carton, Destination, PrintTemplate, PrintTemplateVersion, Product, Shipment


class PrintTemplateViewsTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="print-admin",
            email="print-admin@example.com",
            password="pass1234",
        )
        self.client.force_login(self.superuser)

    def _list_url(self):
        return reverse("scan:scan_print_templates")

    def _edit_url(self, doc_type="shipment_note"):
        return reverse("scan:scan_print_template_edit", args=[doc_type])

    def _preview_url(self):
        return reverse("scan:scan_print_template_preview")

    def _render_stub(self, _request, template_name, context):
        response = HttpResponse(template_name)
        response.context_data = context
        return response

    def test_scan_print_templates_list_displays_override_state(self):
        PrintTemplate.objects.create(
            doc_type="shipment_note",
            layout={"blocks": [{"id": "header", "type": "text"}]},
            updated_by=self.superuser,
        )
        response = self.client.get(self._list_url())
        self.assertEqual(response.status_code, 200)
        template_entry = next(
            item
            for item in response.context["templates"]
            if item["doc_type"] == "shipment_note"
        )
        self.assertTrue(template_entry["has_override"])
        self.assertEqual(template_entry["updated_by"], self.superuser)

    def test_scan_print_template_edit_404_for_unknown_doc_type(self):
        response = self.client.get(self._edit_url("unknown-template"))
        self.assertEqual(response.status_code, 404)

    def test_scan_print_template_edit_save_creates_template_and_version(self):
        layout_data = {"blocks": [{"id": "header", "type": "text"}]}
        response = self.client.post(
            self._edit_url("shipment_note"),
            {"layout_json": json.dumps(layout_data)},
        )
        self.assertEqual(response.status_code, 302)
        template = PrintTemplate.objects.get(doc_type="shipment_note")
        self.assertEqual(template.layout, layout_data)
        self.assertEqual(template.updated_by, self.superuser)
        version = PrintTemplateVersion.objects.get(template=template)
        self.assertEqual(version.version, 1)
        self.assertEqual(version.layout, layout_data)
        self.assertEqual(version.created_by, self.superuser)

    def test_scan_print_template_edit_rejects_invalid_json(self):
        response = self.client.post(
            self._edit_url("shipment_note"),
            {"layout_json": "{"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PrintTemplate.objects.count(), 0)
        self.assertEqual(PrintTemplateVersion.objects.count(), 0)

    def test_scan_print_template_edit_no_change_does_not_create_version(self):
        layout_data = {"blocks": [{"id": "header", "type": "text"}]}
        template = PrintTemplate.objects.create(
            doc_type="shipment_note",
            layout=layout_data,
            updated_by=self.superuser,
        )
        response = self.client.post(
            self._edit_url("shipment_note"),
            {"layout_json": json.dumps(layout_data)},
        )
        self.assertEqual(response.status_code, 302)
        template.refresh_from_db()
        self.assertEqual(template.layout, layout_data)
        self.assertEqual(template.versions.count(), 0)

    def test_scan_print_template_edit_reset_without_existing_template(self):
        response = self.client.post(
            self._edit_url("shipment_note"),
            {"action": "reset"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PrintTemplate.objects.count(), 0)

    def test_scan_print_template_edit_reset_existing_template(self):
        template = PrintTemplate.objects.create(
            doc_type="shipment_note",
            layout={"blocks": [{"id": "header", "type": "text"}]},
            updated_by=self.superuser,
        )
        response = self.client.post(
            self._edit_url("shipment_note"),
            {"action": "reset"},
        )
        self.assertEqual(response.status_code, 302)
        template.refresh_from_db()
        self.assertEqual(template.layout, {})
        self.assertEqual(template.versions.count(), 1)
        self.assertEqual(template.versions.first().version, 1)

    def test_scan_print_template_edit_restore_requires_version_id(self):
        PrintTemplate.objects.create(
            doc_type="shipment_note",
            layout={"blocks": [{"id": "header", "type": "text"}]},
            updated_by=self.superuser,
        )
        response = self.client.post(
            self._edit_url("shipment_note"),
            {"action": "restore"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PrintTemplateVersion.objects.count(), 0)

    def test_scan_print_template_edit_restore_applies_selected_version(self):
        template = PrintTemplate.objects.create(
            doc_type="shipment_note",
            layout={"blocks": [{"id": "current", "type": "text"}]},
            updated_by=self.superuser,
        )
        restored_layout = {"blocks": [{"id": "restored", "type": "text"}]}
        version = PrintTemplateVersion.objects.create(
            template=template,
            version=1,
            layout=restored_layout,
            created_by=self.superuser,
        )
        response = self.client.post(
            self._edit_url("shipment_note"),
            {"action": "restore", "version_id": str(version.id)},
        )
        self.assertEqual(response.status_code, 302)
        template.refresh_from_db()
        self.assertEqual(template.layout, restored_layout)
        versions = list(template.versions.order_by("version"))
        self.assertEqual([item.version for item in versions], [1, 2])
        self.assertEqual(versions[-1].layout, restored_layout)

    def test_scan_print_template_preview_rejects_unknown_doc_type(self):
        response = self.client.post(
            self._preview_url(),
            {"doc_type": "unknown", "layout_json": "{}"},
        )
        self.assertEqual(response.status_code, 404)

    def test_scan_print_template_preview_rejects_invalid_json(self):
        response = self.client.post(
            self._preview_url(),
            {"doc_type": "shipment_note", "layout_json": "{"},
        )
        self.assertEqual(response.status_code, 400)

    def test_scan_print_template_edit_get_builds_shipments_products_and_versions(self):
        correspondent = Contact.objects.create(
            name="Correspondent Template",
            contact_type=ContactType.ORGANIZATION,
        )
        destination = Destination.objects.create(
            city="Paris",
            iata_code="PAR-TPL",
            country="France",
            correspondent_contact=correspondent,
        )
        Shipment.objects.create(
            reference="SHP-B",
            shipper_name="Sender B",
            recipient_name="Recipient B",
            destination=destination,
            destination_address="1 Rue Paris",
            destination_country="France",
        )
        Shipment.objects.create(
            reference="SHP-A",
            shipper_name="Sender A",
            recipient_name="Recipient A",
            destination=None,
            destination_address="Fallback City",
            destination_country="France",
        )
        Product.objects.create(name="Produit Sans SKU")
        Product.objects.create(name="Produit Avec SKU", sku="SKU-TPL")
        template = PrintTemplate.objects.create(
            doc_type="product_label",
            layout={"blocks": [{"id": "main", "type": "text"}]},
            updated_by=self.superuser,
        )
        PrintTemplateVersion.objects.create(
            template=template,
            version=1,
            layout={"blocks": [{"id": "v1", "type": "text"}]},
            created_by=self.superuser,
        )

        response = self.client.get(self._edit_url("product_label"))

        self.assertEqual(response.status_code, 200)
        shipment_labels = [item["label"] for item in response.context["shipments"]]
        self.assertIn("SHP-B - Paris", shipment_labels)
        self.assertIn("SHP-A - Fallback City", shipment_labels)
        product_labels = [item["label"] for item in response.context["products"]]
        self.assertTrue(any("Produit Sans Sku" in label for label in product_labels))
        self.assertIn("SKU-TPL - Produit Avec Sku", product_labels)
        self.assertEqual(len(response.context["versions"]), 1)
        self.assertEqual(response.context["versions"][0].version, 1)

    def test_scan_print_template_preview_shipment_label_without_shipment(self):
        with mock.patch(
            "wms.views_print_templates.build_sample_label_context",
            return_value={"destination_city": "Paris"},
        ):
            with mock.patch(
                "wms.views_print_templates.render_layout_from_layout",
                return_value=[{"type": "label_city"}],
            ):
                with mock.patch(
                    "wms.views_print_templates.render",
                    side_effect=self._render_stub,
                ) as render_mock:
                    response = self.client.post(
                        self._preview_url(),
                        {"doc_type": "shipment_label", "layout_json": "{}"},
                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "print/dynamic_labels.html")
        render_kwargs = render_mock.call_args.args[2]
        self.assertEqual(len(render_kwargs["labels"]), 1)

    def test_scan_print_template_preview_shipment_label_with_shipment_cartons(self):
        shipment = Shipment.objects.create(
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )
        Carton.objects.create(code="C-001", shipment=shipment)
        Carton.objects.create(code="C-002", shipment=shipment)

        with mock.patch(
            "wms.views_print_templates.build_label_context",
            return_value={"destination_city": "Paris"},
        ) as build_label_context_mock:
            with mock.patch(
                "wms.views_print_templates.render_layout_from_layout",
                return_value=[{"type": "label_city"}],
            ):
                with mock.patch(
                    "wms.views_print_templates.render",
                    side_effect=self._render_stub,
                ) as render_mock:
                    response = self.client.post(
                        self._preview_url(),
                        {
                            "doc_type": "shipment_label",
                            "layout_json": "{}",
                            "shipment_id": str(shipment.id),
                        },
                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "print/dynamic_labels.html")
        self.assertEqual(build_label_context_mock.call_count, 2)
        render_kwargs = render_mock.call_args.args[2]
        self.assertEqual(len(render_kwargs["labels"]), 2)

    def test_scan_print_template_preview_shipment_label_with_empty_shipment_uses_sample(self):
        shipment = Shipment.objects.create(
            shipper_name="Sender Empty",
            recipient_name="Recipient Empty",
            destination_address="1 Rue Test",
            destination_country="France",
        )

        with mock.patch(
            "wms.views_print_templates.build_sample_label_context",
            return_value={"destination_city": "Sample"},
        ) as sample_context_mock:
            with mock.patch(
                "wms.views_print_templates.render_layout_from_layout",
                return_value=[{"type": "label_city"}],
            ):
                with mock.patch(
                    "wms.views_print_templates.render",
                    side_effect=self._render_stub,
                ) as render_mock:
                    response = self.client.post(
                        self._preview_url(),
                        {
                            "doc_type": "shipment_label",
                            "layout_json": "{}",
                            "shipment_id": str(shipment.id),
                        },
                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "print/dynamic_labels.html")
        sample_context_mock.assert_called_once()
        self.assertEqual(len(render_mock.call_args.args[2]["labels"]), 1)

    def test_scan_print_template_preview_product_label_with_product(self):
        product = Product.objects.create(name="Produit Preview")
        with mock.patch(
            "wms.views_print_templates.build_product_label_context",
            return_value={"name": product.name},
        ) as product_context_mock:
            with mock.patch(
                "wms.views_print_templates.build_label_pages",
                return_value=([{"rows": []}], {"page_margin": "0"}),
            ) as build_pages_mock:
                with mock.patch(
                    "wms.views_print_templates.render",
                    side_effect=self._render_stub,
                ):
                    response = self.client.post(
                        self._preview_url(),
                        {
                            "doc_type": "product_label",
                            "product_id": str(product.id),
                            "layout_json": "{}",
                        },
                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "print/product_labels.html")
        product_context_mock.assert_called_once()
        self.assertEqual(product_context_mock.call_args.args[0].id, product.id)
        build_pages_kwargs = build_pages_mock.call_args.kwargs
        self.assertEqual(build_pages_kwargs["block_type"], "product_label")
        self.assertEqual(build_pages_kwargs["labels_per_page"], 4)

    def test_scan_print_template_preview_product_label_without_product_uses_generic_context(self):
        with mock.patch(
            "wms.views_print_templates.build_preview_context",
            return_value={"name": "fallback"},
        ) as preview_context_mock:
            with mock.patch(
                "wms.views_print_templates.build_label_pages",
                return_value=([{"rows": []}], {"page_margin": "0"}),
            ):
                with mock.patch(
                    "wms.views_print_templates.render",
                    side_effect=self._render_stub,
                ):
                    response = self.client.post(
                        self._preview_url(),
                        {
                            "doc_type": "product_label",
                            "layout_json": "{}",
                            "product_id": "not-a-number",
                        },
                    )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "print/product_labels.html")
        preview_context_mock.assert_called_once_with("product_label")

    def test_scan_print_template_preview_product_qr_with_product(self):
        product = Product.objects.create(name="Produit QR")
        product.qr_code_image = ""
        product.save(update_fields=["qr_code_image"])

        with mock.patch(
            "wms.models.Product.generate_qr_code",
            autospec=True,
        ) as generate_qr_mock:
            with mock.patch(
                "wms.views_print_templates.build_preview_context",
                return_value={"sku": product.sku},
            ) as preview_context_mock:
                with mock.patch(
                    "wms.views_print_templates.extract_block_style",
                    return_value={"page_rows": "2", "page_columns": "3"},
                ):
                    with mock.patch(
                        "wms.views_print_templates.build_label_pages",
                        return_value=([{"rows": []}], {"page_margin": "0"}),
                    ) as build_pages_mock:
                        with mock.patch(
                            "wms.views_print_templates.render",
                            side_effect=self._render_stub,
                        ):
                            response = self.client.post(
                                self._preview_url(),
                                {
                                    "doc_type": "product_qr",
                                    "product_id": str(product.id),
                                    "layout_json": "{}",
                                },
                            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "print/product_qr_labels.html")
        generate_qr_mock.assert_called_once()
        preview_context_mock.assert_called_once()
        build_pages_kwargs = build_pages_mock.call_args.kwargs
        self.assertEqual(build_pages_kwargs["block_type"], "product_qr_label")
        self.assertEqual(build_pages_kwargs["labels_per_page"], 6)

    def test_scan_print_template_preview_product_qr_without_product_and_invalid_grid_uses_defaults(
        self,
    ):
        with mock.patch(
            "wms.views_print_templates.build_preview_context",
            return_value={"sku": "fallback"},
        ) as preview_context_mock:
            with mock.patch(
                "wms.views_print_templates.extract_block_style",
                return_value={"page_rows": "x", "page_columns": "y"},
            ):
                with mock.patch(
                    "wms.views_print_templates.build_label_pages",
                    return_value=([{"rows": []}], {"page_margin": "0"}),
                ) as build_pages_mock:
                    with mock.patch(
                        "wms.views_print_templates.render",
                        side_effect=self._render_stub,
                    ):
                        response = self.client.post(
                            self._preview_url(),
                            {
                                "doc_type": "product_qr",
                                "layout_json": "{}",
                                "product_id": "",
                            },
                        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "print/product_qr_labels.html")
        preview_context_mock.assert_called_once_with("product_qr")
        build_pages_kwargs = build_pages_mock.call_args.kwargs
        self.assertEqual(build_pages_kwargs["labels_per_page"], 15)

    def test_scan_print_template_preview_standard_document(self):
        with mock.patch(
            "wms.views_print_templates.build_preview_context",
            return_value={"shipment_ref": "SHP-1"},
        ) as preview_context_mock:
            with mock.patch(
                "wms.views_print_templates.render_layout_from_layout",
                return_value=[{"type": "text"}],
            ) as render_layout_mock:
                with mock.patch(
                    "wms.views_print_templates.render",
                    side_effect=self._render_stub,
                ) as render_mock:
                    response = self.client.post(
                        self._preview_url(),
                        {"doc_type": "shipment_note", "layout_json": "{}"},
                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "print/dynamic_document.html")
        preview_context_mock.assert_called_once()
        render_layout_mock.assert_called_once()
        self.assertEqual(render_mock.call_args.args[2]["blocks"], [{"type": "text"}])
