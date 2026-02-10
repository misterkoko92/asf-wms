from types import SimpleNamespace
from unittest import mock

from django import forms
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings

from contacts.models import Contact, ContactTag, ContactType
from wms import models
from wms.admin import (
    AccountDocumentAdmin,
    CartonAdmin,
    CartonItemInline,
    DestinationAdmin,
    OrderAdmin,
    ProductAdmin,
    ProductLotAdmin,
    PublicAccountRequestAdmin,
    RackColorAdmin,
    RackColorAdminForm,
    ReceiptAdmin,
    ReceiptLineAdmin,
    ShipmentAdmin,
    StockMovementAdmin,
)
from wms.services import StockError


class _AdminTestBase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        User = get_user_model()
        self.user = User.objects.create_user("staff", "staff@example.com", "pass1234")
        self.superuser = User.objects.create_superuser(
            "admin",
            "admin@example.com",
            "pass1234",
        )
        self.contact = Contact.objects.create(
            name="Org A",
            contact_type=ContactType.ORGANIZATION,
        )
        self.warehouse = models.Warehouse.objects.create(name="WH1")
        self.location = models.Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.product = models.Product.objects.create(
            sku="SKU-ADMIN",
            name="Produit Admin",
            brand="ADMIN",
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )
        self.destination = models.Destination.objects.create(
            city="Paris",
            iata_code="PAR",
            country="France",
            correspondent_contact=self.contact,
            is_active=True,
        )

    def _request(self, *, superuser=False):
        request = self.factory.get("/admin/")
        request.user = self.superuser if superuser else self.user
        return request

    def _shipment(self, **overrides):
        data = {
            "reference": "260100",
            "shipper_name": "Shipper",
            "recipient_name": "Recipient",
            "correspondent_name": "Correspondent",
            "destination": self.destination,
            "destination_address": "10 Rue Test",
            "destination_country": "France",
        }
        data.update(overrides)
        return models.Shipment.objects.create(**data)


class ProductAdminTests(_AdminTestBase):
    def test_preview_and_simple_actions(self):
        admin_obj = ProductAdmin(models.Product, self.site)
        request = self._request()

        self.assertEqual(admin_obj.qr_code_preview(SimpleNamespace(qr_code_image=None)), "-")
        self.assertEqual(admin_obj.photo_preview(SimpleNamespace(photo=None)), "-")

        obj_with_media = SimpleNamespace(
            qr_code_image=SimpleNamespace(url="/media/qr.png"),
            photo=SimpleNamespace(url="/media/photo.png"),
        )
        self.assertIn("/media/qr.png", admin_obj.qr_code_preview(obj_with_media))
        self.assertIn("/media/photo.png", admin_obj.photo_preview(obj_with_media))

        p1 = models.Product.objects.create(
            sku="ARCH-1",
            name="Archive One",
            qr_code_image="qr_codes/a1.png",
            is_active=True,
        )
        p2 = models.Product.objects.create(
            sku="ARCH-2",
            name="Archive Two",
            qr_code_image="qr_codes/a2.png",
            is_active=False,
        )
        with mock.patch.object(admin_obj, "message_user") as message_user_mock:
            admin_obj.archive_products(request, models.Product.objects.filter(pk__in=[p1.pk, p2.pk]))
            admin_obj.unarchive_products(request, models.Product.objects.filter(pk__in=[p1.pk, p2.pk]))
        self.assertEqual(message_user_mock.call_count, 2)
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertTrue(p1.is_active)
        self.assertTrue(p2.is_active)

    def test_generate_qr_codes_and_empty_print_actions(self):
        admin_obj = ProductAdmin(models.Product, self.site)
        request = self._request()

        product_missing_qr = mock.Mock(qr_code_image="")
        product_missing_qr.generate_qr_code = mock.Mock()
        product_missing_qr.save = mock.Mock()
        product_with_qr = mock.Mock(qr_code_image="existing")
        product_with_qr.generate_qr_code = mock.Mock()
        product_with_qr.save = mock.Mock()

        with mock.patch.object(admin_obj, "message_user") as message_user_mock:
            admin_obj.generate_qr_codes(request, [product_missing_qr, product_with_qr])
            admin_obj.print_product_labels(request, models.Product.objects.none())
            admin_obj.print_product_qr_labels(request, models.Product.objects.none())

        product_missing_qr.generate_qr_code.assert_called_once()
        product_missing_qr.save.assert_called_once_with(update_fields=["qr_code_image"])
        product_with_qr.generate_qr_code.assert_not_called()
        product_with_qr.save.assert_not_called()
        self.assertEqual(message_user_mock.call_count, 3)

    def test_print_product_label_actions_non_empty(self):
        admin_obj = ProductAdmin(models.Product, self.site)
        request = self._request()

        location_b = models.Location.objects.create(
            warehouse=self.warehouse,
            zone="B",
            aisle="02",
            shelf="002",
        )
        product_a = models.Product.objects.create(
            sku="LBL-A",
            name="Label A",
            default_location=self.location,
            qr_code_image="qr_codes/lbl_a.png",
        )
        product_b = models.Product.objects.create(
            sku="LBL-B",
            name="Label B",
            default_location=location_b,
            qr_code_image="",
        )
        product_b.qr_code_image = ""
        product_b.save(update_fields=["qr_code_image"])
        models.RackColor.objects.create(warehouse=self.warehouse, zone="A", color="#FF0000")

        with mock.patch("wms.admin.get_template_layout", return_value={"blocks": []}), mock.patch(
            "wms.admin.build_product_label_context",
            side_effect=lambda product, rack_color=None: {"product": product.id, "rack": rack_color},
        ) as build_context_mock, mock.patch(
            "wms.admin.build_label_pages",
            return_value=(["p1"], {"page_rows": "4"}),
        ) as build_pages_mock, mock.patch(
            "wms.admin.render",
            return_value="labels-rendered",
        ) as render_mock:
            response = admin_obj.print_product_labels(
                request,
                models.Product.objects.filter(pk__in=[product_a.pk, product_b.pk]),
            )
        self.assertEqual(response, "labels-rendered")
        self.assertEqual(build_context_mock.call_count, 2)
        build_pages_mock.assert_called_once()
        self.assertIn("print/product_labels.html", str(render_mock.call_args))

        with mock.patch("wms.admin.get_template_layout", return_value={"blocks": []}), mock.patch(
            "wms.admin.extract_block_style",
            return_value={"page_rows": "oops", "page_columns": "bad"},
        ), mock.patch(
            "wms.admin.build_product_qr_label_context",
            side_effect=lambda product: {"product": product.id},
        ) as qr_context_mock, mock.patch(
            "wms.admin.build_label_pages",
            return_value=(["q1"], {"page_rows": "5", "page_columns": "3"}),
        ) as build_pages_mock, mock.patch(
            "wms.admin.render",
            return_value="qr-rendered",
        ) as render_mock, mock.patch(
            "wms.models.Product.generate_qr_code",
            autospec=True,
            side_effect=lambda self: setattr(self, "qr_code_image", "qr_codes/generated.png"),
        ) as generate_mock:
            response = admin_obj.print_product_qr_labels(
                request,
                models.Product.objects.filter(pk__in=[product_a.pk, product_b.pk]),
            )
        self.assertEqual(response, "qr-rendered")
        self.assertEqual(generate_mock.call_count, 1)
        self.assertEqual(qr_context_mock.call_count, 2)
        build_pages_mock.assert_called_once()
        self.assertIn("print/product_qr_labels.html", str(render_mock.call_args))

        with mock.patch("wms.admin.get_template_layout", return_value={"blocks": []}), mock.patch(
            "wms.admin.extract_block_style",
            return_value={"page_rows": "2", "page_columns": "4"},
        ), mock.patch(
            "wms.admin.build_product_qr_label_context",
            return_value={"product": 1},
        ), mock.patch(
            "wms.admin.build_label_pages",
            return_value=(["q2"], {"page_rows": "2", "page_columns": "4"}),
        ) as build_pages_mock, mock.patch(
            "wms.admin.render",
            return_value="qr-rendered-2",
        ):
            response = admin_obj.print_product_qr_labels(
                request,
                models.Product.objects.filter(pk=product_a.pk),
            )
        self.assertEqual(response, "qr-rendered-2")
        self.assertEqual(build_pages_mock.call_args.kwargs["labels_per_page"], 8)


class PublicAccountRequestAdminTests(_AdminTestBase):
    def setUp(self):
        super().setUp()
        self.admin_obj = PublicAccountRequestAdmin(models.PublicAccountRequest, self.site)
        self.account_request = models.PublicAccountRequest.objects.create(
            association_name="Association A",
            email="association-a@example.com",
            phone="+33123456789",
            address_line1="1 Rue A",
            city="Paris",
            country="France",
            status=models.PublicAccountRequestStatus.PENDING,
        )

    def test_approve_request_rejects_reserved_email(self):
        get_user_model().objects.create_superuser(
            username="reserved",
            email=self.account_request.email,
            password="pass1234",
        )
        ok, reason = self.admin_obj._approve_request(self._request(superuser=True), self.account_request)
        self.assertFalse(ok)
        self.assertEqual(reason, "email reserve")

    def test_approve_reject_save_and_access_info_branches(self):
        approved_request = models.PublicAccountRequest.objects.create(
            association_name="Association Approved",
            email="approved@example.com",
            address_line1="2 Rue B",
            status=models.PublicAccountRequestStatus.APPROVED,
        )
        get_user_model().objects.create_user(
            username="approved",
            email=approved_request.email,
            password="pass1234",
        )
        pending_request = models.PublicAccountRequest.objects.create(
            association_name="Association Pending",
            email="pending@example.com",
            address_line1="3 Rue C",
            status=models.PublicAccountRequestStatus.PENDING,
        )

        with mock.patch.object(self.admin_obj, "_approve_request", return_value=(True, "")) as approve_mock, mock.patch.object(
            self.admin_obj, "message_user"
        ) as message_user_mock:
            self.admin_obj.approve_requests(
                self._request(superuser=True),
                models.PublicAccountRequest.objects.filter(pk__in=[approved_request.pk, pending_request.pk]),
            )
        approve_mock.assert_called_once()
        self.assertEqual(message_user_mock.call_count, 2)

        with mock.patch.object(self.admin_obj, "message_user") as message_user_mock:
            self.admin_obj.reject_requests(
                self._request(superuser=True),
                models.PublicAccountRequest.objects.filter(pk=pending_request.pk),
            )
        pending_request.refresh_from_db()
        self.assertEqual(pending_request.status, models.PublicAccountRequestStatus.REJECTED)
        message_user_mock.assert_called_once()

        save_target = models.PublicAccountRequest.objects.create(
            association_name="Association Save",
            email="save@example.com",
            address_line1="4 Rue D",
            status=models.PublicAccountRequestStatus.PENDING,
        )
        save_target.status = models.PublicAccountRequestStatus.APPROVED
        with mock.patch.object(self.admin_obj, "_approve_request", return_value=(True, "")) as approve_mock, mock.patch.object(
            self.admin_obj, "message_user"
        ) as message_user_mock:
            self.admin_obj.save_model(
                self._request(superuser=True),
                save_target,
                form=mock.Mock(),
                change=True,
            )
        approve_mock.assert_called_once()
        self.assertTrue(any("Compte cree automatiquement" in str(args) for args, _ in message_user_mock.call_args_list))

        with mock.patch.object(self.admin_obj, "_approve_request", return_value=(False, "email reserve")) as approve_mock, mock.patch.object(
            self.admin_obj, "message_user"
        ) as message_user_mock:
            save_target.status = models.PublicAccountRequestStatus.APPROVED
            self.admin_obj.save_model(
                self._request(superuser=True),
                save_target,
                form=mock.Mock(),
                change=True,
            )
        approve_mock.assert_called_once()
        self.assertTrue(any("Validation ignoree" in str(args) for args, _ in message_user_mock.call_args_list))

        not_approved = models.PublicAccountRequest(
            association_name="Tmp",
            email="tmp@example.com",
            address_line1="X",
            status=models.PublicAccountRequestStatus.PENDING,
        )
        self.assertIn("Disponible apres validation", self.admin_obj.account_access_info(not_approved))

        approved_no_user = models.PublicAccountRequest(
            association_name="Tmp2",
            email="tmp2@example.com",
            address_line1="Y",
            status=models.PublicAccountRequestStatus.APPROVED,
        )
        self.assertEqual(self.admin_obj.account_access_info(approved_no_user), "Utilisateur introuvable.")

        portal_user = get_user_model().objects.create_user(
            username="portal-user",
            email="portal@example.com",
            password="pass1234",
        )
        approved_with_user = models.PublicAccountRequest(
            association_name="Tmp3",
            email=portal_user.email,
            address_line1="Z",
            status=models.PublicAccountRequestStatus.APPROVED,
        )
        with override_settings(SITE_BASE_URL=""):
            info = str(self.admin_obj.account_access_info(approved_with_user))
        self.assertIn("SITE_BASE_URL non configuree", info)

    def test_approve_request_updates_existing_contact_and_profile_contact(self):
        old_contact = Contact.objects.create(
            name="Old Contact",
            contact_type=ContactType.ORGANIZATION,
            email="old@example.com",
            phone="000",
        )
        target_contact = Contact.objects.create(
            name="Target Contact",
            contact_type=ContactType.ORGANIZATION,
            email="old@example.com",
            phone="000",
        )
        account_request = models.PublicAccountRequest.objects.create(
            association_name="Association Update",
            email="new@example.com",
            phone="+33999999999",
            address_line1="10 Rue X",
            city="Paris",
            country="France",
            contact=target_contact,
            status=models.PublicAccountRequestStatus.PENDING,
        )
        user = get_user_model().objects.create_user(
            username="existing-user",
            email=account_request.email,
            password="pass1234",
        )
        models.AssociationProfile.objects.create(user=user, contact=old_contact)

        with mock.patch("wms.admin.enqueue_email_safe") as enqueue_mock:
            ok, reason = self.admin_obj._approve_request(self._request(superuser=True), account_request)

        self.assertTrue(ok)
        self.assertEqual(reason, "")
        target_contact.refresh_from_db()
        self.assertEqual(target_contact.email, "new@example.com")
        self.assertEqual(target_contact.phone, "+33999999999")
        profile = models.AssociationProfile.objects.get(user=user)
        self.assertEqual(profile.contact_id, target_contact.id)
        self.assertTrue(profile.must_change_password)
        self.assertTrue(target_contact.tags.filter(name=ContactTag.objects.get(name="expediteur").name).exists())
        enqueue_mock.assert_called_once()

    def test_approve_requests_skip_counter_and_save_model_early_returns(self):
        pending = models.PublicAccountRequest.objects.create(
            association_name="Association Pending 2",
            email="pending2@example.com",
            address_line1="3 Rue C",
            status=models.PublicAccountRequestStatus.PENDING,
        )
        with mock.patch.object(self.admin_obj, "_approve_request", return_value=(False, "email reserve")) as approve_mock, mock.patch.object(
            self.admin_obj, "message_user"
        ) as message_user_mock:
            self.admin_obj.approve_requests(
                self._request(superuser=True),
                models.PublicAccountRequest.objects.filter(pk=pending.pk),
            )
        approve_mock.assert_called_once()
        self.assertTrue(any("ignoree" in str(args) for args, _ in message_user_mock.call_args_list))

        not_approved = models.PublicAccountRequest.objects.create(
            association_name="Association Save Early",
            email="save-early@example.com",
            address_line1="5 Rue E",
            status=models.PublicAccountRequestStatus.PENDING,
        )
        with mock.patch.object(self.admin_obj, "_approve_request") as approve_mock:
            self.admin_obj.save_model(
                self._request(superuser=True),
                not_approved,
                form=mock.Mock(),
                change=True,
            )
        approve_mock.assert_not_called()

        approved = models.PublicAccountRequest.objects.create(
            association_name="Association Save Approved",
            email="save-approved@example.com",
            address_line1="6 Rue F",
            status=models.PublicAccountRequestStatus.APPROVED,
        )
        get_user_model().objects.create_user(
            username="save-approved-user",
            email=approved.email,
            password="pass1234",
        )
        with mock.patch.object(self.admin_obj, "_approve_request") as approve_mock:
            self.admin_obj.save_model(
                self._request(superuser=True),
                approved,
                form=mock.Mock(),
                change=True,
            )
        approve_mock.assert_not_called()

    def test_approve_request_creates_contact_and_user_when_missing(self):
        account_request = models.PublicAccountRequest.objects.create(
            association_name="Association New",
            email="new-association@example.com",
            phone="+33111111111",
            address_line1="12 Rue New",
            city="Lyon",
            postal_code="69001",
            country="France",
            status=models.PublicAccountRequestStatus.PENDING,
        )
        self.assertFalse(Contact.objects.filter(email=account_request.email).exists())
        self.assertFalse(
            get_user_model().objects.filter(email__iexact=account_request.email).exists()
        )

        with mock.patch("wms.admin.enqueue_email_safe") as enqueue_mock:
            ok, reason = self.admin_obj._approve_request(
                self._request(superuser=True), account_request
            )

        self.assertTrue(ok)
        self.assertEqual(reason, "")
        account_request.refresh_from_db()
        self.assertIsNotNone(account_request.contact_id)
        created_contact = Contact.objects.get(pk=account_request.contact_id)
        self.assertEqual(created_contact.name, "Association New")
        created_user = get_user_model().objects.get(email__iexact=account_request.email)
        self.assertFalse(created_user.has_usable_password())
        profile = models.AssociationProfile.objects.get(user=created_user)
        self.assertEqual(profile.contact_id, created_contact.id)
        self.assertTrue(profile.must_change_password)
        enqueue_mock.assert_called_once()


class RackColorAdminFormTests(_AdminTestBase):
    def test_init_and_clean_behaviors(self):
        instance = models.RackColor(
            warehouse=self.warehouse,
            zone="Z",
            color="#AABBCC",
        )
        form = RackColorAdminForm(instance=instance)
        self.assertIn(("Z", "Z"), form.fields["zone"].choices)
        self.assertEqual(form.fields["color_picker"].initial, "#AABBCC")

        valid_color = RackColorAdminForm(
            data={
                "warehouse": self.warehouse.id,
                "zone": "A",
                "color": "#111111",
                "color_picker": "",
            }
        )
        self.assertTrue(valid_color.is_valid())
        self.assertEqual(valid_color.cleaned_data["color"], "#111111")

        color_from_picker_form = RackColorAdminForm()
        color_from_picker_form.cleaned_data = {"color": "", "color_picker": "#222222"}
        self.assertEqual(color_from_picker_form.clean_color(), "#222222")

        missing_color_form = RackColorAdminForm()
        missing_color_form.cleaned_data = {"color": "", "color_picker": ""}
        with self.assertRaisesMessage(forms.ValidationError, "Couleur requise"):
            missing_color_form.clean_color()

        invalid_zone = RackColorAdminForm(
            data={
                "warehouse": self.warehouse.id,
                "zone": "B",
                "color": "#123456",
                "color_picker": "",
            },
            instance=models.RackColor(warehouse=self.warehouse, zone="B", color="#123456"),
        )
        self.assertFalse(invalid_zone.is_valid())
        self.assertIn("Rack inexistant", invalid_zone.errors["zone"][0])

        invalid_warehouse_form = RackColorAdminForm(
            data={"warehouse": "abc", "zone": "A", "color": "#123456", "color_picker": ""}
        )
        self.assertIn(("A", "A"), invalid_warehouse_form.fields["zone"].choices)

        rack_admin = RackColorAdmin(models.RackColor, self.site)
        self.assertEqual(rack_admin.rack(SimpleNamespace(zone="R1")), "R1")


class DocumentAndReceiptAdminTests(_AdminTestBase):
    def test_document_status_actions_and_receipt_actions(self):
        account_request = models.PublicAccountRequest.objects.create(
            association_name="Association Doc",
            email="doc@example.com",
            address_line1="10 Rue Doc",
        )
        document = models.AccountDocument.objects.create(
            association_contact=self.contact,
            account_request=account_request,
            doc_type=models.AccountDocumentType.STATUTES,
            file=SimpleUploadedFile("doc.pdf", b"doc"),
        )
        account_admin = AccountDocumentAdmin(models.AccountDocument, self.site)
        request = self._request(superuser=True)

        with mock.patch.object(account_admin, "message_user") as message_user_mock:
            account_admin.mark_approved(request, models.AccountDocument.objects.filter(pk=document.pk))
            account_admin.mark_rejected(request, models.AccountDocument.objects.filter(pk=document.pk))
        self.assertEqual(message_user_mock.call_count, 2)
        document.refresh_from_db()
        self.assertEqual(document.status, models.DocumentReviewStatus.REJECTED)

        receipt = models.Receipt.objects.create(
            reference="REC-ADMIN",
            warehouse=self.warehouse,
        )
        line_ok = models.ReceiptLine.objects.create(
            receipt=receipt,
            product=self.product,
            quantity=1,
            location=self.location,
        )
        line_err = models.ReceiptLine.objects.create(
            receipt=receipt,
            product=self.product,
            quantity=2,
            location=self.location,
        )
        receipt_admin = ReceiptAdmin(models.Receipt, self.site)
        with mock.patch("wms.admin.receive_receipt_line", side_effect=[None, StockError("boom")]), mock.patch.object(
            receipt_admin, "message_user"
        ) as message_user_mock:
            receipt_admin.receive_lines(request, models.Receipt.objects.filter(pk=receipt.pk))
        self.assertTrue(any("ligne(s) receptionnee(s)" in str(args) for args, _ in message_user_mock.call_args_list))
        self.assertTrue(any("boom" in str(args) for args, _ in message_user_mock.call_args_list))

        receipt_line_admin = ReceiptLineAdmin(models.ReceiptLine, self.site)
        with mock.patch("wms.admin.receive_receipt_line", side_effect=[None, StockError("boom2")]), mock.patch.object(
            receipt_line_admin, "message_user"
        ) as message_user_mock:
            receipt_line_admin.receive_selected_lines(
                request,
                models.ReceiptLine.objects.filter(pk__in=[line_ok.pk, line_err.pk]),
            )
        self.assertTrue(any("ligne(s) receptionnee(s)" in str(args) for args, _ in message_user_mock.call_args_list))
        self.assertTrue(any("boom2" in str(args) for args, _ in message_user_mock.call_args_list))

        received_lot = models.ProductLot.objects.create(
            product=self.product,
            lot_code="LOT-RCV",
            quantity_on_hand=1,
            location=self.location,
        )
        receipt_with_received_only = models.Receipt.objects.create(
            reference="REC-ALREADY",
            warehouse=self.warehouse,
        )
        line_already_received = models.ReceiptLine.objects.create(
            receipt=receipt_with_received_only,
            product=self.product,
            quantity=1,
            location=self.location,
            received_lot=received_lot,
        )
        with mock.patch("wms.admin.receive_receipt_line") as receive_mock:
            with mock.patch.object(receipt_admin, "message_user"), mock.patch.object(
                receipt_line_admin, "message_user"
            ):
                receipt_admin.receive_lines(
                    request,
                    models.Receipt.objects.filter(pk=receipt_with_received_only.pk),
                )
                receipt_line_admin.receive_selected_lines(
                    request,
                    models.ReceiptLine.objects.filter(pk=line_already_received.pk),
                )
        receive_mock.assert_not_called()


class ProductLotAndOtherAdminTests(_AdminTestBase):
    def test_productlot_permissions_and_misc_admin_helpers(self):
        lot_admin = ProductLotAdmin(models.ProductLot, self.site)
        request_user = self._request(superuser=False)
        request_admin = self._request(superuser=True)

        lot = models.ProductLot.objects.create(
            product=self.product,
            lot_code="LOT-Q",
            status=models.ProductLotStatus.QUARANTINED,
            quantity_on_hand=10,
            quantity_reserved=3,
            location=self.location,
        )

        self.assertEqual(lot_admin.get_readonly_fields(request_user, lot), ("quantity_on_hand", "quantity_reserved"))
        self.assertEqual(lot_admin.get_readonly_fields(request_user, None), ())
        self.assertEqual(lot_admin.quantity_available(lot), 7)

        with mock.patch.object(lot_admin, "message_user") as message_user_mock:
            lot_admin.release_quarantine(request_user, models.ProductLot.objects.filter(pk=lot.pk))
        lot.refresh_from_db()
        self.assertEqual(lot.status, models.ProductLotStatus.QUARANTINED)
        self.assertTrue(any("Seuls les admins" in str(args) for args, _ in message_user_mock.call_args_list))

        with mock.patch.object(lot_admin, "message_user") as message_user_mock:
            lot_admin.release_quarantine(request_admin, models.ProductLot.objects.filter(pk=lot.pk))
        lot.refresh_from_db()
        self.assertEqual(lot.status, models.ProductLotStatus.AVAILABLE)
        self.assertEqual(lot.released_by_id, self.superuser.id)
        self.assertTrue(any("libere" in str(args) for args, _ in message_user_mock.call_args_list))

        inline = CartonItemInline(models.CartonItem, self.site)
        self.assertFalse(inline.has_add_permission(request_user))

        destination_admin = DestinationAdmin(models.Destination, self.site)
        db_field = models.Destination._meta.get_field("correspondent_contact")
        with mock.patch("wms.admin.contacts_with_tags", return_value=Contact.objects.filter(pk=self.contact.pk)) as contacts_mock:
            field = destination_admin.formfield_for_foreignkey(db_field, request_user)
        contacts_mock.assert_called_once()
        self.assertEqual(list(field.queryset), [self.contact])


class ShipmentAndStockMovementAdminTests(_AdminTestBase):
    def test_shipment_print_helpers_and_stockmovement_helpers(self):
        shipment_admin = ShipmentAdmin(models.Shipment, self.site)
        stock_admin = StockMovementAdmin(models.StockMovement, self.site)
        request = self._request(superuser=True)
        shipment = self._shipment(reference="260200")
        carton = models.Carton.objects.create(code="CART-ADM", shipment=shipment)

        self.assertEqual(shipment_admin.qr_code_preview(SimpleNamespace(qr_code_image=None)), "-")
        self.assertIn(
            "/media/qr.png",
            shipment_admin.qr_code_preview(SimpleNamespace(qr_code_image=SimpleNamespace(url="/media/qr.png"))),
        )

        with mock.patch.object(shipment_admin, "get_object", return_value=None):
            with self.assertRaises(Http404):
                shipment_admin.print_document(request, shipment.id, "shipment_note")

        with mock.patch.object(shipment_admin, "get_object", return_value=shipment):
            with self.assertRaises(Http404):
                shipment_admin.print_document(request, shipment.id, "unknown")

        with mock.patch.object(shipment_admin, "get_object", return_value=shipment), mock.patch(
            "wms.admin.build_shipment_document_context",
            return_value={"k": "v"},
        ), mock.patch(
            "wms.admin.get_template_layout",
            return_value={"blocks": []},
        ), mock.patch(
            "wms.admin.render_layout_from_layout",
            return_value=[{"block": 1}],
        ), mock.patch(
            "wms.admin.render",
            return_value="dynamic-response",
        ) as render_mock:
            response = shipment_admin.print_document(request, shipment.id, "shipment_note")
        self.assertEqual(response, "dynamic-response")
        render_mock.assert_called_once()

        with mock.patch.object(shipment_admin, "get_object", return_value=shipment), mock.patch(
            "wms.admin.build_shipment_document_context",
            return_value={"k": "v"},
        ), mock.patch(
            "wms.admin.get_template_layout",
            return_value=None,
        ), mock.patch(
            "wms.admin.render",
            return_value="template-response",
        ) as render_mock:
            response = shipment_admin.print_document(request, shipment.id, "shipment_note")
        self.assertEqual(response, "template-response")
        self.assertIn("print/bon_expedition.html", str(render_mock.call_args))

        with mock.patch.object(shipment_admin, "get_object", return_value=shipment):
            with self.assertRaises(Http404):
                shipment_admin.print_carton_packing_list(request, shipment.id, 999999)

        with mock.patch.object(shipment_admin, "get_object", return_value=None):
            with self.assertRaises(Http404):
                shipment_admin.print_carton_packing_list(request, shipment.id, carton.id)

        with mock.patch.object(shipment_admin, "get_object", return_value=shipment), mock.patch(
            "wms.admin.build_carton_document_context",
            return_value={"k": "v"},
        ), mock.patch(
            "wms.admin.get_template_layout",
            return_value={"blocks": []},
        ), mock.patch(
            "wms.admin.render_layout_from_layout",
            return_value=[{"block": 1}],
        ), mock.patch(
            "wms.admin.render",
            return_value="carton-dynamic",
        ):
            response = shipment_admin.print_carton_packing_list(request, shipment.id, carton.id)
        self.assertEqual(response, "carton-dynamic")

        with mock.patch.object(shipment_admin, "get_object", return_value=shipment), mock.patch(
            "wms.admin.build_carton_document_context",
            return_value={"k": "v"},
        ), mock.patch(
            "wms.admin.get_template_layout",
            return_value=None,
        ), mock.patch(
            "wms.admin.render",
            return_value="carton-template",
        ) as render_mock:
            response = shipment_admin.print_carton_packing_list(request, shipment.id, carton.id)
        self.assertEqual(response, "carton-template")
        self.assertIn("print/liste_colisage_carton.html", str(render_mock.call_args))

        readonly = stock_admin.get_readonly_fields(request)
        self.assertIn("movement_type", readonly)
        self.assertFalse(stock_admin.has_add_permission(request))
        self.assertFalse(stock_admin.has_delete_permission(request))

        with mock.patch("wms.admin.render", return_value="rendered-form") as render_mock:
            response = stock_admin._render_form(request, form=mock.Mock(), title="Titre")
        self.assertEqual(response, "rendered-form")
        self.assertIn("Titre", str(render_mock.call_args))


class OrderAndCartonAdminTests(_AdminTestBase):
    def _order(self, **overrides):
        data = {
            "shipper_name": "Shipper",
            "recipient_name": "Recipient",
            "correspondent_name": "Correspondent",
            "destination_address": "10 Rue Test",
            "destination_country": "France",
        }
        data.update(overrides)
        return models.Order.objects.create(**data)

    def test_order_admin_actions(self):
        admin_obj = OrderAdmin(models.Order, self.site)
        request = self._request(superuser=True)

        shipment = self._shipment(reference="260300")
        order_with_shipment = self._order(reference="ORD-WITH", shipment=shipment)
        order_without_shipment = self._order(reference="ORD-WO")

        self.assertEqual(admin_obj.shipment_reference(order_with_shipment), shipment.reference)
        self.assertEqual(admin_obj.shipment_reference(order_without_shipment), "-")

        with mock.patch("wms.admin.create_shipment_for_order") as create_shipment_mock, mock.patch.object(
            admin_obj, "message_user"
        ) as message_user_mock:
            admin_obj.create_shipment(
                request,
                models.Order.objects.filter(pk__in=[order_with_shipment.pk, order_without_shipment.pk]),
            )
        create_shipment_mock.assert_called_once_with(order=order_without_shipment)
        self.assertTrue(any("expedition(s) creee(s)" in str(args) for args, _ in message_user_mock.call_args_list))

        with mock.patch("wms.admin.reserve_stock_for_order", side_effect=[None, StockError("reserve-error")]), mock.patch.object(
            admin_obj, "message_user"
        ) as message_user_mock:
            admin_obj.reserve_order(
                request,
                models.Order.objects.filter(pk__in=[order_with_shipment.pk, order_without_shipment.pk]),
            )
        self.assertTrue(any("reservee(s)" in str(args) for args, _ in message_user_mock.call_args_list))
        self.assertTrue(any("reserve-error" in str(args) for args, _ in message_user_mock.call_args_list))

        with mock.patch("wms.admin.prepare_order", side_effect=[None, StockError("prepare-error")]), mock.patch.object(
            admin_obj, "message_user"
        ) as message_user_mock:
            admin_obj.prepare_order_action(
                request,
                models.Order.objects.filter(pk__in=[order_with_shipment.pk, order_without_shipment.pk]),
            )
        self.assertTrue(any("preparee(s)" in str(args) for args, _ in message_user_mock.call_args_list))
        self.assertTrue(any("prepare-error" in str(args) for args, _ in message_user_mock.call_args_list))

    def test_carton_admin_save_model_and_unpack_action(self):
        admin_obj = CartonAdmin(models.Carton, self.site)
        request = self._request(superuser=True)
        shipment_a = self._shipment(reference="260400")
        shipment_b = self._shipment(reference="260401")

        carton = models.Carton.objects.create(code="CART-UPD", shipment=shipment_a)
        lot = models.ProductLot.objects.create(
            product=self.product,
            lot_code="LOT-CART",
            quantity_on_hand=10,
            location=self.location,
        )
        models.StockMovement.objects.create(
            movement_type=models.MovementType.OUT,
            product=self.product,
            product_lot=lot,
            quantity=1,
            from_location=self.location,
            related_carton=carton,
            related_shipment=shipment_a,
            created_by=self.user,
        )

        carton.shipment = shipment_b
        admin_obj.save_model(request, carton, form=mock.Mock(), change=True)
        self.assertEqual(
            models.StockMovement.objects.get(related_carton=carton).related_shipment_id,
            shipment_b.id,
        )

        carton.shipment = None
        admin_obj.save_model(request, carton, form=mock.Mock(), change=True)
        self.assertEqual(
            models.StockMovement.objects.get(related_carton=carton).related_shipment_id,
            None,
        )

        carton_new = models.Carton.objects.create(code="CART-NEW", shipment=shipment_b)
        models.CartonItem.objects.create(carton=carton_new, product_lot=lot, quantity=2)
        self.assertFalse(
            models.StockMovement.objects.filter(
                related_carton=carton_new,
                movement_type=models.MovementType.OUT,
            ).exists()
        )
        admin_obj.save_model(request, carton_new, form=mock.Mock(), change=True)
        new_movement = models.StockMovement.objects.get(related_carton=carton_new)
        self.assertEqual(new_movement.related_shipment_id, shipment_b.id)
        self.assertEqual(new_movement.quantity, 2)
        self.assertEqual(new_movement.created_by_id, self.superuser.id)

        with mock.patch("wms.admin.unpack_carton", side_effect=[None, StockError("skip")]), mock.patch.object(
            admin_obj, "message_user"
        ) as message_user_mock:
            admin_obj.unpack_cartons(
                request,
                models.Carton.objects.filter(pk__in=[carton.pk, carton_new.pk]),
            )
        self.assertTrue(any("deconditionne(s)" in str(args) for args, _ in message_user_mock.call_args_list))
        self.assertTrue(any("ignores" in str(args) for args, _ in message_user_mock.call_args_list))


class StockMovementAdminViewsTests(_AdminTestBase):
    class _FakeForm:
        def __init__(self, *, valid=True, cleaned_data=None):
            self._valid = valid
            self.cleaned_data = cleaned_data or {}
            self.add_error = mock.Mock()

        def is_valid(self):
            return self._valid

    def test_receive_adjust_transfer_and_pack_views(self):
        admin_obj = StockMovementAdmin(models.StockMovement, self.site)
        post_request = self.factory.post("/admin/wms/stockmovement/receive/", data={})
        post_request.user = self.superuser
        get_request = self.factory.get("/admin/wms/stockmovement/receive/")
        get_request.user = self.superuser

        # receive_view: missing location -> add_error + render form
        product_without_default = models.Product.objects.create(
            sku="SKU-NO-LOC",
            name="No Loc",
            qr_code_image="qr_codes/no_loc.png",
            default_location=None,
        )
        form_missing_location = self._FakeForm(
            cleaned_data={
                "product": product_without_default,
                "status": "",
                "location": None,
                "quantity": 1,
                "lot_code": "",
                "received_on": None,
                "expires_on": None,
                "storage_conditions": "",
            }
        )
        with mock.patch("wms.admin.ReceiveStockForm", return_value=form_missing_location), mock.patch.object(
            admin_obj, "_render_form", return_value="receive-rendered"
        ) as render_form_mock:
            response = admin_obj.receive_view(post_request)
        self.assertEqual(response, "receive-rendered")
        form_missing_location.add_error.assert_called_once()
        render_form_mock.assert_called_once()

        # receive_view: success branch
        lot = models.ProductLot.objects.create(
            product=self.product,
            lot_code="LOT-RECV",
            quantity_on_hand=1,
            location=self.location,
        )
        form_receive_success = self._FakeForm(
            cleaned_data={
                "product": self.product,
                "status": "",
                "location": None,
                "quantity": 2,
                "lot_code": "LOT-NEW",
                "received_on": None,
                "expires_on": None,
                "storage_conditions": "dry",
            }
        )
        with mock.patch("wms.admin.ReceiveStockForm", return_value=form_receive_success), mock.patch(
            "wms.admin.receive_stock",
            return_value=lot,
        ) as receive_stock_mock, mock.patch(
            "wms.admin.redirect",
            return_value="receive-redirect",
        ) as redirect_mock, mock.patch.object(
            admin_obj, "message_user"
        ) as message_user_mock:
            response = admin_obj.receive_view(post_request)
        self.assertEqual(response, "receive-redirect")
        receive_stock_mock.assert_called_once()
        redirect_mock.assert_called_once()
        message_user_mock.assert_called_once()

        with mock.patch("wms.admin.ReceiveStockForm", return_value=self._FakeForm(valid=False)), mock.patch.object(
            admin_obj, "_render_form", return_value="receive-invalid"
        ):
            self.assertEqual(admin_obj.receive_view(post_request), "receive-invalid")
        with mock.patch("wms.admin.ReceiveStockForm", return_value=self._FakeForm(valid=False)), mock.patch.object(
            admin_obj, "_render_form", return_value="receive-get"
        ):
            self.assertEqual(admin_obj.receive_view(get_request), "receive-get")

        # adjust_view
        form_adjust_success = self._FakeForm(
            cleaned_data={
                "product_lot": lot,
                "quantity_delta": 1,
                "reason_code": "ADJ",
                "reason_notes": "note",
            }
        )
        with mock.patch("wms.admin.AdjustStockForm", return_value=form_adjust_success), mock.patch(
            "wms.admin.adjust_stock",
            return_value=None,
        ) as adjust_stock_mock, mock.patch(
            "wms.admin.redirect",
            return_value="adjust-redirect",
        ), mock.patch.object(
            admin_obj, "message_user"
        ):
            self.assertEqual(admin_obj.adjust_view(post_request), "adjust-redirect")
        adjust_stock_mock.assert_called_once()

        form_adjust_error = self._FakeForm(
            cleaned_data={
                "product_lot": lot,
                "quantity_delta": -99,
                "reason_code": "",
                "reason_notes": "",
            }
        )
        with mock.patch("wms.admin.AdjustStockForm", return_value=form_adjust_error), mock.patch(
            "wms.admin.adjust_stock",
            side_effect=StockError("insufficient"),
        ), mock.patch.object(admin_obj, "_render_form", return_value="adjust-render"):
            self.assertEqual(admin_obj.adjust_view(post_request), "adjust-render")
        form_adjust_error.add_error.assert_called_once()

        with mock.patch("wms.admin.AdjustStockForm", return_value=self._FakeForm(valid=False)), mock.patch.object(
            admin_obj, "_render_form", return_value="adjust-get"
        ):
            self.assertEqual(admin_obj.adjust_view(get_request), "adjust-get")

        # transfer_view
        form_transfer_success = self._FakeForm(
            cleaned_data={"product_lot": lot, "to_location": self.location}
        )
        with mock.patch("wms.admin.TransferStockForm", return_value=form_transfer_success), mock.patch(
            "wms.admin.transfer_stock",
            return_value=None,
        ) as transfer_stock_mock, mock.patch(
            "wms.admin.redirect",
            return_value="transfer-redirect",
        ), mock.patch.object(
            admin_obj, "message_user"
        ):
            self.assertEqual(admin_obj.transfer_view(post_request), "transfer-redirect")
        transfer_stock_mock.assert_called_once()

        form_transfer_error = self._FakeForm(
            cleaned_data={"product_lot": lot, "to_location": self.location}
        )
        with mock.patch("wms.admin.TransferStockForm", return_value=form_transfer_error), mock.patch(
            "wms.admin.transfer_stock",
            side_effect=StockError("same"),
        ), mock.patch.object(admin_obj, "_render_form", return_value="transfer-render"):
            self.assertEqual(admin_obj.transfer_view(post_request), "transfer-render")
        form_transfer_error.add_error.assert_called_once()

        with mock.patch("wms.admin.TransferStockForm", return_value=self._FakeForm(valid=False)), mock.patch.object(
            admin_obj, "_render_form", return_value="transfer-get"
        ):
            self.assertEqual(admin_obj.transfer_view(get_request), "transfer-get")

        # pack_view success
        shipment = self._shipment(reference="260500")
        carton = models.Carton.objects.create(code="CART-PACK")
        form_pack_success = self._FakeForm(
            cleaned_data={
                "product": self.product,
                "quantity": 2,
                "carton": carton,
                "carton_code": "CART-PACK",
                "shipment": shipment,
                "current_location": self.location,
            }
        )
        with mock.patch("wms.admin.PackCartonForm", return_value=form_pack_success), mock.patch(
            "wms.admin.pack_carton",
            return_value=carton,
        ) as pack_carton_mock, mock.patch(
            "wms.admin.redirect",
            return_value="pack-redirect",
        ), mock.patch.object(
            admin_obj, "message_user"
        ):
            self.assertEqual(admin_obj.pack_view(post_request), "pack-redirect")
        pack_carton_mock.assert_called_once()

        # pack_view mapped errors
        error_cases = [
            ("Carton deja lie", "shipment"),
            ("Stock insuffisant", "quantity"),
            ("carton expedie", "carton"),
            ("expedition expediee", "shipment"),
            ("autre erreur", None),
        ]
        for message, field in error_cases:
            form_pack_error = self._FakeForm(
                cleaned_data={
                    "product": self.product,
                    "quantity": 1,
                    "carton": carton,
                    "carton_code": "CART-PACK",
                    "shipment": shipment,
                    "current_location": self.location,
                }
            )
            with mock.patch("wms.admin.PackCartonForm", return_value=form_pack_error), mock.patch(
                "wms.admin.pack_carton",
                side_effect=StockError(message),
            ), mock.patch.object(admin_obj, "_render_form", return_value="pack-render"):
                self.assertEqual(admin_obj.pack_view(post_request), "pack-render")
            form_pack_error.add_error.assert_called_once_with(field, message)

        with mock.patch("wms.admin.PackCartonForm", return_value=self._FakeForm(valid=False)), mock.patch.object(
            admin_obj, "_render_form", return_value="pack-get"
        ):
            self.assertEqual(admin_obj.pack_view(get_request), "pack-get")
