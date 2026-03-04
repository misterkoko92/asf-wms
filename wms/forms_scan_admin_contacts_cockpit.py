from django import forms


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
