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
