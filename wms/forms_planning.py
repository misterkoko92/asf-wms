from django import forms
from django.utils.translation import gettext_lazy as _

from .models import (
    CommunicationChannel,
    CommunicationDraft,
    CommunicationDraftStatus,
    PlanningAssignment,
    PlanningRun,
    PlanningVersionStatus,
)
from .view_utils import sorted_choices


def _append_widget_class(field, css_class):
    existing_class = field.widget.attrs.get("class", "").strip()
    classes = [item for item in existing_class.split() if item]
    if css_class not in classes:
        classes.append(css_class)
    field.widget.attrs["class"] = " ".join(classes)


def _sort_field_choices(field):
    if hasattr(field, "choices"):
        field.choices = sorted_choices(field.choices)


class PlanningRunForm(forms.ModelForm):
    class Meta:
        model = PlanningRun
        fields = [
            "week_start",
            "week_end",
            "parameter_set",
            "flight_mode",
            "flight_batch",
        ]
        labels = {
            "week_start": _("Debut de semaine"),
            "week_end": _("Fin de semaine"),
            "parameter_set": _("Jeu de parametres"),
            "flight_mode": _("Mode vols"),
            "flight_batch": _("Batch vols existant"),
        }
        widgets = {
            "week_start": forms.DateInput(attrs={"type": "date"}),
            "week_end": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _sort_field_choices(self.fields["parameter_set"])
        _sort_field_choices(self.fields["flight_mode"])
        _sort_field_choices(self.fields["flight_batch"])
        _append_widget_class(self.fields["parameter_set"], "form-select")
        _append_widget_class(self.fields["parameter_set"], "ui-select--lg")
        _append_widget_class(self.fields["flight_mode"], "form-select")
        _append_widget_class(self.fields["flight_mode"], "ui-select--md")
        _append_widget_class(self.fields["flight_batch"], "form-select")
        _append_widget_class(self.fields["flight_batch"], "ui-select--lg")

    def clean(self):
        cleaned_data = super().clean()
        week_start = cleaned_data.get("week_start")
        week_end = cleaned_data.get("week_end")
        if week_start and week_end and week_end < week_start:
            self.add_error("week_end", _("La fin de semaine doit etre apres le debut."))
        return cleaned_data


class PlanningAssignmentForm(forms.ModelForm):
    class Meta:
        model = PlanningAssignment
        fields = [
            "volunteer_snapshot",
            "flight_snapshot",
            "assigned_carton_count",
            "status",
            "notes",
        ]
        labels = {
            "volunteer_snapshot": _("Benevole"),
            "flight_snapshot": _("Vol"),
            "assigned_carton_count": _("Colis"),
            "status": _("Statut"),
            "notes": _("Notes"),
        }
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, version=None, **kwargs):
        super().__init__(*args, **kwargs)
        if version is not None:
            self.fields["volunteer_snapshot"].queryset = version.run.volunteer_snapshots.all()
            self.fields["flight_snapshot"].queryset = version.run.flight_snapshots.all()
            if version.status != PlanningVersionStatus.DRAFT:
                for field in self.fields.values():
                    field.disabled = True
        _sort_field_choices(self.fields["volunteer_snapshot"])
        _sort_field_choices(self.fields["status"])
        _append_widget_class(self.fields["volunteer_snapshot"], "form-select")
        _append_widget_class(self.fields["volunteer_snapshot"], "ui-select--lg")
        _append_widget_class(self.fields["flight_snapshot"], "form-select")
        _append_widget_class(self.fields["flight_snapshot"], "ui-select--lg")
        _append_widget_class(self.fields["status"], "form-select")
        _append_widget_class(self.fields["status"], "ui-select--md")


PlanningAssignmentFormSet = forms.modelformset_factory(
    PlanningAssignment,
    form=PlanningAssignmentForm,
    extra=0,
)


def build_assignment_formset(version, *, data=None):
    return PlanningAssignmentFormSet(
        data=data,
        queryset=version.assignments.select_related(
            "shipment_snapshot",
            "volunteer_snapshot",
            "flight_snapshot",
        ).order_by("sequence", "id"),
        prefix="assignments",
        form_kwargs={"version": version},
    )


class PlanningVersionCloneForm(forms.Form):
    change_reason = forms.CharField(
        required=False,
        label=_("Motif du changement"),
        widget=forms.Textarea(attrs={"rows": 2}),
    )


class PlanningCommunicationDraftForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subject"].widget.attrs.setdefault(
            "class",
            "form-control form-control-sm",
        )
        body_attrs = self.fields["body"].widget.attrs
        body_attrs.setdefault("class", "form-control form-control-sm")
        body_attrs.setdefault("rows", 3)
        if self.instance and self.instance.channel == CommunicationChannel.EMAIL:
            body_attrs["data-planning-email-body-source"] = "1"

    class Meta:
        model = CommunicationDraft
        fields = [
            "subject",
            "body",
        ]
        labels = {
            "subject": _("Sujet"),
            "body": _("Message"),
        }
        widgets = {
            "body": forms.Textarea(attrs={"rows": 3}),
        }


PlanningCommunicationDraftFormSet = forms.modelformset_factory(
    CommunicationDraft,
    form=PlanningCommunicationDraftForm,
    extra=0,
)


def build_communication_draft_formset(version, *, data=None):
    return PlanningCommunicationDraftFormSet(
        data=data,
        queryset=version.communication_drafts.select_related("template").order_by(
            "family",
            "channel",
            "recipient_label",
            "id",
        ),
        prefix="drafts",
    )
