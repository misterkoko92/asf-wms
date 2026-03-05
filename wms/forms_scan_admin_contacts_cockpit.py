from django import forms

from .models import OrganizationRole


class OrganizationContactUpsertForm(forms.Form):
    organization_id = forms.IntegerField(min_value=1)
    organization_contact_id = forms.IntegerField(required=False, min_value=1)
    title = forms.CharField(required=False, max_length=10)
    first_name = forms.CharField(required=False, max_length=120)
    last_name = forms.CharField(required=False, max_length=120)
    email = forms.EmailField(required=False)
    phone = forms.CharField(required=False, max_length=40)
    is_active = forms.BooleanField(required=False)


class RoleContactActionForm(forms.Form):
    role_assignment_id = forms.IntegerField(min_value=1)
    organization_contact_id = forms.IntegerField(min_value=1)


class ShipperScopeUpsertForm(forms.Form):
    role_assignment_id = forms.IntegerField(min_value=1)
    scope_id = forms.IntegerField(required=False, min_value=1)
    all_destinations = forms.BooleanField(required=False)
    destination_id = forms.IntegerField(required=False, min_value=1)
    valid_from = forms.DateTimeField(required=False)
    valid_to = forms.DateTimeField(required=False)


class ShipperScopeDisableForm(forms.Form):
    scope_id = forms.IntegerField(min_value=1)


class RecipientBindingUpsertForm(forms.Form):
    binding_id = forms.IntegerField(required=False, min_value=1)
    shipper_org_id = forms.IntegerField(min_value=1)
    recipient_org_id = forms.IntegerField(min_value=1)
    destination_id = forms.IntegerField(min_value=1)
    valid_from = forms.DateTimeField(required=False)
    valid_to = forms.DateTimeField(required=False)


class RecipientBindingCloseForm(forms.Form):
    binding_id = forms.IntegerField(min_value=1)
    valid_to = forms.DateTimeField(required=True)


class GuidedContactCreateForm(forms.Form):
    entity_kind = forms.ChoiceField(
        choices=(
            ("organization", "organization"),
            ("organization_with_contact", "organization_with_contact"),
        )
    )
    organization_name = forms.CharField(required=False, max_length=200)
    name = forms.CharField(required=False, max_length=200)
    first_name = forms.CharField(required=False, max_length=120)
    last_name = forms.CharField(required=False, max_length=120)
    email = forms.EmailField(required=False)
    phone = forms.CharField(required=False, max_length=40)
    role = forms.CharField(required=False, max_length=40)
    is_active = forms.BooleanField(required=False)

    def clean(self):
        cleaned = super().clean()
        entity_kind = cleaned.get("entity_kind")

        role_value = (cleaned.get("role") or "").strip().lower()
        if role_value and role_value not in {choice[0] for choice in OrganizationRole.choices}:
            self.add_error("role", "Role initial invalide.")

        organization_name = (cleaned.get("organization_name") or "").strip()
        person_fields = ("name", "first_name", "last_name", "email", "phone")

        if entity_kind == "organization":
            if not organization_name:
                self.add_error("organization_name", "Nom organisation requis.")
            if not role_value:
                self.add_error("role", "Role initial requis.")
        if entity_kind == "organization_with_contact":
            if not organization_name:
                self.add_error("organization_name", "Nom organisation requis.")
            if not role_value:
                self.add_error("role", "Role initial requis.")
            for field_name in person_fields:
                if not (cleaned.get(field_name) or "").strip():
                    self.add_error(
                        field_name,
                        "Champ requis pour creer la personne rattachee.",
                    )
        return cleaned
