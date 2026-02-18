from types import SimpleNamespace
from unittest import mock

from django.http import Http404, HttpResponse
from django.test import RequestFactory, TestCase
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms.models import Carton, Document, DocumentType, Shipment, ShipmentStatus, ShipmentTrackingStatus
from wms.shipment_view_helpers import (
    build_carton_options,
    build_shipment_document_links,
    build_shipments_ready_rows,
    next_tracking_status,
    render_carton_document,
    render_shipment_document,
    render_shipment_labels,
)


class ShipmentViewHelpersTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get("/scan/")

    def _render_stub(self, _request, template_name, context):
        response = HttpResponse(template_name)
        response.context_data = context
        return response

    def _create_shipment(self):
        return Shipment.objects.create(
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )

    def test_build_carton_options_computes_weights(self):
        item_set_a = mock.MagicMock()
        item_set_b = mock.MagicMock()
        item_set_a.all.return_value = [
            SimpleNamespace(
                product_lot=SimpleNamespace(product=SimpleNamespace(weight_g=200)),
                quantity=3,
            )
        ]
        item_set_b.all.return_value = [
            SimpleNamespace(
                product_lot=SimpleNamespace(product=SimpleNamespace(weight_g=None)),
                quantity=2,
            )
        ]
        cartons = [
            SimpleNamespace(id=1, code="C-001", cartonitem_set=item_set_a),
            SimpleNamespace(id=2, code="C-002", cartonitem_set=item_set_b),
        ]

        rows = build_carton_options(cartons)
        self.assertEqual(
            rows,
            [
                {"id": 1, "code": "C-001", "weight_g": 600},
                {"id": 2, "code": "C-002", "weight_g": 0},
            ],
        )

    def test_build_shipment_document_links_public_returns_empty_sets(self):
        shipment = self._create_shipment()
        documents, carton_docs, additional_docs = build_shipment_document_links(
            shipment, public=True
        )
        self.assertEqual(documents, [])
        self.assertEqual(carton_docs, [])
        self.assertEqual(additional_docs.count(), 0)

    def test_build_shipment_document_links_builds_routes_and_additional_docs(self):
        shipment = self._create_shipment()
        carton = Carton.objects.create(code="C-100", shipment=shipment)
        Document.objects.create(
            shipment=shipment,
            doc_type=DocumentType.ADDITIONAL,
        )
        Document.objects.create(
            shipment=shipment,
            doc_type=DocumentType.SHIPMENT_NOTE,
        )

        documents, carton_docs, additional_docs = build_shipment_document_links(shipment)

        self.assertEqual(len(documents), 6)
        self.assertEqual(documents[0]["label"], "Bon d'expédition")
        self.assertIn(f"/scan/shipment/{shipment.id}/doc/shipment_note/", documents[0]["url"])
        self.assertEqual(carton_docs, [{"label": carton.code, "url": f"/scan/shipment/{shipment.id}/carton/{carton.id}/doc/"}])
        self.assertEqual(additional_docs.count(), 1)

    def test_next_tracking_status_handles_empty_choices(self):
        with mock.patch(
            "wms.shipment_view_helpers.ShipmentTrackingStatus",
            SimpleNamespace(choices=[]),
        ):
            self.assertIsNone(next_tracking_status(None))

    def test_next_tracking_status_progression_and_bounds(self):
        first = ShipmentTrackingStatus.choices[0][0]
        second = ShipmentTrackingStatus.choices[1][0]
        last = ShipmentTrackingStatus.choices[-1][0]
        self.assertEqual(next_tracking_status(None), first)
        self.assertEqual(next_tracking_status("invalid"), first)
        self.assertEqual(next_tracking_status(first), second)
        self.assertEqual(next_tracking_status(last), last)

    def test_render_shipment_document_raises_for_unknown_doc_type(self):
        shipment = self._create_shipment()
        with self.assertRaises(Http404):
            render_shipment_document(self.request, shipment, "unknown-doc")

    def test_render_shipment_document_uses_dynamic_layout_when_configured(self):
        shipment = self._create_shipment()
        with mock.patch(
            "wms.shipment_view_helpers.build_shipment_document_context",
            return_value={"shipment_ref": shipment.reference},
        ):
            with mock.patch(
                "wms.shipment_view_helpers.get_template_layout",
                return_value={"blocks": [{"id": "header"}]},
            ):
                with mock.patch(
                    "wms.shipment_view_helpers.render_layout_from_layout",
                    return_value=[{"type": "header"}],
                ):
                    with mock.patch(
                        "wms.shipment_view_helpers.render",
                        side_effect=self._render_stub,
                    ) as render_mock:
                        response = render_shipment_document(
                            self.request, shipment, "shipment_note"
                        )
        self.assertEqual(response.content.decode(), "print/dynamic_document.html")
        self.assertEqual(render_mock.call_args.args[2], {"blocks": [{"type": "header"}]})

    def test_render_shipment_document_uses_default_template_without_layout(self):
        shipment = self._create_shipment()
        with mock.patch(
            "wms.shipment_view_helpers.build_shipment_document_context",
            return_value={"shipment_ref": shipment.reference},
        ):
            with mock.patch(
                "wms.shipment_view_helpers.get_template_layout",
                return_value=None,
            ):
                with mock.patch(
                    "wms.shipment_view_helpers.render",
                    side_effect=self._render_stub,
                ) as render_mock:
                    response = render_shipment_document(
                        self.request, shipment, "shipment_note"
                    )
        self.assertEqual(response.content.decode(), "print/bon_expedition.html")
        self.assertEqual(render_mock.call_args.args[2], {"shipment_ref": shipment.reference})

    def test_render_carton_document_handles_layout_and_default_template(self):
        shipment = self._create_shipment()
        carton = Carton.objects.create(code="C-200", shipment=shipment)

        with mock.patch(
            "wms.shipment_view_helpers.build_carton_document_context",
            return_value={"carton_code": carton.code},
        ):
            with mock.patch(
                "wms.shipment_view_helpers.get_template_layout",
                return_value={"blocks": [{"id": "carton"}]},
            ):
                with mock.patch(
                    "wms.shipment_view_helpers.render_layout_from_layout",
                    return_value=[{"type": "carton"}],
                ):
                    with mock.patch(
                        "wms.shipment_view_helpers.render",
                        side_effect=self._render_stub,
                    ):
                        dynamic_response = render_carton_document(
                            self.request, shipment, carton
                        )

        with mock.patch(
            "wms.shipment_view_helpers.build_carton_document_context",
            return_value={"carton_code": carton.code},
        ):
            with mock.patch(
                "wms.shipment_view_helpers.get_template_layout",
                return_value=None,
            ):
                with mock.patch(
                    "wms.shipment_view_helpers.render",
                    side_effect=self._render_stub,
                ):
                    default_response = render_carton_document(
                        self.request, shipment, carton
                    )

        self.assertEqual(dynamic_response.content.decode(), "print/dynamic_document.html")
        self.assertEqual(default_response.content.decode(), "print/liste_colisage_carton.html")

    def test_render_shipment_labels_uses_fallback_qr_url_without_layout(self):
        shipment = self._create_shipment()
        shipment.qr_code_image = "qr_codes/fallback.png"
        shipment.save(update_fields=["qr_code_image"])
        carton1 = Carton.objects.create(code="A-CARTON", shipment=shipment)
        carton2 = Carton.objects.create(code="B-CARTON", shipment=shipment)

        with mock.patch.object(shipment, "ensure_qr_code") as ensure_mock:
            with mock.patch(
                "wms.shipment_view_helpers.build_label_context",
                side_effect=[
                    {
                        "label_city": "Paris",
                        "label_iata": "CDG",
                        "label_shipment_ref": shipment.reference,
                        "label_position": "1",
                        "label_total": "2",
                        "label_qr_url": "",
                    },
                    {
                        "label_city": "Lyon",
                        "label_iata": "LYS",
                        "label_shipment_ref": shipment.reference,
                        "label_position": "2",
                        "label_total": "2",
                        "label_qr_url": "",
                    },
                ],
            ):
                with mock.patch(
                    "wms.shipment_view_helpers.get_template_layout",
                    return_value=None,
                ):
                    with mock.patch(
                        "wms.shipment_view_helpers.render",
                        side_effect=self._render_stub,
                    ) as render_mock:
                        response = render_shipment_labels(self.request, shipment)

        self.assertEqual(response.content.decode(), "print/etiquette_expedition.html")
        labels = render_mock.call_args.args[2]["labels"]
        self.assertEqual([labels[0]["carton_id"], labels[1]["carton_id"]], [carton1.id, carton2.id])
        self.assertTrue(labels[0]["qr_url"].endswith("/media/qr_codes/fallback.png"))
        ensure_mock.assert_called_once_with(request=self.request)

    def test_render_shipment_labels_uses_dynamic_layout(self):
        shipment = self._create_shipment()
        carton = Carton.objects.create(code="ONLY-CARTON", shipment=shipment)

        with mock.patch.object(shipment, "ensure_qr_code"):
            with mock.patch(
                "wms.shipment_view_helpers.build_label_context",
                return_value={
                    "label_city": "Paris",
                    "label_iata": "CDG",
                    "label_shipment_ref": shipment.reference,
                    "label_position": "1",
                    "label_total": "1",
                    "label_qr_url": "custom-qr",
                },
            ):
                with mock.patch(
                    "wms.shipment_view_helpers.get_template_layout",
                    return_value={"blocks": [{"id": "label"}]},
                ):
                    with mock.patch(
                        "wms.shipment_view_helpers.render_layout_from_layout",
                        return_value=[{"type": "label"}],
                    ) as render_layout_mock:
                        with mock.patch(
                            "wms.shipment_view_helpers.render",
                            side_effect=self._render_stub,
                        ) as render_mock:
                            response = render_shipment_labels(self.request, shipment)

        self.assertEqual(response.content.decode(), "print/dynamic_labels.html")
        self.assertEqual(render_mock.call_args.args[2], {"labels": [{"blocks": [{"type": "label"}]}]})
        self.assertEqual(render_layout_mock.call_count, 1)
        self.assertEqual(render_layout_mock.call_args.args[1]["label_qr_url"], "custom-qr")
        self.assertEqual(render_layout_mock.call_args.args[1]["label_position"], "1")
        self.assertEqual(render_layout_mock.call_args.args[1]["label_total"], "1")
        self.assertEqual(render_mock.call_args.args[2]["labels"][0]["blocks"][0]["type"], "label")
        self.assertEqual(carton.code, "ONLY-CARTON")

    def test_build_shipments_ready_rows_derives_progress_and_status_labels(self):
        now = timezone.now()

        class FakeFiltered:
            def __init__(self, count):
                self._count = count

            def count(self):
                return self._count

        class FakeCartonSet:
            def __init__(self, total, ready):
                self._total = total
                self._ready = ready

            def count(self):
                return self._total

            def filter(self, **_kwargs):
                return FakeFiltered(self._ready)

        draft = SimpleNamespace(
            id=1,
            reference="S-001",
            tracking_token="token-1",
            carton_count=None,
            ready_count=None,
            carton_set=FakeCartonSet(total=0, ready=0),
            destination=None,
            shipper_name="ASF",
            recipient_name="A",
            created_at=now,
            ready_at=None,
            status=ShipmentStatus.DRAFT,
        )
        partial = SimpleNamespace(
            id=2,
            reference="S-002",
            tracking_token="token-2",
            carton_count=3,
            ready_count=1,
            carton_set=FakeCartonSet(total=3, ready=1),
            destination=SimpleNamespace(iata_code="CDG"),
            shipper_name="ASF",
            recipient_name="B",
            created_at=now,
            ready_at=now,
            status=ShipmentStatus.PACKED,
        )
        shipped = SimpleNamespace(
            id=3,
            reference="S-003",
            tracking_token="token-3",
            carton_count=2,
            ready_count=2,
            carton_set=FakeCartonSet(total=2, ready=2),
            destination=SimpleNamespace(iata_code="LYS"),
            shipper_name="ASF",
            recipient_name="C",
            created_at=now,
            ready_at=now,
            status=ShipmentStatus.SHIPPED,
        )

        rows = build_shipments_ready_rows([draft, partial, shipped])
        self.assertEqual(rows[0]["status_label"], "CREATION")
        self.assertTrue(rows[0]["can_edit"])
        self.assertEqual(rows[1]["status_label"], "EN COURS (1/3)")
        self.assertEqual(rows[1]["destination_iata"], "CDG")
        self.assertEqual(rows[2]["status_label"], ShipmentStatus(ShipmentStatus.SHIPPED).label)
        self.assertFalse(rows[2]["can_edit"])

    def test_build_shipments_ready_rows_formats_party_names_from_contact_refs(self):
        now = timezone.now()
        organization = Contact.objects.create(
            name="ASSOCIATION TEST",
            contact_type=ContactType.ORGANIZATION,
        )
        shipper = Contact.objects.create(
            name="Legacy Sender",
            contact_type=ContactType.PERSON,
            title="M.",
            first_name="Jean",
            last_name="Dupont",
            organization=organization,
        )
        recipient = Contact.objects.create(
            name="Legacy Recipient",
            contact_type=ContactType.PERSON,
            title="Mme",
            first_name="Alice",
            last_name="Martin",
        )

        class FakeFiltered:
            def __init__(self, count):
                self._count = count

            def count(self):
                return self._count

        class FakeCartonSet:
            def __init__(self, total, ready):
                self._total = total
                self._ready = ready

            def count(self):
                return self._total

            def filter(self, **_kwargs):
                return FakeFiltered(self._ready)

        shipment = SimpleNamespace(
            id=11,
            reference="S-011",
            tracking_token="token-11",
            carton_count=1,
            ready_count=1,
            carton_set=FakeCartonSet(total=1, ready=1),
            destination=SimpleNamespace(iata_code="BZV"),
            shipper_name="Fallback Sender",
            shipper_contact_ref=shipper,
            recipient_name="Fallback Recipient",
            recipient_contact_ref=recipient,
            created_at=now,
            ready_at=now,
            status=ShipmentStatus.PACKED,
        )

        rows = build_shipments_ready_rows([shipment])

        self.assertEqual(rows[0]["shipper_name"], "ASSOCIATION TEST")
        self.assertEqual(rows[0]["recipient_name"], "Mme Alice MARTIN")
