from django import forms

from apps.tickets.constants import TICKET_COMMENT_MAXIMUM_LENGTH
from apps.tickets.models import Ticket, TicketComment


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["category", "title", "description", "photo", "priority"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}


class TicketCommentForm(forms.ModelForm):
    class Meta:
        model = TicketComment
        fields = ["text"]
        widgets = {"text": forms.Textarea(attrs={"rows": 3})}


class TicketStatusForm(forms.Form):
    comment = forms.CharField(
        label="Комментарий",
        widget=forms.Textarea(attrs={"rows": 4}),
        strip=True,
        max_length=TICKET_COMMENT_MAXIMUM_LENGTH,
    )
