from datetime import date
from types import SimpleNamespace
from unittest import mock

from django import forms
from django.db import IntegrityError
from django.test import RequestFactory, TestCase
from django.utils.translation import override as override_language

from contacts.models import Contact, ContactType
from wms.models import (
    Carton,
    CartonStatus,
    Destination,
    OrganizationRole,
    OrganizationRoleAssignment,
    RecipientBinding,
    Shipment,
    ShipmentStatus,
    ShipperScope,
)
from wms.scan_shipment_handlers import (
    _get_carton_count,
    _handle_shipment_save_draft_post,
    handle_shipment_create_post,
    handle_shipment_edit_post,
)
from wms.services import StockError
from wms.shipment_helpers import parse_shipment_lines


class _FakeForm:
    def __init__(self, *, valid, cleaned_data=None, data=None, fields=None):
        self._valid = valid
        self.cleaned_data = cleaned_data or {}
        self.data = data or {}
        self.fields = fields or {}
        self.errors = []

    def is_valid(self):
        return self._valid

    def add_error(self, field, error):
        self.errors.append((field, str(error)))


class ScanShipmentHandlersTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=1, username="scanner")

    def _request(self, data=None):
        request = self.factory.post("/scan/shipment/", data or {})
        request.user = self.user
        return request

    def _cleaned_data(self, *, carton_count=2):
        suffix = Destination.objects.count() + 1
        correspondent = Contact.objects.create(
            name=f"Correspondant {suffix}",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        destination = Destination.objects.create(
            city=f"Paris {suffix}",
            iata_code=f"T{suffix:03d}",
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper = Contact.objects.create(
            name="ASF",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient = Contact.objects.create(
            name="Association Dest",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_assignment = OrganizationRoleAssignment.objects.create(
            organization=shipper,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=recipient,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            destination=destination,
            is_active=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper,
            recipient_org=recipient,
            destination=destination,
            is_active=True,
        )
        return {
            "carton_count": carton_count,
            "destination": destination,
            "shipper_contact": shipper,
            "recipient_contact": recipient,
            "correspondent_contact": correspondent,
        }

    def test_handle_shipment_save_draft_translates_unavailable_correspondent_error(self):
        linked_correspondent = Contact.objects.create(
            name="Correspondent linked",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Paris",
            iata_code="PAR",
            country="France",
            correspondent_contact=linked_correspondent,
            is_active=True,
        )
        unavailable_correspondent = Contact.objects.create(
            name="Correspondent unavailable",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        request = self._request(
            {
                "destination": str(destination.id),
                "correspondent_contact": str(unavailable_correspondent.id),
            }
        )
        form = _FakeForm(
            valid=False,
            data=request.POST,
            fields={
                "destination": forms.ModelChoiceField(
                    queryset=Destination.objects.filter(pk=destination.pk)
                ),
                "correspondent_contact": forms.ModelChoiceField(
                    queryset=Contact.objects.none(),
                    required=False,
                ),
            },
        )

        with override_language("en"):
            response = _handle_shipment_save_draft_post(request, form=form)

        self.assertIsNone(response)
        self.assertEqual(
            form.errors,
            [("correspondent_contact", "Contact unavailable for this destination.")],
        )

    def test_get_carton_count_uses_form_when_valid(self):
        request = self._request({"carton_count": "10"})
        form = _FakeForm(valid=True, cleaned_data={"carton_count": 4})
        self.assertEqual(_get_carton_count(form, request), 4)

    def test_get_carton_count_handles_invalid_values(self):
        form = _FakeForm(valid=False)
        self.assertEqual(_get_carton_count(form, self._request({"carton_count": "0"})), 1)
        self.assertEqual(_get_carton_count(form, self._request({"carton_count": "bad"})), 1)

    def test_parse_shipment_lines_keeps_expiry_for_product_lines(self):
        product = SimpleNamespace(id=7, name="Produit test")

        with mock.patch("wms.shipment_helpers.resolve_product", return_value=product):
            line_values, line_items, line_errors = parse_shipment_lines(
                carton_count=1,
                data={
                    "line_1_product_code": "SKU-1",
                    "line_1_quantity": "2",
                    "line_1_expires_on": "2026-02-01",
                },
                allowed_carton_ids=set(),
            )

        self.assertEqual(line_errors, {})
        self.assertEqual(line_values[0]["expires_on"], "2026-02-01")
        self.assertEqual(line_items[0]["expires_on"], date(2026, 2, 1))

    def test_parse_shipment_lines_keeps_preassignment_confirmation_for_selected_carton(self):
        line_values, line_items, line_errors = parse_shipment_lines(
            carton_count=1,
            data={
                "line_1_carton_id": "12",
                "line_1_preassigned_destination_confirmed": "1",
            },
            allowed_carton_ids={"12"},
        )

        self.assertEqual(line_errors, {})
        self.assertEqual(line_values[0]["carton_id"], "12")
        self.assertEqual(line_items[0]["carton_id"], 12)
        self.assertTrue(line_items[0]["preassigned_destination_confirmed"])

    def test_handle_shipment_create_post_success(self):
        request = self._request({"carton_count": "2"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=2))
        shipment = SimpleNamespace(reference="S-001")
        carton = SimpleNamespace(shipment=None, save=mock.Mock())
        carton_query = mock.MagicMock()
        carton_query.select_related.return_value = carton_query
        carton_query.select_for_update.return_value = carton_query
        carton_query.first.return_value = carton

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=(
                [{"line": 1}],
                [{"carton_id": 10}, {"product": "P", "quantity": 3}],
                {},
            ),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.build_destination_label",
                return_value="Paris - France",
            ):
                with mock.patch(
                    "wms.scan_shipment_handlers.Shipment.objects.create",
                    return_value=shipment,
                ):
                    with mock.patch(
                        "wms.scan_shipment_handlers.Carton.objects.filter",
                        return_value=carton_query,
                    ):
                        with mock.patch("wms.scan_shipment_handlers.pack_carton") as pack_mock:
                            with mock.patch(
                                "wms.scan_shipment_handlers.sync_shipment_ready_state"
                            ) as sync_mock:
                                with mock.patch("wms.scan_shipment_handlers.messages.success"):
                                    with mock.patch(
                                        "wms.scan_shipment_handlers.redirect",
                                        return_value=SimpleNamespace(status_code=302, url="/next"),
                                    ) as redirect_mock:
                                        with mock.patch(
                                            "wms.scan_shipment_handlers.connection",
                                            SimpleNamespace(
                                                features=SimpleNamespace(has_select_for_update=True)
                                            ),
                                        ):
                                            response, carton_count, line_values, line_errors = (
                                                handle_shipment_create_post(
                                                    request,
                                                    form=form,
                                                    available_carton_ids={10},
                                                )
                                            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(carton_count, 2)
        self.assertEqual(line_values, [{"line": 1}])
        self.assertEqual(line_errors, {})
        carton.save.assert_called_once_with(
            update_fields=["shipment", "preassigned_destination", "status"]
        )
        pack_mock.assert_called_once()
        sync_mock.assert_called_once_with(shipment)
        redirect_mock.assert_called_once_with("scan:scan_shipment_create")

    def test_handle_shipment_create_post_adds_form_error_on_unavailable_carton(self):
        request = self._request({"carton_count": "1"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=1))
        shipment = SimpleNamespace(reference="S-002")
        carton_query = mock.MagicMock()
        carton_query.select_related.return_value = carton_query
        carton_query.first.return_value = None

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [{"carton_id": 22}], {}),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.build_destination_label",
                return_value="Paris - France",
            ):
                with mock.patch(
                    "wms.scan_shipment_handlers.Shipment.objects.create",
                    return_value=shipment,
                ):
                    with mock.patch(
                        "wms.scan_shipment_handlers.Carton.objects.filter",
                        return_value=carton_query,
                    ):
                        response, _count, _lines, _errors = handle_shipment_create_post(
                            request,
                            form=form,
                            available_carton_ids={22},
                        )

        self.assertIsNone(response)
        self.assertIn((None, "Carton indisponible."), form.errors)

    def test_handle_shipment_create_post_rejects_preassigned_destination_mismatch_without_confirmation(
        self,
    ):
        correspondent = Contact.objects.create(
            name="Correspondent mismatch",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        preassigned_destination = Destination.objects.create(
            city="Nouakchott",
            iata_code="NKC",
            country="Mauritanie",
            correspondent_contact=correspondent,
            is_active=True,
        )
        target_destination = Destination.objects.create(
            city="Conakry",
            iata_code="CKY",
            country="Guinee",
            correspondent_contact=correspondent,
            is_active=True,
        )
        carton = Carton.objects.create(
            code="MM-00001",
            status=CartonStatus.PACKED,
            preassigned_destination=preassigned_destination,
        )
        request = self._request({"carton_count": "1"})
        cleaned_data = self._cleaned_data(carton_count=1)
        shipper_contact = Contact.objects.create(
            name="ASF mismatch create",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_contact = Contact.objects.create(
            name="Association mismatch create",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_assignment = OrganizationRoleAssignment.objects.create(
            organization=shipper_contact,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=recipient_contact,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            destination=target_destination,
            is_active=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_contact,
            recipient_org=recipient_contact,
            destination=target_destination,
            is_active=True,
        )
        cleaned_data["destination"] = target_destination
        cleaned_data["shipper_contact"] = shipper_contact
        cleaned_data["recipient_contact"] = recipient_contact
        cleaned_data["correspondent_contact"] = correspondent
        form = _FakeForm(valid=True, cleaned_data=cleaned_data)

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=(
                [
                    {
                        "carton_id": str(carton.id),
                        "product_code": "",
                        "quantity": "",
                        "expires_on": "",
                    }
                ],
                [{"carton_id": carton.id, "preassigned_destination_confirmed": False}],
                {},
            ),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.Shipment.objects.create",
                return_value=SimpleNamespace(reference="S-003"),
            ):
                response, *_ = handle_shipment_create_post(
                    request,
                    form=form,
                    available_carton_ids={str(carton.id)},
                )

        self.assertIsNone(response)
        self.assertIn(
            (
                None,
                "Ce colis a été pré-affecté pour la destination "
                f"{preassigned_destination}. Voulez vous vraiment l'affecter à "
                f"l'expédition en cours pour la destination {target_destination} ?",
            ),
            form.errors,
        )

    def test_handle_shipment_edit_post_accepts_preassigned_destination_mismatch_with_confirmation(
        self,
    ):
        correspondent = Contact.objects.create(
            name="Correspondent edit mismatch",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        preassigned_destination = Destination.objects.create(
            city="Nouakchott",
            iata_code="NKC",
            country="Mauritanie",
            correspondent_contact=correspondent,
            is_active=True,
        )
        target_destination = Destination.objects.create(
            city="Conakry",
            iata_code="CKY",
            country="Guinee",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name="ASF",
            recipient_name="Association Dest",
            destination=target_destination,
            destination_address=str(target_destination),
            destination_country=target_destination.country,
        )
        shipper_contact = Contact.objects.create(
            name="ASF shipment edit",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_contact = Contact.objects.create(
            name="Association shipment edit",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        correspondent_contact = Contact.objects.create(
            name="Correspondent shipment edit",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        shipper_assignment = OrganizationRoleAssignment.objects.create(
            organization=shipper_contact,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=recipient_contact,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            destination=target_destination,
            is_active=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_contact,
            recipient_org=recipient_contact,
            destination=target_destination,
            is_active=True,
        )
        carton = Carton.objects.create(
            code="MM-00002",
            status=CartonStatus.PACKED,
            preassigned_destination=preassigned_destination,
        )
        request = self._request({"carton_count": "1"})
        cleaned_data = self._cleaned_data(carton_count=1)
        cleaned_data["destination"] = target_destination
        cleaned_data["shipper_contact"] = shipper_contact
        cleaned_data["recipient_contact"] = recipient_contact
        cleaned_data["correspondent_contact"] = correspondent_contact
        form = _FakeForm(valid=True, cleaned_data=cleaned_data)

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=(
                [
                    {
                        "carton_id": str(carton.id),
                        "product_code": "",
                        "quantity": "",
                        "expires_on": "",
                    }
                ],
                [{"carton_id": carton.id, "preassigned_destination_confirmed": True}],
                {},
            ),
        ):
            with mock.patch("wms.scan_shipment_handlers.sync_shipment_ready_state"):
                with mock.patch("wms.scan_shipment_handlers.messages.success"):
                    response, *_ = handle_shipment_edit_post(
                        request,
                        form=form,
                        shipment=shipment,
                        allowed_carton_ids={str(carton.id)},
                    )

        self.assertEqual(response.status_code, 302)
        carton.refresh_from_db()
        self.assertEqual(carton.shipment_id, shipment.id)
        self.assertEqual(carton.status, CartonStatus.ASSIGNED)
        self.assertIsNone(carton.preassigned_destination)

    def test_handle_shipment_create_post_adds_form_error_on_integrity_error(self):
        request = self._request({"carton_count": "1"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=1))

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=(
                [{"carton_id": "", "product_code": "P-001", "quantity": "1"}],
                [{"product": "P", "quantity": 1}],
                {},
            ),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.build_destination_label",
                return_value="Paris - France",
            ):
                with mock.patch(
                    "wms.scan_shipment_handlers.Shipment.objects.create",
                    side_effect=IntegrityError("duplicate key"),
                ):
                    with mock.patch("wms.scan_shipment_handlers.logger.exception") as log_mock:
                        response, carton_count, line_values, line_errors = (
                            handle_shipment_create_post(
                                request,
                                form=form,
                                available_carton_ids=set(),
                            )
                        )

        self.assertIsNone(response)
        self.assertEqual(carton_count, 1)
        self.assertEqual(
            line_values,
            [{"carton_id": "", "product_code": "P-001", "quantity": "1"}],
        )
        self.assertEqual(line_errors, {})
        self.assertIn(
            (
                None,
                "Erreur technique lors de la création de l'expédition. Merci de réessayer.",
            ),
            form.errors,
        )
        log_mock.assert_called_once()

    def test_handle_shipment_create_post_skips_processing_when_line_errors_present(self):
        request = self._request({"carton_count": "3"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=3))

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [], {"1": "invalid"}),
        ):
            with mock.patch("wms.scan_shipment_handlers.Shipment.objects.create") as create_mock:
                response, carton_count, line_values, line_errors = handle_shipment_create_post(
                    request,
                    form=form,
                    available_carton_ids=set(),
                )

        self.assertIsNone(response)
        self.assertEqual(carton_count, 3)
        self.assertEqual(line_values, [{"line": 1}])
        self.assertEqual(line_errors, {"1": "invalid"})
        create_mock.assert_not_called()

    def test_handle_shipment_create_post_save_draft_ignores_line_errors(self):
        request = self._request({"action": "save_draft", "carton_count": "1"})
        form = _FakeForm(valid=False)
        expected_response = SimpleNamespace(status_code=302, url="/shipment/1/edit")

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [], {"1": ["missing"]}),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers._handle_shipment_save_draft_post",
                return_value=expected_response,
            ) as save_draft_mock:
                response, carton_count, line_values, line_errors = handle_shipment_create_post(
                    request,
                    form=form,
                    available_carton_ids=set(),
                )

        self.assertEqual(response, expected_response)
        self.assertEqual(carton_count, 1)
        self.assertEqual(line_values, [{"line": 1}])
        self.assertEqual(line_errors, {})
        save_draft_mock.assert_called_once_with(
            request,
            form=form,
            redirect_to_pack=False,
        )

    def test_handle_shipment_create_post_save_draft_pack_redirects_to_pack_flow(self):
        request = self._request({"action": "save_draft_pack", "carton_count": "1"})
        form = _FakeForm(valid=False)
        expected_response = SimpleNamespace(status_code=302, url="/scan/pack/")

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [], {"1": ["missing"]}),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers._handle_shipment_save_draft_post",
                return_value=expected_response,
            ) as save_draft_mock:
                response, carton_count, line_values, line_errors = handle_shipment_create_post(
                    request,
                    form=form,
                    available_carton_ids=set(),
                )

        self.assertEqual(response, expected_response)
        self.assertEqual(carton_count, 1)
        self.assertEqual(line_values, [{"line": 1}])
        self.assertEqual(line_errors, {})
        save_draft_mock.assert_called_once_with(
            request,
            form=form,
            redirect_to_pack=True,
        )

    def test_handle_shipment_edit_post_success(self):
        request = self._request({"carton_count": "2"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=2))
        shipment = SimpleNamespace(
            id=50,
            reference="S-EDIT-001",
            status=ShipmentStatus.DRAFT,
            carton_set=mock.MagicMock(),
            save=mock.Mock(),
        )
        carton_to_remove = SimpleNamespace(
            status=CartonStatus.PACKED, shipment=shipment, save=mock.Mock()
        )
        shipment.carton_set.exclude.return_value = [carton_to_remove]
        selected_carton = SimpleNamespace(
            shipment_id=None,
            shipment=None,
            status=CartonStatus.PACKED,
            save=mock.Mock(),
        )
        carton_query = mock.MagicMock()
        carton_query.select_related.return_value = carton_query
        carton_query.select_for_update.return_value = carton_query
        carton_query.first.return_value = selected_carton

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=(
                [{"line": 1}],
                [{"carton_id": 99}, {"product": "P", "quantity": 1}],
                {},
            ),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.build_destination_label",
                return_value="Paris - France",
            ):
                with mock.patch(
                    "wms.scan_shipment_handlers.Carton.objects.filter",
                    return_value=carton_query,
                ):
                    with mock.patch("wms.scan_shipment_handlers.pack_carton") as pack_mock:
                        with mock.patch(
                            "wms.scan_shipment_handlers.sync_shipment_ready_state"
                        ) as sync_mock:
                            with mock.patch("wms.scan_shipment_handlers.messages.success"):
                                with mock.patch(
                                    "wms.scan_shipment_handlers.redirect",
                                    return_value=SimpleNamespace(status_code=302, url="/ready"),
                                ) as redirect_mock:
                                    with mock.patch(
                                        "wms.scan_shipment_handlers.connection",
                                        SimpleNamespace(
                                            features=SimpleNamespace(has_select_for_update=True)
                                        ),
                                    ):
                                        response, carton_count, line_values, line_errors = (
                                            handle_shipment_edit_post(
                                                request,
                                                form=form,
                                                shipment=shipment,
                                                allowed_carton_ids={99},
                                            )
                                        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(carton_count, 2)
        self.assertEqual(line_values, [{"line": 1}])
        self.assertEqual(line_errors, {})
        shipment.save.assert_called_once()
        carton_to_remove.save.assert_called_once_with(update_fields=["shipment"])
        selected_carton.save.assert_called_once_with(
            update_fields=["shipment", "preassigned_destination", "status"]
        )
        pack_mock.assert_called_once()
        sync_mock.assert_called_once_with(shipment)
        redirect_mock.assert_called_once_with("scan:scan_shipments_ready")

    def test_handle_shipment_edit_post_uses_reserved_stock_for_related_order(self):
        request = self._request({"carton_count": "1"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=1))
        related_order_line = SimpleNamespace(product_id=7, remaining_quantity=4)
        lines_manager = mock.MagicMock()
        lines_manager.select_related.return_value.all.return_value = [related_order_line]
        shipment = SimpleNamespace(
            id=53,
            reference="S-EDIT-RESERVED",
            status=ShipmentStatus.DRAFT,
            carton_set=mock.MagicMock(),
            save=mock.Mock(),
            order=SimpleNamespace(lines=lines_manager),
        )
        shipment.carton_set.exclude.return_value = []
        product = SimpleNamespace(id=7, name="Produit reserve")
        reserved_carton = SimpleNamespace()

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [{"product": product, "quantity": 2}], {}),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.build_destination_label",
                return_value="Paris - France",
            ):
                with mock.patch(
                    "wms.scan_shipment_handlers.pack_carton_from_reserved",
                    return_value=reserved_carton,
                ) as reserved_mock:
                    with mock.patch("wms.scan_shipment_handlers.pack_carton") as pack_mock:
                        with mock.patch("wms.scan_shipment_handlers.set_carton_status"):
                            with mock.patch("wms.scan_shipment_handlers.sync_shipment_ready_state"):
                                with mock.patch("wms.scan_shipment_handlers.messages.success"):
                                    with mock.patch(
                                        "wms.scan_shipment_handlers.redirect",
                                        return_value=SimpleNamespace(
                                            status_code=302,
                                            url="/ready",
                                        ),
                                    ):
                                        response, *_ = handle_shipment_edit_post(
                                            request,
                                            form=form,
                                            shipment=shipment,
                                            allowed_carton_ids=set(),
                                        )

        self.assertEqual(response.status_code, 302)
        reserved_mock.assert_called_once_with(
            user=request.user,
            line=related_order_line,
            quantity=2,
            carton=None,
            shipment=shipment,
            display_expires_on=None,
        )
        pack_mock.assert_not_called()

    def test_handle_shipment_edit_post_rejects_product_outside_related_order(self):
        request = self._request({"carton_count": "1"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=1))
        related_order_line = SimpleNamespace(product_id=7, remaining_quantity=4)
        lines_manager = mock.MagicMock()
        lines_manager.select_related.return_value.all.return_value = [related_order_line]
        shipment = SimpleNamespace(
            id=54,
            reference="S-EDIT-ORDER-MISS",
            status=ShipmentStatus.DRAFT,
            carton_set=mock.MagicMock(),
            save=mock.Mock(),
            order=SimpleNamespace(lines=lines_manager),
        )
        shipment.carton_set.exclude.return_value = []
        product = SimpleNamespace(id=99, name="Produit inconnu")

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [{"product": product, "quantity": 1}], {}),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.build_destination_label",
                return_value="Paris - France",
            ):
                with mock.patch(
                    "wms.scan_shipment_handlers.pack_carton_from_reserved"
                ) as reserved_mock:
                    response, *_ = handle_shipment_edit_post(
                        request,
                        form=form,
                        shipment=shipment,
                        allowed_carton_ids=set(),
                    )

        self.assertIsNone(response)
        self.assertIn((None, "Produit non présent dans la commande liée."), form.errors)
        reserved_mock.assert_not_called()

    def test_handle_shipment_edit_post_rejects_removal_of_shipped_carton(self):
        request = self._request({"carton_count": "1"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=1))
        shipment = SimpleNamespace(
            id=51,
            reference="S-EDIT-002",
            status=ShipmentStatus.DRAFT,
            carton_set=mock.MagicMock(),
            save=mock.Mock(),
        )
        shipment.carton_set.exclude.return_value = [SimpleNamespace(status=CartonStatus.SHIPPED)]

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [], {}),
        ):
            response, _count, _lines, _errors = handle_shipment_edit_post(
                request,
                form=form,
                shipment=shipment,
                allowed_carton_ids=set(),
            )

        self.assertIsNone(response)
        self.assertIn((None, "Impossible de retirer un carton expédié."), form.errors)

    def test_handle_shipment_edit_post_rejects_missing_or_unavailable_selected_carton(self):
        request = self._request({"carton_count": "1"})
        form_missing = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=1))
        shipment = SimpleNamespace(
            id=52,
            reference="S-EDIT-003",
            status=ShipmentStatus.DRAFT,
            carton_set=mock.MagicMock(),
            save=mock.Mock(),
        )
        shipment.carton_set.exclude.return_value = []
        missing_query = mock.MagicMock()
        missing_query.select_related.return_value = missing_query
        missing_query.first.return_value = None

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [{"carton_id": 123}], {}),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.Carton.objects.filter",
                return_value=missing_query,
            ):
                response, *_ = handle_shipment_edit_post(
                    request,
                    form=form_missing,
                    shipment=shipment,
                    allowed_carton_ids={123},
                )
        self.assertIsNone(response)
        self.assertIn((None, "Carton introuvable."), form_missing.errors)

        form_unavailable = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=1))
        unavailable_query = mock.MagicMock()
        unavailable_query.select_related.return_value = unavailable_query
        unavailable_query.first.return_value = SimpleNamespace(
            shipment_id=999, shipment=None, status=CartonStatus.PACKED, save=mock.Mock()
        )
        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [{"carton_id": 123}], {}),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.Carton.objects.filter",
                return_value=unavailable_query,
            ):
                response, *_ = handle_shipment_edit_post(
                    request,
                    form=form_unavailable,
                    shipment=shipment,
                    allowed_carton_ids={123},
                )
        self.assertIsNone(response)
        self.assertIn((None, "Carton indisponible."), form_unavailable.errors)

    def test_handle_shipment_edit_post_rejects_locked_shipment(self):
        request = self._request({"carton_count": "1"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=1))
        shipment = SimpleNamespace(
            id=55,
            reference="S-LOCKED",
            status=ShipmentStatus.PLANNED,
            carton_set=mock.MagicMock(),
            save=mock.Mock(),
        )

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [], {}),
        ):
            response, *_ = handle_shipment_edit_post(
                request,
                form=form,
                shipment=shipment,
                allowed_carton_ids=set(),
            )

        self.assertIsNone(response)
        self.assertIn(
            (None, "Expédition verrouillée: modification des colis impossible."),
            form.errors,
        )

    def test_handle_shipment_edit_post_rejects_disputed_shipment(self):
        request = self._request({"carton_count": "1"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=1))
        shipment = SimpleNamespace(
            id=56,
            reference="S-DISPUTED",
            status=ShipmentStatus.DRAFT,
            is_disputed=True,
            carton_set=mock.MagicMock(),
            save=mock.Mock(),
        )

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [], {}),
        ):
            response, *_ = handle_shipment_edit_post(
                request,
                form=form,
                shipment=shipment,
                allowed_carton_ids=set(),
            )

        self.assertIsNone(response)
        self.assertIn(
            (None, "Expédition en litige: modification des colis impossible."),
            form.errors,
        )

    def test_handle_shipment_edit_post_rejects_selected_carton_not_packed(self):
        request = self._request({"carton_count": "1"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=1))
        shipment = SimpleNamespace(
            id=57,
            reference="S-EDIT-NOT-PACKED",
            status=ShipmentStatus.DRAFT,
            carton_set=mock.MagicMock(),
            save=mock.Mock(),
        )
        shipment.carton_set.exclude.return_value = []
        unavailable_query = mock.MagicMock()
        unavailable_query.select_related.return_value = unavailable_query
        unavailable_query.first.return_value = SimpleNamespace(
            shipment_id=None,
            status=CartonStatus.ASSIGNED,
            shipment=None,
        )

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [{"carton_id": 123}], {}),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.build_destination_label",
                return_value="Paris - France",
            ):
                with mock.patch(
                    "wms.scan_shipment_handlers.Carton.objects.filter",
                    return_value=unavailable_query,
                ):
                    response, *_ = handle_shipment_edit_post(
                        request,
                        form=form,
                        shipment=shipment,
                        allowed_carton_ids={123},
                    )

        self.assertIsNone(response)
        self.assertIn((None, "Carton indisponible."), form.errors)

    def test_handle_shipment_edit_post_rejects_quantity_above_related_order_remaining(self):
        request = self._request({"carton_count": "1"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=1))
        related_order_line = SimpleNamespace(product_id=7, remaining_quantity=1)
        lines_manager = mock.MagicMock()
        lines_manager.select_related.return_value.all.return_value = [related_order_line]
        product = SimpleNamespace(id=7, name="Produit limite")
        shipment = SimpleNamespace(
            id=58,
            reference="S-EDIT-ORDER-QTY",
            status=ShipmentStatus.DRAFT,
            carton_set=mock.MagicMock(),
            save=mock.Mock(),
            order=SimpleNamespace(lines=lines_manager),
        )
        shipment.carton_set.exclude.return_value = []

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [{"product": product, "quantity": 2}], {}),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.build_destination_label",
                return_value="Paris - France",
            ):
                with mock.patch(
                    "wms.scan_shipment_handlers.pack_carton_from_reserved"
                ) as reserved_mock:
                    response, *_ = handle_shipment_edit_post(
                        request,
                        form=form,
                        shipment=shipment,
                        allowed_carton_ids=set(),
                    )

        self.assertIsNone(response)
        self.assertIn(
            (
                None,
                "Produit limite: quantité demandée supérieure au reliquat de la commande.",
            ),
            form.errors,
        )
        reserved_mock.assert_not_called()
