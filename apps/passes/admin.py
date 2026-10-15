from datetime import date

from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest

from apps.passes.constants import PassStatus
from apps.passes.models import GuestPass
from apps.users.services import is_security


@admin.register(GuestPass)
class GuestPassAdmin(admin.ModelAdmin):
    list_display = (
        "guest_name",
        "residency",
        "pass_type",
        "visit_date",
        "status",
        "reviewed_by",
    )
    list_filter = ("status", "pass_type", "visit_date")
    search_fields = (
        "guest_name",
        "document_number",
        "residency__student__email",
    )
    actions = ["approve_passes", "reject_passes"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[GuestPass]:
        qs = super().get_queryset(request)
        if is_security(request.user):
            return qs.filter(
                residency__bed__room__floor__building__security=request.user
            )
        return qs

    @admin.action(description="Одобрить выбранные пропуска")
    def approve_passes(
        self, request: HttpRequest, queryset: QuerySet[GuestPass]
    ) -> None:
        today = date.today()
        invalid_passes = queryset.filter(visit_date__lt=today)
        if invalid_passes.exists():
            self.message_user(
                request,
                "Некоторые пропуска не одобрены: дата визита уже прошла.",
                level=messages.WARNING,
            )

        valid_qs = queryset.filter(visit_date__gte=today, status=PassStatus.PENDING)
        updated = valid_qs.update(status=PassStatus.APPROVED, reviewed_by=request.user)
        self.message_user(
            request,
            f"Успешно одобрено пропусков: {updated}",
            level=messages.SUCCESS,
        )

    @admin.action(description="Отклонить выбранные пропуска")
    def reject_passes(
        self, request: HttpRequest, queryset: QuerySet[GuestPass]
    ) -> None:
        updated = queryset.update(status=PassStatus.REJECTED, reviewed_by=request.user)
        self.message_user(
            request,
            f"Отклонено пропусков: {updated}",
            level=messages.SUCCESS,
        )
