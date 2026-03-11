from django import forms
from django.utils.translation import gettext_lazy as _

from .models import (
    CommunicationDraft,
    CommunicationDraftStatus,
    PlanningAssignment,
    PlanningRun,
    PlanningVersionStatus,
)


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
