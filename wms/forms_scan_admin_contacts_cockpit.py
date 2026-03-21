from django import forms


class ShipmentAuthorizedRecipientDefaultForm(forms.Form):
    link_id = forms.IntegerField(min_value=1)
    recipient_contact_id = forms.IntegerField(min_value=1)


class ShipmentRecipientOrganizationActionForm(forms.Form):
    recipient_organization_id = forms.IntegerField(min_value=1)


class ShipmentRecipientOrganizationMergeForm(forms.Form):
    source_recipient_organization_id = forms.IntegerField(min_value=1)
    target_recipient_organization_id = forms.IntegerField(min_value=1)
