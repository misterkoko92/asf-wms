from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe


class WmsUiTemplateTagTests(SimpleTestCase):
    def test_ui_alert_renders_shared_contract_with_tone_copy_and_attrs(self):
        template = Template(
            "{% load wms_ui %}"
            "{% ui_alert tone='warning' title=title body=body extra_classes='mb-3' attrs=attrs %}"
        )

        rendered = template.render(
            Context(
                {
                    "title": "Attention <unsafe>",
                    "body": "Produits sans dimensions <unsafe>",
                    "attrs": {
                        "aria-live": "polite",
                        "data-alert-scope": "pack",
                    },
                }
            )
        )

        self.assertIn('class="scan-message warning ui-comp-alert mb-3"', rendered)
        self.assertIn('role="alert"', rendered)
        self.assertIn('aria-live="polite"', rendered)
        self.assertIn('data-alert-scope="pack"', rendered)
        self.assertIn(
            '<strong class="ui-comp-alert-title">Attention &lt;unsafe&gt;</strong>',
            rendered,
        )
        self.assertIn(
            '<div class="ui-comp-alert-body">Produits sans dimensions &lt;unsafe&gt;</div>',
            rendered,
        )

    def test_ui_button_renders_secure_link_variant_classes_and_attrs(self):
        template = Template(
            "{% load wms_ui %}"
            "{% ui_button label=label href='/back/' variant='tertiary' size='sm' target='_blank' attrs=attrs %}"
        )

        rendered = template.render(
            Context(
                {
                    "label": "Annuler <unsafe>",
                    "attrs": {
                        "aria-controls": "history-panel",
                        "aria-expanded": "false",
                    },
                }
            )
        )

        self.assertIn('class="btn btn-tertiary btn-sm"', rendered)
        self.assertIn('href="/back/"', rendered)
        self.assertIn('target="_blank"', rendered)
        self.assertIn('rel="noopener noreferrer"', rendered)
        self.assertIn('aria-controls="history-panel"', rendered)
        self.assertIn('aria-expanded="false"', rendered)
        self.assertIn("Annuler &lt;unsafe&gt;", rendered)

    def test_ui_button_preserves_disabled_and_aria_attrs_on_button(self):
        template = Template(
            "{% load wms_ui %}"
            "{% ui_button label='Enregistrer' button_type='submit' attrs=attrs %}"
        )

        rendered = template.render(
            Context(
                {
                    "attrs": {
                        "disabled": True,
                        "aria-label": "Enregistrer le brouillon",
                    }
                }
            )
        )

        self.assertIn('type="submit"', rendered)
        self.assertIn('class="btn btn-primary"', rendered)
        self.assertIn("disabled", rendered)
        self.assertIn('aria-label="Enregistrer le brouillon"', rendered)

    def test_ui_switch_renders_existing_switch_contract_and_escapes_copy(self):
        template = Template(
            "{% load wms_ui %}"
            "{% ui_switch name='notify' id='id_notify' label=label checked=True help_text=help_text wide=True extra_classes='mt-2' %}"
        )

        rendered = template.render(
            Context(
                {
                    "label": "Avertir <unsafe>",
                    "help_text": "Contacte le correspondant <unsafe>",
                }
            )
        )

        self.assertIn(
            'class="form-check form-switch scan-inline-switch scan-inline-switch-wide mt-2"',
            rendered,
        )
        self.assertIn('name="notify"', rendered)
        self.assertIn('id="id_notify"', rendered)
        self.assertIn('value="1"', rendered)
        self.assertIn("checked", rendered)
        self.assertIn("Avertir &lt;unsafe&gt;", rendered)
        self.assertIn("Contacte le correspondant &lt;unsafe&gt;", rendered)

    def test_ui_field_wraps_existing_form_markup_help_text_and_errors(self):
        template = Template(
            "{% load wms_ui %}"
            "{% ui_field field_id='id_structure_name' label=label field_html=field_html help_text=help_text errors=errors %}"
        )

        rendered = template.render(
            Context(
                {
                    "label": "Nom de la structure",
                    "field_html": mark_safe(
                        '<input class="form-control" id="id_structure_name" name="structure_name" type="text">'
                    ),
                    "help_text": "Nom visible par les équipes <unsafe>",
                    "errors": ["Champ requis", "Valeur <unsafe>"],
                }
            )
        )

        self.assertIn('class="scan-field"', rendered)
        self.assertIn(
            '<label class="form-label" for="id_structure_name">Nom de la structure</label>',
            rendered,
        )
        self.assertIn('name="structure_name"', rendered)
        self.assertIn("Nom visible par les équipes &lt;unsafe&gt;", rendered)
        self.assertIn('<div class="text-danger small">Champ requis</div>', rendered)
        self.assertIn('<div class="text-danger small">Valeur &lt;unsafe&gt;</div>', rendered)

    def test_ui_status_badge_uses_shared_tone_resolution(self):
        template = Template(
            "{% load wms_ui %}"
            "{% ui_status_badge label='Expedie' status_value='shipped' domain='shipment' %}"
        )

        rendered = template.render(Context())

        self.assertIn('class="ui-comp-status-pill is-info"', rendered)
        self.assertIn(">Expedie<", rendered)
