from typing import Any

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse

from apps.tickets.constants import (
    TICKET_COMMENT_MAXIMUM_LENGTH,
    TicketStatus,
)
from apps.tickets.forms import TicketStatusForm
from apps.tickets.models import Ticket, TicketComment
from apps.tickets.services import add_ticket_comment, change_ticket_status
from apps.users.services import is_commandant


class TicketAdminForm(forms.ModelForm):
    new_comment = forms.CharField(
        label="Новый служебный комментарий",
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        max_length=TICKET_COMMENT_MAXIMUM_LENGTH,
        help_text="Автором будет текущий комендант.",
    )

    class Meta:
        model = Ticket
        fields = [
            "category",
            "title",
            "description",
            "photo",
            "priority",
            "assigned_to",
        ]


class TicketCommentInline(admin.TabularInline):
    model = TicketComment
    fields = ("text", "author", "created_at")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(
        self,
        request: HttpRequest,
        obj: Ticket | None = None,
    ) -> bool:
        return False

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: Ticket | None = None,
    ) -> bool:
        return False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    form = TicketAdminForm
    inlines = (TicketCommentInline,)
    list_display = (
        "id",
        "title",
        "author",
        "category",
        "priority",
        "status",
        "assigned_to",
        "created_at",
        "closed_at",
    )
    search_fields = (
        "title",
        "author__email",
        "author__first_name",
        "author__last_name",
        "author__student_profile__student_number",
    )
    list_filter = ("status", "category", "residency__bed__room__floor__building")
    list_select_related = ("author", "assigned_to", "residency")
    readonly_fields = (
        "author",
        "residency",
        "status",
        "created_at",
        "closed_at",
        "updated_at",
    )
    fields = (
        "author",
        "residency",
        "category",
        "title",
        "description",
        "photo",
        "priority",
        "assigned_to",
        "status",
        "closed_at",
        "created_at",
        "updated_at",
        "new_comment",
    )
    actions = ("take_in_work", "complete_ticket", "reject_ticket")

    def has_module_permission(self, request: HttpRequest) -> bool:
        return is_commandant(request.user)

    def has_view_permission(
        self,
        request: HttpRequest,
        obj: Ticket | None = None,
    ) -> bool:
        return is_commandant(request.user)

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: Ticket | None = None,
    ) -> bool:
        return is_commandant(request.user)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: Ticket | None = None,
    ) -> bool:
        return False

    def save_model(
        self,
        request: HttpRequest,
        obj: Ticket,
        form: TicketAdminForm,
        change: bool,
    ) -> None:
        super().save_model(request, obj, form, change)
        comment = form.cleaned_data.get("new_comment", "")
        if comment:
            add_ticket_comment(ticket_id=obj.pk, actor=request.user, text=comment)

    def _apply_status(
        self,
        request: HttpRequest,
        queryset: QuerySet[Ticket],
        new_status: str,
        comment: str = "",
    ) -> None:
        if not is_commandant(request.user):
            raise PermissionDenied
        updated = 0
        for ticket in queryset:
            try:
                change_ticket_status(
                    ticket_id=ticket.pk,
                    actor=request.user,
                    new_status=new_status,
                    comment=comment,
                )
            except ValidationError as error:
                self.message_user(
                    request,
                    f"Заявка №{ticket.pk}: {' '.join(error.messages)}",
                    messages.ERROR,
                )
            else:
                updated += 1
        if updated:
            self.message_user(
                request, f"Обновлено заявок: {updated}.", messages.SUCCESS
            )

    def _close_with_comment(
        self,
        request: HttpRequest,
        queryset: QuerySet[Ticket],
        *,
        new_status: str,
        action: str,
        title: str,
    ) -> HttpResponse | None:
        if not is_commandant(request.user):
            raise PermissionDenied
        confirmed = "confirm" in request.POST
        form = TicketStatusForm(request.POST if confirmed else None)
        if confirmed and form.is_valid():
            self._apply_status(
                request, queryset, new_status, form.cleaned_data["comment"]
            )
            return None
        context: dict[str, Any] = {
            **self.admin_site.each_context(request),
            "title": title,
            "opts": self.model._meta,
            "form": form,
            "tickets": queryset,
            "action": action,
            "media": self.media + form.media,
        }
        return TemplateResponse(request, "admin/tickets/status_action.html", context)

    @admin.action(description="Взять в работу", permissions=["change"])
    def take_in_work(
        self,
        request: HttpRequest,
        queryset: QuerySet[Ticket],
    ) -> None:
        self._apply_status(request, queryset, TicketStatus.IN_PROGRESS)

    @admin.action(description="Завершить с комментарием", permissions=["change"])
    def complete_ticket(
        self,
        request: HttpRequest,
        queryset: QuerySet[Ticket],
    ) -> HttpResponse | None:
        return self._close_with_comment(
            request,
            queryset,
            new_status=TicketStatus.DONE,
            action="complete_ticket",
            title="Завершить заявки",
        )

    @admin.action(description="Отклонить с причиной", permissions=["change"])
    def reject_ticket(
        self,
        request: HttpRequest,
        queryset: QuerySet[Ticket],
    ) -> HttpResponse | None:
        return self._close_with_comment(
            request,
            queryset,
            new_status=TicketStatus.REJECTED,
            action="reject_ticket",
            title="Отклонить заявки",
        )
