from django import forms
from django.core.validators import MinValueValidator

from .models import WmsRuntimeSettings


class ScanRuntimeSettingsForm(forms.ModelForm):
    RUNTIME_FIELDS = (
        "low_stock_threshold",
        "tracking_alert_hours",
        "workflow_blockage_hours",
        "stale_drafts_age_days",
        "email_queue_max_attempts",
        "email_queue_retry_base_seconds",
        "email_queue_retry_max_seconds",
        "email_queue_processing_timeout_seconds",
        "enable_shipment_track_legacy",
    )
    MIN_ONE_FIELDS = (
        "low_stock_threshold",
        "tracking_alert_hours",
        "workflow_blockage_hours",
        "stale_drafts_age_days",
        "email_queue_max_attempts",
        "email_queue_retry_base_seconds",
        "email_queue_retry_max_seconds",
        "email_queue_processing_timeout_seconds",
    )
    change_note = forms.CharField(
        required=False,
        max_length=255,
        label="Commentaire operateur",
        help_text="Obligatoire si vous modifiez au moins un parametre.",
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    class Meta:
        model = WmsRuntimeSettings
        fields = [
            "low_stock_threshold",
            "tracking_alert_hours",
            "workflow_blockage_hours",
            "stale_drafts_age_days",
            "email_queue_max_attempts",
            "email_queue_retry_base_seconds",
            "email_queue_retry_max_seconds",
            "email_queue_processing_timeout_seconds",
            "enable_shipment_track_legacy",
        ]
        labels = {
            "low_stock_threshold": "Seuil stock bas",
            "tracking_alert_hours": "Alerte suivi (heures)",
            "workflow_blockage_hours": "Blocage workflow (heures)",
            "stale_drafts_age_days": "Ancienneté brouillons (jours)",
            "email_queue_max_attempts": "Queue email: tentatives max",
            "email_queue_retry_base_seconds": "Queue email: retry base (secondes)",
            "email_queue_retry_max_seconds": "Queue email: retry max (secondes)",
            "email_queue_processing_timeout_seconds": "Queue email: timeout processing (secondes)",
            "enable_shipment_track_legacy": "Activer la route legacy suivi expédition",
        }
        help_texts = {
            "low_stock_threshold": "Produit considéré en stock bas sous ce seuil.",
            "tracking_alert_hours": "Déclenche les cartes d'alerte de suivi.",
            "workflow_blockage_hours": "Ancienneté utilisée pour détecter les blocages.",
            "stale_drafts_age_days": "Un brouillon temporaire plus ancien est archivable.",
            "email_queue_max_attempts": "Nombre maximal de retries avant échec définitif.",
            "email_queue_retry_base_seconds": "Délai de base du backoff exponentiel.",
            "email_queue_retry_max_seconds": "Délai maximal du backoff exponentiel.",
            "email_queue_processing_timeout_seconds": "Au-delà, un événement processing est considéré bloqué.",
            "enable_shipment_track_legacy": "Permet la route /scan/shipment/track/<reference>/.",
        }
        widgets = {
            "low_stock_threshold": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "tracking_alert_hours": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "workflow_blockage_hours": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "stale_drafts_age_days": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "email_queue_max_attempts": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "email_queue_retry_base_seconds": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "email_queue_retry_max_seconds": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "email_queue_processing_timeout_seconds": forms.NumberInput(
                attrs={"min": 1, "step": 1}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.MIN_ONE_FIELDS:
            field = self.fields[field_name]
            field.min_value = 1
            field.widget.attrs["min"] = 1
            field.error_messages["min_value"] = (
                "La valeur doit être supérieure ou égale à 1."
            )
            field.validators = [
                validator
                for validator in field.validators
                if not isinstance(validator, MinValueValidator)
            ]
            field.validators.append(MinValueValidator(1))

    def clean(self):
        cleaned_data = super().clean()
        retry_base = cleaned_data.get("email_queue_retry_base_seconds")
        retry_max = cleaned_data.get("email_queue_retry_max_seconds")
        if (
            retry_base is not None
            and retry_max is not None
            and retry_max < retry_base
        ):
            self.add_error(
                "email_queue_retry_max_seconds",
                "Le retry max doit être supérieur ou égal au retry base.",
            )
        if getattr(self.instance, "pk", None):
            action = (self.data.get("action") or "").strip().lower()
            requires_change_note = action in {"", "save"}
            changed_runtime_fields = [
                field_name
                for field_name in self.RUNTIME_FIELDS
                if cleaned_data.get(field_name) != getattr(self.instance, field_name, None)
            ]
            if (
                requires_change_note
                and changed_runtime_fields
                and not (cleaned_data.get("change_note") or "").strip()
            ):
                self.add_error(
                    "change_note",
                    "Ajoutez un commentaire operateur pour tracer ce changement.",
                )
        return cleaned_data
