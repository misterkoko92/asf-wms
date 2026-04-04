from django import forms

from .models import CartonFormat


class CartonFormatCrudForm(forms.ModelForm):
    class Meta:
        model = CartonFormat
        fields = ("name", "length_cm", "width_cm", "height_cm", "max_weight_g", "is_default")
        widgets = {
            "name": forms.TextInput(),
            "length_cm": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "width_cm": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "height_cm": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "max_weight_g": forms.NumberInput(attrs={"min": 1, "step": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == "is_default":
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"
