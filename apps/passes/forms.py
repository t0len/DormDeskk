from django import forms

from apps.passes.models import GuestPass


class GuestPassForm(forms.ModelForm):
    class Meta:
        model = GuestPass
        fields = (
            "guest_name",
            "document_number",
            "pass_type",
            "visit_date",
            "time_from",
            "time_to",
            "student_comment",
        )
        widgets = {
            "visit_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "time_from": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            ),
            "time_to": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
        }
