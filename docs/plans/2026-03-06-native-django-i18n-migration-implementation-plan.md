# Native Django I18n Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrer tout le legacy Django vers une i18n native FR/EN et supprimer le middleware de traduction runtime sans perdre la couverture anglaise.

**Architecture:** Garder le legacy Django comme seule surface en scope, introduire un vrai catalogue `locale/`, convertir progressivement templates et messages Python vers `trans` / `gettext`, puis retirer le middleware runtime une fois que les tests EN passent sans lui. Le travail avance par vagues courtes: fondation, pages publiques, portail, scan, admin, emails/print, puis retrait final.

**Tech Stack:** Django 4.2, templates Django, ORM, formulaires Django, gettext (`makemessages` / `compilemessages`), tests `manage.py test`.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:systematic-debugging`, `@superpowers:verification-before-completion`, `@superpowers:requesting-code-review`, `@superpowers:using-git-worktrees`.

### Task 1: Poser la fondation i18n native et rendre le middleware coupable desactive

**Files:**
- Modify: `asf_wms/settings.py`
- Modify: `wms/middleware_runtime_translation.py`
- Modify: `wms/tests/views/tests_i18n_language_switch.py`
- Create: `locale/fr/LC_MESSAGES/django.po`
- Create: `locale/en/LC_MESSAGES/django.po`

**Step 1: Write the failing test**

Ajouter un test qui prouve que le middleware peut etre coupe, afin d'observer les pages encore non migrees.

```python
from django.test import override_settings

@override_settings(WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION=False)
def test_runtime_translation_can_be_disabled(self):
    self._activate_english()
    response = self.client.get(reverse("portal:portal_login"))
    self.assertContains(response, "Connexion association")
    self.assertNotContains(response, "Association login")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch.LanguageSwitchI18nTests.test_runtime_translation_can_be_disabled -v 2`
Expected: FAIL because the runtime middleware still forces English.

**Step 3: Write minimal implementation**

- Ajouter dans `asf_wms/settings.py` un flag:

```python
WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION = _env_bool(
    "WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION",
    True,
)
```

- Court-circuiter le middleware si le flag est faux:

```python
from django.conf import settings

if not settings.WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION:
    return response
```

- Generer les catalogues initiaux:

```bash
./.venv/bin/python manage.py makemessages -l fr -l en
```

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch.LanguageSwitchI18nTests.test_runtime_translation_can_be_disabled -v 2`
- `./.venv/bin/python manage.py compilemessages -v 1`

Expected: PASS for the test and successful compilation of the initial catalogs.

**Step 5: Commit**

```bash
git add asf_wms/settings.py wms/middleware_runtime_translation.py wms/tests/views/tests_i18n_language_switch.py locale/fr/LC_MESSAGES/django.po locale/en/LC_MESSAGES/django.po
git commit -m "feat(i18n): add native locale foundation and middleware flag"
```

### Task 2: Migrer la coquille partagee et les pages publiques d'authentification

**Files:**
- Modify: `templates/includes/language_switch.html`
- Modify: `templates/portal/login.html`
- Modify: `templates/portal/access_recovery.html`
- Modify: `templates/portal/set_password.html`
- Modify: `templates/scan/public_account_request.html`
- Modify: `templates/scan/public_order.html`
- Modify: `wms/tests/views/tests_i18n_language_switch.py`
- Modify: `locale/en/LC_MESSAGES/django.po`

**Step 1: Write the failing test**

Ajouter des assertions EN avec middleware coupe pour les pages publiques.

```python
@override_settings(WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION=False)
def test_public_auth_pages_render_native_english(self):
    self._activate_english()
    login_response = self.client.get(reverse("portal:portal_login"))
    self.assertContains(login_response, "Association login")
    self.assertContains(login_response, "Use your email and password.")
    self.assertNotContains(login_response, "Connexion association")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch.LanguageSwitchI18nTests.test_public_auth_pages_render_native_english -v 2`
Expected: FAIL because templates still contain French literals.

**Step 3: Write minimal implementation**

- Ajouter `{% trans %}` / `{% blocktrans %}` dans les templates publics:

```django
{% load static i18n %}
<title>{% trans "Connexion association" %}</title>
<h2 class="ui-comp-title">{% trans "Connexion association" %}</h2>
<p class="scan-help">{% trans "Utilisez votre email et votre mot de passe." %}</p>
```

- Pour les phrases longues:

```django
{% blocktrans %}
Pas de compte ? Envoyez une demande, elle sera validee par un administrateur ASF.
{% endblocktrans %}
```

- Mettre a jour le catalogue EN, puis recompiler:

```bash
./.venv/bin/python manage.py makemessages -l en
./.venv/bin/python manage.py compilemessages -v 1
```

**Step 4: Run tests to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch -v 2`
Expected: PASS with correct English on login, recovery, set-password, public account request and public order pages even when runtime translation is disabled.

**Step 5: Commit**

```bash
git add templates/includes/language_switch.html templates/portal/login.html templates/portal/access_recovery.html templates/portal/set_password.html templates/scan/public_account_request.html templates/scan/public_order.html wms/tests/views/tests_i18n_language_switch.py locale/en/LC_MESSAGES/django.po
git commit -m "feat(i18n): migrate public auth and shared entry pages"
```

### Task 3: Migrer le portail association en i18n native

**Files:**
- Modify: `templates/portal/base.html`
- Modify: `templates/portal/dashboard.html`
- Modify: `templates/portal/account.html`
- Modify: `templates/portal/recipients.html`
- Modify: `templates/portal/order_create.html`
- Modify: `templates/portal/order_detail.html`
- Modify: `wms/views_portal_auth.py`
- Modify: `wms/views_portal_orders.py`
- Modify: `wms/views_portal_account.py`
- Modify: `wms/portal_order_handlers.py`
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/views/tests_i18n_language_switch.py`
- Modify: `locale/en/LC_MESSAGES/django.po`

**Step 1: Write the failing test**

Ajouter un test portail EN natif pour dashboard + creation commande.

```python
@override_settings(WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION=False)
def test_portal_dashboard_and_order_create_render_native_english(self):
    self.client.force_login(self.portal_user)
    self._activate_english()
    dashboard = self.client.get(reverse("portal:portal_dashboard"))
    self.assertContains(dashboard, "Association portal")
    self.assertContains(dashboard, "New order")
    self.assertNotContains(dashboard, "Portail association")
```

**Step 2: Run test to verify it fails**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch.LanguageSwitchI18nTests.test_portal_dashboard_and_order_create_render_native_english -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal -v 2`

Expected: FAIL on English assertions while existing FR behavior remains.

**Step 3: Write minimal implementation**

- Migrer les templates portail vers `trans` / `blocktrans`.
- Migrer les messages Python de `views_portal_auth.py`, `views_portal_orders.py`, `views_portal_account.py`, `portal_order_handlers.py`.

```python
from django.utils.translation import gettext as _

messages.success(request, _("Commande creee: %(reference)s.") % {"reference": order.reference})
```

- Pour les titres ou labels de formulaires dynamiques, preferer `gettext_lazy`.

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py makemessages -l en`
- `./.venv/bin/python manage.py compilemessages -v 1`
- `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch wms.tests.views.tests_views_portal -v 2`

Expected: PASS with English portal UI, English feedback messages, and no regression in portal flows.

**Step 5: Commit**

```bash
git add templates/portal/base.html templates/portal/dashboard.html templates/portal/account.html templates/portal/recipients.html templates/portal/order_create.html templates/portal/order_detail.html wms/views_portal_auth.py wms/views_portal_orders.py wms/views_portal_account.py wms/portal_order_handlers.py wms/tests/views/tests_views_portal.py wms/tests/views/tests_i18n_language_switch.py locale/en/LC_MESSAGES/django.po
git commit -m "feat(i18n): migrate legacy portal pages and messages"
```

### Task 4: Migrer la reception et les formulaires scan les plus visibles

**Files:**
- Modify: `templates/scan/receive.html`
- Modify: `templates/scan/receive_pallet.html`
- Modify: `templates/scan/receive_association.html`
- Modify: `wms/views_scan_receipts.py`
- Modify: `wms/receipt_handlers.py`
- Modify: `wms/receipt_pallet_handlers.py`
- Modify: `wms/forms.py`
- Modify: `wms/tests/views/tests_views_scan_receipts.py`
- Modify: `wms/tests/forms/tests_forms.py`
- Modify: `wms/tests/views/tests_i18n_language_switch.py`
- Modify: `locale/en/LC_MESSAGES/django.po`

**Step 1: Write the failing test**

Verifier qu'une page reception passe en anglais natif sans middleware.

```python
@override_settings(WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION=False)
def test_receive_pages_render_native_english(self):
    self.client.force_login(self.staff_user)
    self._activate_english()
    response = self.client.get(reverse("scan:scan_receive_pallet"))
    self.assertContains(response, "Pallet receiving")
    self.assertContains(response, "Reception date")
    self.assertNotContains(response, "Reception palette")
```

**Step 2: Run test to verify it fails**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch.LanguageSwitchI18nTests.test_receive_pages_render_native_english -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_receipts -v 2`

Expected: FAIL because labels, help texts and handler messages are still French literals.

**Step 3: Write minimal implementation**

- Migrer labels/aides/erreurs de `wms/forms.py`.

```python
from django.utils.translation import gettext_lazy as _

quantity = forms.IntegerField(label=_("Quantite"), min_value=1)
```

- Migrer les messages de succes / erreur des handlers reception.

```python
messages.success(request, _("Reception palette enregistree (ref %(reference)s).") % {"reference": receipt.reference})
```

- Migrer les templates reception et recompiler le catalogue.

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py makemessages -l en`
- `./.venv/bin/python manage.py compilemessages -v 1`
- `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch wms.tests.views.tests_views_scan_receipts wms.tests.forms.tests_forms -v 2`

Expected: PASS with natural English for the reception flow, including form validation.

**Step 5: Commit**

```bash
git add templates/scan/receive.html templates/scan/receive_pallet.html templates/scan/receive_association.html wms/views_scan_receipts.py wms/receipt_handlers.py wms/receipt_pallet_handlers.py wms/forms.py wms/tests/views/tests_views_scan_receipts.py wms/tests/forms/tests_forms.py wms/tests/views/tests_i18n_language_switch.py locale/en/LC_MESSAGES/django.po
git commit -m "feat(i18n): migrate legacy receiving flows"
```

### Task 5: Migrer stock, commandes et preparation legacy scan

**Files:**
- Modify: `templates/scan/stock.html`
- Modify: `templates/scan/stock_update.html`
- Modify: `templates/scan/orders_view.html`
- Modify: `templates/scan/order.html`
- Modify: `templates/scan/pack.html`
- Modify: `templates/scan/cartons_ready.html`
- Modify: `templates/scan/prepare_kits.html`
- Modify: `wms/views_scan_stock.py`
- Modify: `wms/views_scan_orders.py`
- Modify: `wms/stock_update_handlers.py`
- Modify: `wms/order_scan_handlers.py`
- Modify: `wms/pack_handlers.py`
- Modify: `wms/tests/views/tests_views_scan_stock.py`
- Modify: `wms/tests/views/tests_views_scan_orders.py`
- Modify: `wms/tests/orders/tests_order_scan_handlers.py`
- Modify: `locale/en/LC_MESSAGES/django.po`

**Step 1: Write the failing test**

Ajouter un test EN natif sur les surfaces scan stock/commande.

```python
@override_settings(WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION=False)
def test_scan_stock_and_orders_render_native_english(self):
    self.client.force_login(self.staff_user)
    self._activate_english()
    stock_response = self.client.get(reverse("scan:scan_stock"))
    self.assertContains(stock_response, "Stock view")
    self.assertNotContains(stock_response, "Vue Stock")
```

**Step 2: Run test to verify it fails**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_stock wms.tests.views.tests_views_scan_orders wms.tests.orders.tests_order_scan_handlers -v 2`

Expected: FAIL on untranslated labels and messages.

**Step 3: Write minimal implementation**

- Migrer les templates et messages runtime.
- Remplacer les chaines en dur cote Python:

```python
messages.success(request, _("Stock mis a jour."))
form.add_error("shipment_reference", _("Expedition introuvable."))
```

- Recompiler le catalogue EN.

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py makemessages -l en`
- `./.venv/bin/python manage.py compilemessages -v 1`
- `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch wms.tests.views.tests_views_scan_stock wms.tests.views.tests_views_scan_orders wms.tests.orders.tests_order_scan_handlers -v 2`

Expected: PASS for stock, orders and preparation pages with no French leakage on key screens.

**Step 5: Commit**

```bash
git add templates/scan/stock.html templates/scan/stock_update.html templates/scan/orders_view.html templates/scan/order.html templates/scan/pack.html templates/scan/cartons_ready.html templates/scan/prepare_kits.html wms/views_scan_stock.py wms/views_scan_orders.py wms/stock_update_handlers.py wms/order_scan_handlers.py wms/pack_handlers.py wms/tests/views/tests_views_scan_stock.py wms/tests/views/tests_views_scan_orders.py wms/tests/orders/tests_order_scan_handlers.py locale/en/LC_MESSAGES/django.po
git commit -m "feat(i18n): migrate legacy stock and order scan flows"
```

### Task 6: Migrer expeditions, dashboard, FAQ et settings scan

**Files:**
- Modify: `templates/scan/base.html`
- Modify: `templates/scan/dashboard.html`
- Modify: `templates/scan/shipment_create.html`
- Modify: `templates/scan/shipments_ready.html`
- Modify: `templates/scan/shipments_tracking.html`
- Modify: `templates/scan/shipment_tracking.html`
- Modify: `templates/scan/faq.html`
- Modify: `templates/scan/settings.html`
- Modify: `wms/views_scan_dashboard.py`
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/views_scan_misc.py`
- Modify: `wms/views_scan_settings.py`
- Modify: `wms/scan_shipment_handlers.py`
- Modify: `wms/shipment_tracking_handlers.py`
- Modify: `wms/shipment_helpers.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/views/tests_views_scan_misc.py`
- Modify: `wms/tests/views/tests_i18n_language_switch.py`
- Modify: `locale/en/LC_MESSAGES/django.po`

**Step 1: Write the failing test**

Ajouter une couverture EN native sur dashboard + tracking + FAQ.

```python
@override_settings(WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION=False)
def test_scan_dashboard_faq_and_tracking_render_native_english(self):
    self.client.force_login(self.staff_user)
    self._activate_english()
    faq_response = self.client.get(reverse("scan:scan_faq"))
    self.assertContains(faq_response, "Access & roles")
    self.assertNotContains(faq_response, "Acces & roles")
```

**Step 2: Run test to verify it fails**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments wms.tests.views.tests_views_scan_misc -v 2`

Expected: FAIL because the scan shell and shipment flows still depend on FR literals plus runtime replacement.

**Step 3: Write minimal implementation**

- Migrer la navigation scan, dashboard cards, FAQ sections et libelles shipment.
- Internationaliser les messages des handlers shipment:

```python
messages.success(request, _("Expedition creee: %(reference)s.") % {"reference": shipment.reference})
raise StockError(_("Impossible de retirer un carton expedie."))
```

- Recompiler le catalogue EN.

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py makemessages -l en`
- `./.venv/bin/python manage.py compilemessages -v 1`
- `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch wms.tests.views.tests_views_scan_shipments wms.tests.views.tests_views_scan_misc -v 2`

Expected: PASS with English dashboard, FAQ, shipment creation/edit/tracking, and no dependency on runtime translation for those screens.

**Step 5: Commit**

```bash
git add templates/scan/base.html templates/scan/dashboard.html templates/scan/shipment_create.html templates/scan/shipments_ready.html templates/scan/shipments_tracking.html templates/scan/shipment_tracking.html templates/scan/faq.html templates/scan/settings.html wms/views_scan_dashboard.py wms/views_scan_shipments.py wms/views_scan_misc.py wms/views_scan_settings.py wms/scan_shipment_handlers.py wms/shipment_tracking_handlers.py wms/shipment_helpers.py wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_views_scan_misc.py wms/tests/views/tests_i18n_language_switch.py locale/en/LC_MESSAGES/django.po
git commit -m "feat(i18n): migrate legacy shipment and scan shell pages"
```

### Task 7: Migrer l'admin custom et les messages back-office

**Files:**
- Modify: `templates/admin/base_site.html`
- Modify: `templates/admin/wms/organization_roles_review.html`
- Modify: `templates/admin/wms/stockmovement/change_list.html`
- Modify: `templates/admin/wms/stockmovement/form.html`
- Modify: `wms/admin.py`
- Modify: `wms/admin_misc.py`
- Modify: `wms/admin_stockmovement_views.py`
- Modify: `wms/admin_account_request_approval.py`
- Modify: `wms/tests/admin/tests_admin_extra.py`
- Modify: `wms/tests/admin/tests_admin_bootstrap_ui.py`
- Modify: `locale/en/LC_MESSAGES/django.po`

**Step 1: Write the failing test**

Ajouter un test admin EN natif sur les vues custom.

```python
@override_settings(WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION=False)
def test_admin_custom_pages_render_native_english(self):
    self.client.force_login(self.superuser)
    response = self.client.get(reverse("admin:index"))
    self.assertContains(response, "Django admin")
    self.assertNotContains(response, "Admin Django")
```

**Step 2: Run test to verify it fails**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch -v 2`
- `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_extra wms.tests.admin.tests_admin_bootstrap_ui -v 2`

Expected: FAIL on admin labels, action descriptions and message_user strings.

**Step 3: Write minimal implementation**

- Migrer templates admin custom vers `trans`.
- Migrer `short_description`, `message_user`, titres de vues et feedbacks admin:

```python
from django.utils.translation import gettext_lazy as _

mark_approved.short_description = _("Marquer comme approuve")
```

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py makemessages -l en`
- `./.venv/bin/python manage.py compilemessages -v 1`
- `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch wms.tests.admin.tests_admin_extra wms.tests.admin.tests_admin_bootstrap_ui -v 2`

Expected: PASS with native English for admin entry points and stock movement views.

**Step 5: Commit**

```bash
git add templates/admin/base_site.html templates/admin/wms/organization_roles_review.html templates/admin/wms/stockmovement/change_list.html templates/admin/wms/stockmovement/form.html wms/admin.py wms/admin_misc.py wms/admin_stockmovement_views.py wms/admin_account_request_approval.py wms/tests/admin/tests_admin_extra.py wms/tests/admin/tests_admin_bootstrap_ui.py locale/en/LC_MESSAGES/django.po
git commit -m "feat(i18n): migrate legacy admin surfaces"
```

### Task 8: Migrer emails et documents d'impression

**Files:**
- Modify: `templates/emails/account_request_admin_notification.txt`
- Modify: `templates/emails/account_request_approved.txt`
- Modify: `templates/emails/account_request_approved_user.txt`
- Modify: `templates/emails/account_request_received.txt`
- Modify: `templates/emails/order_admin_notification_portal.txt`
- Modify: `templates/emails/order_admin_notification_public.txt`
- Modify: `templates/emails/order_confirmation.txt`
- Modify: `templates/emails/order_status_association_notification.txt`
- Modify: `templates/emails/portal_forgot_password.txt`
- Modify: `templates/emails/shipment_delivery_notification.txt`
- Modify: `templates/emails/shipment_status_admin_notification.txt`
- Modify: `templates/emails/shipment_status_correspondant_notification.txt`
- Modify: `templates/emails/shipment_status_party_notification.txt`
- Modify: `templates/emails/shipment_tracking_admin_notification.txt`
- Modify: `templates/print/attestation_aide_humanitaire.html`
- Modify: `templates/print/attestation_donation.html`
- Modify: `templates/print/attestation_douane.html`
- Modify: `templates/print/bon_expedition.html`
- Modify: `templates/print/dynamic_document.html`
- Modify: `templates/print/dynamic_labels.html`
- Modify: `templates/print/etiquette_expedition.html`
- Modify: `templates/print/liste_colisage_carton.html`
- Modify: `templates/print/liste_colisage_lot.html`
- Modify: `templates/print/order_summary.html`
- Modify: `templates/print/picking_list_carton.html`
- Modify: `templates/print/picking_list_kits.html`
- Modify: `templates/print/product_labels.html`
- Modify: `templates/print/product_qr_labels.html`
- Modify: `wms/emailing.py`
- Modify: `wms/order_notifications.py`
- Modify: `wms/views_print_docs.py`
- Modify: `wms/views_print_labels.py`
- Modify: `wms/tests/emailing/tests_emailing.py`
- Modify: `wms/tests/views/tests_views_print_docs.py`
- Modify: `wms/tests/views/tests_views_print_labels.py`
- Modify: `locale/en/LC_MESSAGES/django.po`

**Step 1: Write the failing test**

Ajouter une couverture EN native pour un email et un document imprime.

```python
def test_portal_forgot_password_email_uses_native_english(self):
    with translation.override("en"):
        body = render_to_string("emails/portal_forgot_password.txt", context)
    self.assertIn("Association login", body)
    self.assertNotIn("Connexion association", body)
```

**Step 2: Run test to verify it fails**

Run:
- `./.venv/bin/python manage.py test wms.tests.emailing.tests_emailing -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs wms.tests.views.tests_views_print_labels -v 2`

Expected: FAIL on untranslated email and print templates.

**Step 3: Write minimal implementation**

- Migrer les templates email et print avec `trans` / `blocktrans`.
- Migrer sujets/messages Python:

```python
subject = _("ASF WMS - Demande de compte recue")
```

- Recompiler le catalogue EN.

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py makemessages -l en`
- `./.venv/bin/python manage.py compilemessages -v 1`
- `./.venv/bin/python manage.py test wms.tests.emailing.tests_emailing wms.tests.views.tests_views_print_docs wms.tests.views.tests_views_print_labels -v 2`

Expected: PASS with English emails and printable documents sourced from Django i18n.

**Step 5: Commit**

```bash
git add templates/emails templates/print wms/emailing.py wms/order_notifications.py wms/views_print_docs.py wms/views_print_labels.py wms/tests/emailing/tests_emailing.py wms/tests/views/tests_views_print_docs.py wms/tests/views/tests_views_print_labels.py locale/en/LC_MESSAGES/django.po
git commit -m "feat(i18n): migrate legacy emails and print templates"
```

### Task 9: Ajouter un audit automatise des chaines visibles encore non internationalisees

**Files:**
- Create: `wms/management/commands/audit_i18n_strings.py`
- Create: `wms/tests/management/tests_management_audit_i18n_strings.py`
- Modify: `docs/plans/2026-03-06-native-django-i18n-migration-design.md`

**Step 1: Write the failing test**

Ajouter un test de commande management qui detecte une chaine francaise non encapsulee.

```python
def test_audit_i18n_strings_reports_unwrapped_french_literals(self):
    out = StringIO()
    with self.assertRaises(CommandError):
        call_command("audit_i18n_strings", path="templates/portal/login.html", stdout=out)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.management.tests_management_audit_i18n_strings -v 2`
Expected: FAIL because the command does not exist yet.

**Step 3: Write minimal implementation**

- Creer une commande qui scanne les chemins legacy et signale les lignes contenant des caracteres accentues ou des litteraux FR sans wrapper i18n.

```python
if "{% trans" not in line and "{% blocktrans" not in line and _looks_like_french(line):
    findings.append((path, lineno, line.strip()))
```

- Retourner `CommandError` si des findings existent.

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.management.tests_management_audit_i18n_strings -v 2`
- `./.venv/bin/python manage.py audit_i18n_strings`

Expected: PASS for the command test and actionable output for any remaining untranslated literal.

**Step 5: Commit**

```bash
git add wms/management/commands/audit_i18n_strings.py wms/tests/management/tests_management_audit_i18n_strings.py docs/plans/2026-03-06-native-django-i18n-migration-design.md
git commit -m "feat(i18n): add untranslated string audit command"
```

### Task 10: Basculer les tests EN sans middleware puis supprimer le runtime translation legacy

**Files:**
- Modify: `asf_wms/settings.py`
- Delete: `wms/middleware_runtime_translation.py`
- Modify: `wms/tests/views/tests_i18n_language_switch.py`
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/views/tests_views_scan_receipts.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/admin/tests_admin_extra.py`
- Modify: `wms/tests/emailing/tests_emailing.py`

**Step 1: Write the failing test**

Ajouter un smoke test qui exige que les pages critiques EN passent avec le middleware runtime retire.

```python
@override_settings(WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION=False)
def test_critical_english_pages_no_longer_depend_on_runtime_translation(self):
    self.client.force_login(self.staff_user)
    self._activate_english()
    response = self.client.get(reverse("scan:scan_dashboard"))
    self.assertContains(response, "Dashboard")
    self.assertNotContains(response, "Tableau de bord")
```

**Step 2: Run test to verify it fails**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch -v 2`
- `./.venv/bin/python manage.py audit_i18n_strings`

Expected: FAIL if any remaining page still relies on runtime translation or contains untranslated literals.

**Step 3: Write minimal implementation**

- Retirer le middleware de `MIDDLEWARE` dans `asf_wms/settings.py`.
- Supprimer le fichier runtime translation.
- Nettoyer les tests qui affirmaient le comportement runtime et les remplacer par des assertions sur l'i18n native.

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    ...
]
```

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py compilemessages -v 1`
- `./.venv/bin/python manage.py audit_i18n_strings`
- `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch wms.tests.views.tests_views_portal wms.tests.views.tests_views_scan_receipts wms.tests.views.tests_views_scan_shipments wms.tests.admin.tests_admin_extra wms.tests.emailing.tests_emailing -v 2`

Expected: PASS with no runtime middleware, clean audit output, and stable English on all critical legacy surfaces.

**Step 5: Commit**

```bash
git add asf_wms/settings.py wms/tests/views/tests_i18n_language_switch.py wms/tests/views/tests_views_portal.py wms/tests/views/tests_views_scan_receipts.py wms/tests/views/tests_views_scan_shipments.py wms/tests/admin/tests_admin_extra.py wms/tests/emailing/tests_emailing.py
git rm wms/middleware_runtime_translation.py
git commit -m "feat(i18n): remove runtime translation middleware"
```
