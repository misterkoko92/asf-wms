import re
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from wms.models import (
    Location,
    MovementType,
    Order,
    OrderReviewStatus,
    OrderStatus,
    Product,
    ProductCategory,
    ProductLot,
    ProductLotStatus,
    StockMovement,
    VolunteerProfile,
    Warehouse,
)
from wms.preparateur_home_queries import (
    ORDER_GROUP_ALL,
    ORDER_GROUP_CRITICAL,
    _build_order_option,
    _order_is_realisable_now,
    _remaining_total,
    _shipper_display_name,
    build_preparateur_order_groups,
)
from wms.preparateur_orders import PREPARATEUR_SELECTED_ORDER_SESSION_KEY
from wms.preparateur_session import (
    LEGACY_PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY,
    PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY,
    build_preparateur_volunteer_label,
    clear_active_preparateur_volunteer,
    get_active_preparateur_volunteer,
    get_preparateur_greeting_name,
    list_active_preparateur_volunteers,
)
from wms.scan_permissions import is_scan_view_allowed_for_user

TEST_PASSWORD = "pass1234"  # pragma: allowlist secret


class ScanPreparateurHomeViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.preparateur = get_user_model().objects.create_user(
            username="scan-preparateur-home",
            password=TEST_PASSWORD,
            is_staff=True,
        )
        Group.objects.get_or_create(name="Preparateur")[0].user_set.add(cls.preparateur)
        cls.alpha_alice = cls._create_volunteer(
            username="volunteer-alpha-alice",
            first_name="Alice",
            last_name="Alpha",
        )
        cls.alpha_zoe = cls._create_volunteer(
            username="volunteer-alpha-zoe",
            first_name="Zoe",
            last_name="Alpha",
        )
        cls.bravo_bob = cls._create_volunteer(
            username="volunteer-bravo-bob",
            first_name="Bob",
            last_name="Bravo",
        )
        cls._create_volunteer(
            username="volunteer-inactive",
            first_name="Inactive",
            last_name="Zulu",
            is_active=False,
        )

    @classmethod
    def _create_volunteer(cls, *, username, first_name, last_name, is_active=True):
        user = get_user_model().objects.create_user(
            username=username,
            password=TEST_PASSWORD,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        return VolunteerProfile.objects.create(user=user, is_active=is_active)

    def setUp(self):
        self.client.force_login(self.preparateur)

    def _set_active_volunteer(self, volunteer):
        session = self.client.session
        session[PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY] = volunteer.id
        session.save()

    def test_scan_preparateur_home_lists_active_volunteers_sorted_and_disables_actions_without_selection(
        self,
    ):
        response = self.client.get(reverse("scan:scan_preparateur_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choisir un bénévole")
        self.assertFalse(response.context["has_active_volunteer"])
        self.assertIsNone(response.context["active_volunteer"])
        self.assertEqual(
            [row["id"] for row in response.context["volunteer_options"]],
            [self.alpha_alice.id, self.alpha_zoe.id, self.bravo_bob.id],
        )
        content = response.content.decode()
        self.assertRegex(
            content,
            re.compile(r'id="scan-preparateur-home-prepare-order"[^>]*disabled'),
        )
        self.assertRegex(
            content,
            re.compile(r'id="scan-preparateur-home-prepare-cartons"[^>]*disabled'),
        )
        self.assertNotContains(response, "Inactive ZULU")

    def test_scan_preparateur_home_post_stores_active_volunteer_in_session(self):
        response = self.client.post(
            reverse("scan:scan_preparateur_home"),
            {"volunteer_id": str(self.bravo_bob.id)},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_preparateur_home"))
        session = self.client.session
        self.assertEqual(session[PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY], self.bravo_bob.id)

    def test_scan_preparateur_home_renders_stock_update_shortcut(self):
        response = self.client.get(reverse("scan:scan_preparateur_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MAJ Stock")
        self.assertContains(response, 'id="scan-preparateur-home-stock-update"')
        self.assertContains(response, f'href="{reverse("scan:scan_stock_update")}"')

    def test_scan_preparateur_can_open_stock_update_page(self):
        response = self.client.get(reverse("scan:scan_stock_update"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "scan/stock_update.html")

    def test_scan_preparateur_home_renders_rangement_action(self):
        response = self.client.get(reverse("scan:scan_preparateur_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rangement")
        self.assertContains(response, 'id="scan-preparateur-home-rangement"')

    def test_scan_preparateur_home_rangement_requires_active_volunteer(self):
        response = self.client.post(
            reverse("scan:scan_preparateur_home"),
            {"action": "rangement"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_preparateur_home"))

    def test_scan_preparateur_home_rangement_redirects_with_active_volunteer(self):
        self._set_active_volunteer(self.alpha_alice)

        response = self.client.post(
            reverse("scan:scan_preparateur_home"),
            {"action": "rangement"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_preparateur_rangement"))

    def test_scan_preparateur_can_open_rangement_page(self):
        response = self.client.get(reverse("scan:scan_preparateur_rangement"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "scan/preparateur_rangement.html")
        self.assertContains(response, "Rangement")
        self.assertContains(response, 'data-scan-target="id_rangement_product_code"')

    def test_scan_preparateur_rangement_scan_requires_mode_and_quantity(self):
        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {
                "action": "scan_product",
                "product_code": "ANY",
                "quantity": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choisissez un mode de rangement.")
        self.assertContains(response, "Quantité obligatoire.")

    def test_scan_preparateur_rangement_receipt_mode_adds_draft_then_validates_stock(self):
        warehouse = Warehouse.objects.create(name="Rangement warehouse", code="RANG")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        product = Product.objects.create(
            sku="RANG-001",
            name="Produit rangement",
            barcode="BAR-RANG-001",
            default_location=location,
        )

        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {
                "action": "scan_product",
                "movement_mode": "receipt",
                "product_code": "BAR-RANG-001",
                "quantity": "3",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Produit Rangement")
        self.assertContains(response, "Rangement warehouse A-01-001")
        self.assertContains(response, "En attente de validation")
        self.assertEqual(ProductLot.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertEqual(response.context["rangement_mode"], "receipt")

        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {"action": "validate_batch"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_preparateur_rangement"))
        lot = ProductLot.objects.get(product=product)
        self.assertEqual(lot.quantity_on_hand, 3)
        self.assertEqual(lot.location, location)
        movement = StockMovement.objects.get(product=product)
        self.assertEqual(movement.movement_type, MovementType.IN)
        self.assertEqual(movement.quantity, 3)
        self.assertEqual(movement.to_location, location)
        self.assertNotIn("preparateur_rangement_batch", self.client.session)

    def test_scan_preparateur_rangement_duplicate_scan_merges_draft_quantity(self):
        warehouse = Warehouse.objects.create(name="Rangement duplicate", code="RANGD")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="B",
            aisle="02",
            shelf="002",
        )
        product = Product.objects.create(
            sku="RANG-002",
            name="Produit doublon",
            barcode="BAR-RANG-002",
            default_location=location,
        )

        url = reverse("scan:scan_preparateur_rangement")
        self.client.post(
            url,
            {
                "action": "scan_product",
                "movement_mode": "receipt",
                "product_code": product.sku,
                "quantity": "2",
            },
        )
        response = self.client.post(
            url,
            {
                "action": "scan_product",
                "movement_mode": "receipt",
                "product_code": product.barcode,
                "quantity": "4",
            },
        )

        self.assertEqual(response.status_code, 200)
        batch = response.context["rangement_batch"]
        self.assertEqual(len(batch), 1)
        self.assertEqual(batch[0]["quantity"], 6)
        self.assertEqual(ProductLot.objects.filter(product=product).count(), 0)

    def test_scan_preparateur_rangement_rejects_mode_change_with_open_batch(self):
        warehouse = Warehouse.objects.create(name="Rangement locked mode", code="RANGLM")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="LM",
            aisle="01",
            shelf="001",
        )
        receipt_product = Product.objects.create(
            sku="RANG-LOCKED-RECEIPT",
            name="Produit mode entree",
            barcode="BAR-RANG-LOCKED-RECEIPT",
            default_location=location,
        )
        transfer_product = Product.objects.create(
            sku="RANG-LOCKED-TRANSFER",
            name="Produit mode transfert",
            barcode="BAR-RANG-LOCKED-TRANSFER",
            default_location=location,
        )
        url = reverse("scan:scan_preparateur_rangement")
        self.client.post(
            url,
            {
                "action": "scan_product",
                "movement_mode": "receipt",
                "product_code": receipt_product.barcode,
                "quantity": "1",
            },
        )

        response = self.client.post(
            url,
            {
                "action": "scan_product",
                "movement_mode": "transfer",
                "product_code": transfer_product.barcode,
                "quantity": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Terminez le batch avant de changer de mode.")
        self.assertEqual(response.context["rangement_mode"], "receipt")
        batch = response.context["rangement_batch"]
        self.assertEqual(len(batch), 1)
        self.assertEqual(batch[0]["product_id"], receipt_product.id)

    def test_scan_preparateur_rangement_missing_location_blocks_then_can_be_fixed(self):
        warehouse = Warehouse.objects.create(name="Rangement fix", code="RANGF")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="C",
            aisle="03",
            shelf="003",
        )
        product = Product.objects.create(
            sku="RANG-NOLOC",
            name="Produit sans emplacement",
            barcode="BAR-RANG-NOLOC",
        )

        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {
                "action": "scan_product",
                "movement_mode": "receipt",
                "product_code": "BAR-RANG-NOLOC",
                "quantity": "2",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Produit Sans Emplacement")
        self.assertContains(response, "Emplacement par défaut manquant")
        self.assertContains(response, "Définir l'emplacement")
        self.assertEqual(ProductLot.objects.count(), 0)

        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {
                "action": "validate_batch",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Définissez les emplacements manquants avant validation.")
        self.assertEqual(ProductLot.objects.count(), 0)

        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {
                "action": "set_default_location",
                "product_id": str(product.id),
                "location_id": str(location.id),
            },
        )

        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.default_location, location)
        self.assertContains(response, "Rangement fix C-03-003")
        self.assertNotContains(response, "Emplacement par défaut manquant")

    def test_scan_preparateur_rangement_set_default_location_rejects_unknown_ids(self):
        warehouse = Warehouse.objects.create(name="Rangement bad location", code="RANGBL")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="BL",
            aisle="01",
            shelf="001",
        )
        product = Product.objects.create(
            sku="RANG-BAD-LOCATION",
            name="Produit mauvais emplacement",
            barcode="BAR-RANG-BAD-LOCATION",
        )
        url = reverse("scan:scan_preparateur_rangement")

        response = self.client.post(
            url,
            {
                "action": "set_default_location",
                "product_id": str(product.id + 999),
                "location_id": str(location.id),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Produit introuvable.")

        response = self.client.post(
            url,
            {
                "action": "set_default_location",
                "product_id": str(product.id),
                "location_id": str(location.id + 999),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Emplacement introuvable.")

    def test_scan_preparateur_rangement_limits_batch_to_five_distinct_products(self):
        warehouse = Warehouse.objects.create(name="Rangement limit", code="RANGL")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="D",
            aisle="04",
            shelf="004",
        )
        url = reverse("scan:scan_preparateur_rangement")
        for index in range(5):
            Product.objects.create(
                sku=f"RANG-LIM-{index}",
                name=f"Produit limite {index}",
                barcode=f"BAR-RANG-LIM-{index}",
                default_location=location,
            )
            self.client.post(
                url,
                {
                    "action": "scan_product",
                    "movement_mode": "receipt",
                    "product_code": f"BAR-RANG-LIM-{index}",
                    "quantity": "1",
                },
            )
        overflow = Product.objects.create(
            sku="RANG-LIM-OVER",
            name="Produit limite overflow",
            barcode="BAR-RANG-LIM-OVER",
            default_location=location,
        )

        response = self.client.post(
            url,
            {
                "action": "scan_product",
                "movement_mode": "receipt",
                "product_code": overflow.barcode,
                "quantity": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Batch limité à 5 produits.")
        self.assertEqual(len(response.context["rangement_batch"]), 5)
        self.assertFalse(ProductLot.objects.filter(product=overflow).exists())

    def test_scan_preparateur_rangement_transfer_mode_moves_partial_quantity(self):
        warehouse = Warehouse.objects.create(name="Rangement transfer", code="RANGT")
        source_location = Location.objects.create(
            warehouse=warehouse,
            zone="TABLE",
            aisle="01",
            shelf="001",
        )
        target_location = Location.objects.create(
            warehouse=warehouse,
            zone="E",
            aisle="05",
            shelf="005",
        )
        product = Product.objects.create(
            sku="RANG-TRANSFER",
            name="Produit transfert",
            barcode="BAR-RANG-TRANSFER",
            default_location=target_location,
        )
        source_lot = ProductLot.objects.create(
            product=product,
            quantity_on_hand=20,
            quantity_reserved=0,
            location=source_location,
            received_on=date.today() - timedelta(days=3),
            expires_on=date.today() + timedelta(days=30),
        )

        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {
                "action": "scan_product",
                "movement_mode": "transfer",
                "product_code": product.barcode,
                "quantity": "3",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rangement transfer E-05-005")
        self.assertContains(response, "Rangement transfer TABLE-01-001")
        self.assertEqual(source_lot.quantity_on_hand, 20)
        self.assertEqual(StockMovement.objects.count(), 0)

        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {"action": "validate_batch"},
        )

        self.assertEqual(response.status_code, 302)
        source_lot.refresh_from_db()
        self.assertEqual(source_lot.quantity_on_hand, 17)
        target_lot = ProductLot.objects.get(product=product, location=target_location)
        self.assertEqual(target_lot.quantity_on_hand, 3)
        movement = StockMovement.objects.get(product=product)
        self.assertEqual(movement.movement_type, MovementType.TRANSFER)
        self.assertEqual(movement.quantity, 3)
        self.assertEqual(movement.from_location, source_location)
        self.assertEqual(movement.to_location, target_location)

    def test_scan_preparateur_rangement_transfer_mode_moves_whole_unreserved_lot(self):
        warehouse = Warehouse.objects.create(name="Rangement transfer whole", code="RANGTW")
        source_location = Location.objects.create(
            warehouse=warehouse,
            zone="TABLE",
            aisle="02",
            shelf="001",
        )
        target_location = Location.objects.create(
            warehouse=warehouse,
            zone="TW",
            aisle="02",
            shelf="002",
        )
        product = Product.objects.create(
            sku="RANG-TRANSFER-WHOLE",
            name="Produit transfert lot entier",
            barcode="BAR-RANG-TRANSFER-WHOLE",
            default_location=target_location,
        )
        source_lot = ProductLot.objects.create(
            product=product,
            lot_code="WHOLE",
            quantity_on_hand=3,
            quantity_reserved=0,
            location=source_location,
            received_on=date.today() - timedelta(days=2),
            expires_on=date.today() + timedelta(days=20),
        )

        self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {
                "action": "scan_product",
                "movement_mode": "transfer",
                "product_code": product.barcode,
                "quantity": "3",
            },
        )
        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {"action": "validate_batch"},
        )

        self.assertEqual(response.status_code, 302)
        source_lot.refresh_from_db()
        self.assertEqual(source_lot.quantity_on_hand, 3)
        self.assertEqual(source_lot.location, target_location)
        self.assertEqual(ProductLot.objects.filter(product=product).count(), 1)
        movement = StockMovement.objects.get(product=product)
        self.assertEqual(movement.movement_type, MovementType.TRANSFER)
        self.assertEqual(movement.product_lot, source_lot)

    def test_scan_preparateur_rangement_transfer_mode_blocks_insufficient_stock(self):
        warehouse = Warehouse.objects.create(name="Rangement transfer short", code="RANGTS")
        source_location = Location.objects.create(
            warehouse=warehouse,
            zone="TABLE",
            aisle="03",
            shelf="001",
        )
        target_location = Location.objects.create(
            warehouse=warehouse,
            zone="TS",
            aisle="03",
            shelf="002",
        )
        product = Product.objects.create(
            sku="RANG-TRANSFER-SHORT",
            name="Produit transfert insuffisant",
            barcode="BAR-RANG-TRANSFER-SHORT",
            default_location=target_location,
        )
        ProductLot.objects.create(
            product=product,
            lot_code="SHORT",
            quantity_on_hand=1,
            quantity_reserved=1,
            location=source_location,
            received_on=date.today() - timedelta(days=1),
            expires_on=date.today() + timedelta(days=10),
        )

        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {
                "action": "scan_product",
                "movement_mode": "transfer",
                "product_code": product.barcode,
                "quantity": "2",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stock disponible insuffisant")
        self.assertFalse(response.context["rangement_batch"][0]["is_valid"])

        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {"action": "validate_batch"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Corrigez les lignes bloquées avant validation.")
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_scan_preparateur_rangement_validate_empty_batch_errors(self):
        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {"action": "validate_batch"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aucun produit à valider.")

    def test_scan_preparateur_rangement_unknown_product_opens_modal_with_recap(self):
        warehouse = Warehouse.objects.create(name="Rangement unknown", code="RANGU")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="F",
            aisle="06",
            shelf="006",
        )
        known = Product.objects.create(
            sku="RANG-KNOWN",
            name="Produit déjà scanné",
            barcode="BAR-RANG-KNOWN",
            default_location=location,
        )
        url = reverse("scan:scan_preparateur_rangement")
        self.client.post(
            url,
            {
                "action": "scan_product",
                "movement_mode": "receipt",
                "product_code": known.barcode,
                "quantity": "2",
            },
        )

        response = self.client.post(
            url,
            {
                "action": "scan_product",
                "movement_mode": "receipt",
                "product_code": "UNKNOWN-RANG",
                "quantity": "4",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["unknown_product_modal_open"])
        self.assertContains(response, "Produit Déjà Scanné")
        self.assertContains(response, "UNKNOWN-RANG")
        self.assertContains(response, 'id="pack-unknown-product-modal"')
        self.assertContains(response, 'value="finish_batch"')
        self.assertContains(response, 'value="create_unknown_product"')
        self.assertEqual(ProductLot.objects.filter(product__name="UNKNOWN-RANG").count(), 0)

    def test_scan_preparateur_rangement_unknown_product_modal_script_runs_after_bootstrap(self):
        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {
                "action": "scan_product",
                "movement_mode": "receipt",
                "product_code": "UNKNOWN-RANG-SCRIPT",
                "quantity": "4",
            },
        )

        content = response.content.decode()
        self.assertContains(response, 'data-open-on-load="1"')
        self.assertLess(
            content.index("bootstrap.bundle.min.js"),
            content.index("window.bootstrap.Modal.getOrCreateInstance(modal).show();"),
        )

    def test_scan_preparateur_rangement_transfer_unknown_product_stays_in_flow(self):
        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {
                "action": "scan_product",
                "movement_mode": "transfer",
                "product_code": "UNKNOWN-RANG-TRANSFER",
                "quantity": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Impossible de déplacer un produit inconnu. Utilisez Entrée en stock.",
        )
        self.assertFalse(response.context["unknown_product_modal_open"])
        self.assertContains(response, 'data-open-on-load="0"')

    def test_scan_preparateur_rangement_create_unknown_product_rejects_transfer_mode(self):
        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {
                "action": "create_unknown_product",
                "movement_mode": "transfer",
                "unknown_product_source_code": "BAR-RANG-TRANSFER-CREATE",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["unknown_product_modal_open"])
        self.assertContains(
            response,
            "Créer un produit inconnu est réservé au mode Entrée en stock.",
        )
        self.assertFalse(Product.objects.filter(barcode="BAR-RANG-TRANSFER-CREATE").exists())

    def test_scan_preparateur_rangement_create_unknown_product_adds_draft_then_validation_stock(
        self,
    ):
        warehouse = Warehouse.objects.create(name="Rangement create", code="RANGC")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="G",
            aisle="07",
            shelf="007",
        )
        ProductCategory.objects.create(name="MM")
        session = self.client.session
        session["preparateur_rangement_mode"] = "receipt"
        session.save()

        with mock.patch("wms.pack_handlers.notify_preparateur_product_review_needed"):
            response = self.client.post(
                reverse("scan:scan_preparateur_rangement"),
                {
                    "action": "create_unknown_product",
                    "unknown_product_line_index": "0",
                    "unknown_product_source_code": "BAR-RANG-NEW",
                    "unknown_product_name": "Produit rangement nouveau",
                    "unknown_product_barcode": "BAR-RANG-NEW",
                    "unknown_product_pack_family": "MM",
                    "unknown_product_initial_quantity": "5",
                    "unknown_product_brand": "Marque Rangement",
                    "unknown_product_length_cm": "10.5",
                    "unknown_product_width_cm": "4",
                    "unknown_product_height_cm": "2",
                    "unknown_product_weight_g": "250",
                    "unknown_product_location": str(location.id),
                    "unknown_product_location_warehouse": warehouse.name,
                    "unknown_product_location_zone": location.zone,
                    "unknown_product_location_aisle": location.aisle,
                    "unknown_product_location_shelf": location.shelf,
                },
            )

        self.assertEqual(response.status_code, 200)
        product = Product.objects.get(barcode="BAR-RANG-NEW")
        self.assertTrue(product.is_incomplete)
        self.assertEqual(product.default_location, location)
        self.assertEqual(product.brand, "MARQUE RANGEMENT")
        self.assertEqual(product.length_cm, Decimal("10.50"))
        self.assertFalse(ProductLot.objects.filter(product=product).exists())
        self.assertContains(response, product.sku)
        self.assertContains(response, "Rangement create G-07-007")

        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {"action": "validate_batch"},
        )

        self.assertEqual(response.status_code, 302)
        lot = ProductLot.objects.get(product=product)
        self.assertEqual(lot.quantity_on_hand, 5)
        self.assertEqual(lot.location, location)

    def test_scan_preparateur_rangement_create_unknown_product_respects_batch_limit(self):
        warehouse = Warehouse.objects.create(name="Rangement full unknown", code="RANGFU")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="H",
            aisle="08",
            shelf="008",
        )
        ProductCategory.objects.create(name="MM")
        session = self.client.session
        session["preparateur_rangement_mode"] = "receipt"
        session["preparateur_rangement_batch"] = [
            {
                "product_id": index + 1,
                "mode": "receipt",
                "name": f"Produit plein {index}",
                "sku": f"FULL-{index}",
                "quantity": 1,
                "location_label": "Rangement full unknown F-06-006",
                "stock_updated": True,
                "stock_status_label": "Stock ajouté",
            }
            for index in range(5)
        ]
        session.save()

        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {
                "action": "create_unknown_product",
                "unknown_product_line_index": "0",
                "unknown_product_source_code": "BAR-RANG-FULL-NEW",
                "unknown_product_name": "Produit rangement plein",
                "unknown_product_barcode": "BAR-RANG-FULL-NEW",
                "unknown_product_pack_family": "MM",
                "unknown_product_initial_quantity": "5",
                "unknown_product_brand": "Marque Rangement",
                "unknown_product_length_cm": "10.5",
                "unknown_product_width_cm": "4",
                "unknown_product_height_cm": "2",
                "unknown_product_weight_g": "250",
                "unknown_product_location": str(location.id),
                "unknown_product_location_warehouse": warehouse.name,
                "unknown_product_location_zone": location.zone,
                "unknown_product_location_aisle": location.aisle,
                "unknown_product_location_shelf": location.shelf,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["unknown_product_modal_open"])
        self.assertContains(response, "Batch limité à 5 produits.")
        self.assertFalse(Product.objects.filter(barcode="BAR-RANG-FULL-NEW").exists())
        self.assertFalse(ProductLot.objects.exists())
        self.assertEqual(len(response.context["rangement_batch"]), 5)

    def test_scan_preparateur_rangement_finish_clears_batch_and_stays_on_rangement(self):
        session = self.client.session
        session["preparateur_rangement_mode"] = "receipt"
        session["preparateur_rangement_batch"] = [
            {
                "product_id": 123,
                "mode": "receipt",
                "name": "Produit terminé",
                "sku": "DONE",
                "quantity": 1,
                "location_label": "A-01-001",
                "stock_updated": True,
            }
        ]
        session.save()

        response = self.client.post(
            reverse("scan:scan_preparateur_rangement"),
            {"action": "finish_batch"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_preparateur_rangement"))
        self.assertNotIn("preparateur_rangement_batch", self.client.session)
        self.assertNotIn("preparateur_rangement_mode", self.client.session)

    def test_scan_preparateur_home_prepare_order_redirects_to_order_select_with_active_volunteer(
        self,
    ):
        self._set_active_volunteer(self.alpha_alice)

        response = self.client.post(
            reverse("scan:scan_preparateur_home"),
            {"action": "prepare_order"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_preparateur_order_select"))
        session = self.client.session
        self.assertEqual(session[PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY], self.alpha_alice.id)

    def test_scan_preparateur_home_prepare_cartons_clears_selected_order_and_redirects_pack(self):
        self._set_active_volunteer(self.bravo_bob)
        session = self.client.session
        session[PREPARATEUR_SELECTED_ORDER_SESSION_KEY] = 999
        session["preparateur_order_plan"] = {"order_id": 999, "cartons": []}
        session.save()

        response = self.client.post(
            reverse("scan:scan_preparateur_home"),
            {"action": "prepare_cartons"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_pack"))
        session = self.client.session
        self.assertEqual(session[PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY], self.bravo_bob.id)
        self.assertNotIn(PREPARATEUR_SELECTED_ORDER_SESSION_KEY, session)
        self.assertNotIn("preparateur_order_plan", session)

    def test_scan_preparateur_pack_start_clears_selected_order_and_plan_before_pack(self):
        self._set_active_volunteer(self.alpha_alice)
        session = self.client.session
        session[PREPARATEUR_SELECTED_ORDER_SESSION_KEY] = 123
        session["preparateur_order_plan"] = {"order_id": 123, "cartons": [{"index": 1}]}
        session.save()

        response = self.client.get(reverse("scan:scan_preparateur_pack_start"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_pack"))
        session = self.client.session
        self.assertEqual(session[PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY], self.alpha_alice.id)
        self.assertNotIn(PREPARATEUR_SELECTED_ORDER_SESSION_KEY, session)
        self.assertNotIn("preparateur_order_plan", session)

    def test_scan_preparateur_home_redirects_non_preparateur_to_dashboard(self):
        regular_staff = get_user_model().objects.create_user(
            username="scan-preparateur-regular-staff",
            password=TEST_PASSWORD,
            is_staff=True,
        )
        self.client.force_login(regular_staff)
        response = self.client.get(reverse("scan:scan_preparateur_home"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_dashboard"))

    def test_scan_preparateur_home_post_without_selection_clears_active_volunteer(self):
        self._set_active_volunteer(self.alpha_alice)

        response = self.client.post(reverse("scan:scan_preparateur_home"), {})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_preparateur_home"))
        session = self.client.session
        self.assertNotIn(PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY, session)

    def test_scan_preparateur_home_actions_require_active_volunteer(self):
        response_order = self.client.post(
            reverse("scan:scan_preparateur_home"),
            {"action": "prepare_order"},
        )
        response_cartons = self.client.post(
            reverse("scan:scan_preparateur_home"),
            {"action": "prepare_cartons"},
        )

        self.assertEqual(response_order.status_code, 302)
        self.assertEqual(response_order["Location"], reverse("scan:scan_preparateur_home"))
        self.assertEqual(response_cartons.status_code, 302)
        self.assertEqual(response_cartons["Location"], reverse("scan:scan_preparateur_home"))

    def test_scan_preparateur_pack_start_redirects_non_preparateur_to_pack(self):
        response = self.client.get(reverse("scan:scan_preparateur_pack_start"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_pack"))

    def test_scan_logout_redirects_to_site_root(self):
        response = self.client.get(reverse("scan:scan_logout"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")

    def test_scan_change_account_logs_out_and_redirects_to_scan_login(self):
        response = self.client.get(reverse("scan:scan_change_account"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            f"{reverse('admin:login')}?{urlencode({'next': reverse('scan:scan_root')})}",
        )
        self.assertNotIn("_auth_user_id", self.client.session)


class ScanPreparateurSessionHelperTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.alpha = cls._create_volunteer(
            username="volunteer-helper-alpha",
            first_name="Alice",
            last_name="Alpha",
        )
        cls.beta = cls._create_volunteer(
            username="volunteer-helper-beta",
            first_name="Bob",
            last_name="Beta",
        )
        cls.first_only = cls._create_volunteer(
            username="volunteer-helper-first",
            first_name="Claire",
            last_name="",
        )
        cls.last_only = cls._create_volunteer(
            username="volunteer-helper-last",
            first_name="",
            last_name="Durand",
        )
        cls.username_only = cls._create_volunteer(
            username="volunteer-helper-username",
            first_name="",
            last_name="",
        )

    @classmethod
    def _create_volunteer(cls, *, username, first_name, last_name):
        user = get_user_model().objects.create_user(
            username=username,
            password=TEST_PASSWORD,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        return VolunteerProfile.objects.create(user=user, is_active=True)

    def test_session_helpers_cover_cleanup_fallbacks_and_sorting(self):
        request = SimpleNamespace(
            session={
                PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY: self.alpha.id + 999,
                LEGACY_PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY: self.beta.id,
            }
        )

        active_volunteer = get_active_preparateur_volunteer(request)

        self.assertIsNone(active_volunteer)
        self.assertNotIn(PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY, request.session)
        self.assertNotIn(LEGACY_PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY, request.session)

        request = SimpleNamespace(
            session={
                LEGACY_PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY: self.beta.id,
            }
        )
        self.assertEqual(get_active_preparateur_volunteer(request), self.beta)

        request = SimpleNamespace(
            session={
                PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY: self.alpha.id,
                LEGACY_PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY: self.beta.id,
            }
        )
        clear_active_preparateur_volunteer(request)
        self.assertEqual(request.session, {})

        self.assertEqual(
            [volunteer.id for volunteer in list_active_preparateur_volunteers()],
            [
                self.username_only.id,
                self.first_only.id,
                self.alpha.id,
                self.beta.id,
                self.last_only.id,
            ],
        )

    def test_preparateur_label_and_greeting_helpers_cover_all_fallbacks(self):
        no_user_volunteer = SimpleNamespace(user=None)

        self.assertEqual(build_preparateur_volunteer_label(no_user_volunteer), "")
        self.assertEqual(build_preparateur_volunteer_label(self.alpha), "Alice ALPHA")
        self.assertEqual(build_preparateur_volunteer_label(self.first_only), "Claire")
        self.assertEqual(build_preparateur_volunteer_label(self.last_only), "DURAND")
        self.assertEqual(
            build_preparateur_volunteer_label(self.username_only),
            self.username_only.user.username,
        )

        self.assertEqual(get_preparateur_greeting_name(no_user_volunteer), "")
        self.assertEqual(get_preparateur_greeting_name(self.alpha), "Alice")
        self.assertEqual(get_preparateur_greeting_name(self.last_only), "DURAND")
        self.assertEqual(
            get_preparateur_greeting_name(self.username_only),
            self.username_only.user.username,
        )

    def test_scan_permission_helper_requires_resolver_match_for_preparateur(self):
        preparateur = get_user_model().objects.create_user(
            username="scan-preparateur-permissions",
            password=TEST_PASSWORD,
            is_staff=True,
        )
        Group.objects.get_or_create(name="Preparateur")[0].user_set.add(preparateur)
        request = SimpleNamespace(user=preparateur)

        self.assertFalse(is_scan_view_allowed_for_user(request))

        request.resolver_match = SimpleNamespace(url_name="scan_cartons_ready")
        self.assertTrue(is_scan_view_allowed_for_user(request))

        request.resolver_match = SimpleNamespace(url_name="scan_carton_document")
        self.assertTrue(is_scan_view_allowed_for_user(request))

        request.resolver_match = SimpleNamespace(url_name="scan_stock_update")
        self.assertTrue(is_scan_view_allowed_for_user(request))

        request.resolver_match = SimpleNamespace(url_name="scan_dashboard")
        self.assertFalse(is_scan_view_allowed_for_user(request))


class PreparateurHomeQueriesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.staff_user = get_user_model().objects.create_user(
            username="scan-preparateur-queries",
            password=TEST_PASSWORD,
            is_staff=True,
        )
        cls.warehouse = Warehouse.objects.create(name="Preparateur WH", code="PWH")
        cls.location = Location.objects.create(
            warehouse=cls.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )

    def _create_stocked_product(self, *, sku, name, quantity_on_hand, quantity_reserved=0):
        product = Product.objects.create(
            sku=sku,
            name=name,
            weight_g=100,
            volume_cm3=100,
            default_location=self.location,
        )
        ProductLot.objects.create(
            product=product,
            lot_code=f"LOT-{sku}",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            location=self.location,
        )
        return product

    def _create_order(
        self,
        *,
        shipper_name,
        product,
        quantity,
        reserved_quantity=0,
        prepared_quantity=0,
        requested_delivery_date=None,
        created_at=None,
        review_status=OrderReviewStatus.APPROVED,
        status=OrderStatus.DRAFT,
    ):
        order = Order.objects.create(
            shipper_name=shipper_name,
            recipient_name="Association Test",
            destination_address="1 rue du test",
            destination_city="Paris",
            destination_country="France",
            review_status=review_status,
            status=status,
            requested_delivery_date=requested_delivery_date,
            created_by=self.staff_user,
        )
        order.lines.create(
            product=product,
            quantity=quantity,
            reserved_quantity=reserved_quantity,
            prepared_quantity=prepared_quantity,
        )
        if created_at is not None:
            Order.objects.filter(pk=order.pk).update(created_at=created_at)
            order.refresh_from_db()
        return order

    def test_preparateur_home_query_helpers_cover_display_option_and_remaining_quantity(self):
        order = SimpleNamespace(
            shipper_contact=None,
            shipper_name="Shipper Name",
            reference="REF-001",
            id=10,
            requested_delivery_date=date(2026, 5, 1),
            lines=SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(remaining_quantity=3),
                    SimpleNamespace(remaining_quantity=-2),
                ]
            ),
            created_at=date(2026, 4, 20),
        )
        reference_only_order = SimpleNamespace(
            shipper_contact=None,
            shipper_name="",
            reference="REF-ONLY",
            id=11,
        )
        unnamed_order = SimpleNamespace(
            shipper_contact=None,
            shipper_name="",
            reference="",
            id=12,
        )

        self.assertEqual(_shipper_display_name(order), "Shipper Name")
        self.assertEqual(_shipper_display_name(reference_only_order), "REF-ONLY")
        self.assertEqual(_shipper_display_name(unnamed_order), "Commande 12")
        self.assertEqual(_remaining_total(order), 3)
        self.assertEqual(
            _build_order_option(order)["label"],
            "Shipper Name · REF-001 · reste 3 · livraison 01/05/2026",
        )

    def test_preparateur_home_query_helpers_cover_realisable_rules_and_grouping(self):
        full_product = self._create_stocked_product(
            sku="PREP-HQ-FULL",
            name="Produit Full",
            quantity_on_hand=8,
        )
        partial_product = self._create_stocked_product(
            sku="PREP-HQ-PARTIAL",
            name="Produit Partiel",
            quantity_on_hand=1,
        )
        reserved_product = self._create_stocked_product(
            sku="PREP-HQ-RESERVED",
            name="Produit Reserve",
            quantity_on_hand=0,
        )
        now = date(2026, 4, 20)

        critical = self._create_order(
            shipper_name="Zulu Hope",
            product=full_product,
            quantity=3,
            requested_delivery_date=now + timedelta(days=1),
        )
        alpha = self._create_order(
            shipper_name="Alpha Med",
            product=full_product,
            quantity=1,
            requested_delivery_date=now + timedelta(days=4),
        )
        self._create_order(
            shipper_name="Blocked",
            product=partial_product,
            quantity=5,
            requested_delivery_date=now + timedelta(days=2),
        )
        reserved = self._create_order(
            shipper_name="Reserved Flow",
            product=reserved_product,
            quantity=2,
            reserved_quantity=2,
            requested_delivery_date=now + timedelta(days=3),
            status=OrderStatus.RESERVED,
        )
        completed = self._create_order(
            shipper_name="Complete",
            product=full_product,
            quantity=2,
            prepared_quantity=2,
            requested_delivery_date=now + timedelta(days=5),
        )

        self.assertTrue(
            _order_is_realisable_now(
                critical,
                available_stock_by_product_id={full_product.id: 8},
            )
        )
        self.assertTrue(
            _order_is_realisable_now(
                reserved,
                available_stock_by_product_id={reserved_product.id: 0},
            )
        )
        self.assertFalse(
            _order_is_realisable_now(
                completed,
                available_stock_by_product_id={full_product.id: 8},
            )
        )
        self.assertFalse(
            _order_is_realisable_now(
                self._create_order(
                    shipper_name="Insufficient",
                    product=partial_product,
                    quantity=4,
                    requested_delivery_date=now + timedelta(days=6),
                ),
                available_stock_by_product_id={partial_product.id: 1},
            )
        )

        order_groups, selected_order_id = build_preparateur_order_groups()

        self.assertEqual(selected_order_id, critical.id)
        self.assertEqual(
            [group["label"] for group in order_groups],
            [ORDER_GROUP_CRITICAL, ORDER_GROUP_ALL],
        )
        self.assertEqual(
            [option["order"].id for option in order_groups[0]["options"]],
            [critical.id, reserved.id, alpha.id],
        )
        self.assertEqual(
            [option["order"].id for option in order_groups[1]["options"]],
            [alpha.id, reserved.id, critical.id],
        )
