from typing import Any

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import MaxLengthValidator
from django.db import models
from django.utils import timezone

from apps.abstracts.models import TimeStampedModel
from apps.residency.constants import ResidencyStatus
from apps.tickets.constants import (
    ALLOWED_STATUS_TRANSITION,
    CLOSED_STATUSES,
    CONSTANTS_MAXIMUM_LENGTH,
    TICKET_COMMENT_MAXIMUM_LENGTH,
    TITLE_MAXIMUM_LENGTH,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from apps.users.services import is_commandant, is_student


class Ticket(TimeStampedModel):
    residency = models.ForeignKey(
        "residency.Residency",
        on_delete=models.PROTECT,
        related_name="tickets",
        verbose_name="заселение",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tickets",
        verbose_name="автор",
    )
    category = models.CharField(
        "категория",
        max_length=CONSTANTS_MAXIMUM_LENGTH,
        choices=TicketCategory.choices,
    )
    title = models.CharField("заголовок", max_length=TITLE_MAXIMUM_LENGTH)
    description = models.TextField("описание")
    photo = models.ImageField("фотография", upload_to="tickets/%Y/%m", blank=True)
    priority = models.CharField(
        "приоритет",
        max_length=CONSTANTS_MAXIMUM_LENGTH,
        choices=TicketPriority.choices,
        default=TicketPriority.MEDIUM,
    )
    status = models.CharField(
        "статус",
        max_length=CONSTANTS_MAXIMUM_LENGTH,
        choices=TicketStatus.choices,
        default=TicketStatus.NEW,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_tickets",
        verbose_name="исполнитель",
        blank=True,
        null=True,
    )
    closed_at = models.DateTimeField("дата закрытия", blank=True, null=True)

    class Meta:
        verbose_name = "заявка на ремонт"
        verbose_name_plural = "заявки на ремонт"
        ordering = ["-created_at", "-pk"]

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        super().clean()
        errors = {}
        self.title = self.title.strip()
        self.description = self.description.strip()
        if not self.title:
            errors["title"] = "Укажите заголовок."
        if not self.description:
            errors["description"] = "Укажите описание."
        previous = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        try:
            if self.author_id and not is_student(self.author):
                errors["author"] = "Автором заявки может быть только студент."
            if self.residency_id:
                residency = self.residency
                if self.author_id and residency.student_id != self.author_id:
                    errors["residency"] = "Заселение должно принадлежать автору заявки."
                # Existing repairs can still be processed after the student leaves.
                if previous is None:
                    today = timezone.localdate()
                    end_date = residency.actual_end_date or residency.planned_end_date
                    if (
                        residency.status != ResidencyStatus.ACTIVE
                        or not residency.start_date <= today <= end_date
                    ):
                        errors["residency"] = "Нужно текущее активное заселение."
        except ObjectDoesNotExist:
            errors["__all__"] = "Выбранный автор или заселение не существует."
        if previous is None:
            if self.status != TicketStatus.NEW:
                errors["status"] = "Новая заявка должна иметь статус «Новая»."
        else:
            if (self.author_id, self.residency_id) != (
                previous.author_id,
                previous.residency_id,
            ):
                errors["__all__"] = "Нельзя менять автора и заселение готовой заявки."
            if self.status != previous.status and self.status not in (
                ALLOWED_STATUS_TRANSITION.get(previous.status, frozenset())
            ):
                errors["status"] = "Этот переход статуса запрещён."
        if self.status in CLOSED_STATUSES and self.closed_at is None:
            errors["closed_at"] = "У закрытой заявки должна быть дата закрытия."
        elif self.status not in CLOSED_STATUSES and self.closed_at is not None:
            errors["closed_at"] = "У открытой заявки не может быть даты закрытия."
        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class TicketComment(TimeStampedModel):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="заявка",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_comments",
        verbose_name="автор",
    )
    text = models.TextField(
        "текст",
        max_length=TICKET_COMMENT_MAXIMUM_LENGTH,
        validators=[MaxLengthValidator(TICKET_COMMENT_MAXIMUM_LENGTH)],
    )

    class Meta:
        verbose_name = "комментарий к заявке"
        verbose_name_plural = "комментарии к заявкам"
        ordering = ["created_at", "pk"]

    def __str__(self) -> str:
        return f"Комментарий к заявке №{self.ticket_id}: {self.text[:50]}"

    def clean(self) -> None:
        super().clean()
        self.text = self.text.strip()
        if not self.text:
            raise ValidationError({"text": "Комментарий не может быть пустым."})
        try:
            if self.author_id:
                if is_student(self.author):
                    if self.ticket_id and self.ticket.author_id != self.author_id:
                        raise ValidationError("Нельзя комментировать чужую заявку.")
                    if self.ticket_id and self.ticket.status in CLOSED_STATUSES:
                        raise ValidationError("Нельзя комментировать закрытую заявку.")
                elif not is_commandant(self.author):
                    raise ValidationError("Комментарии доступны студенту и коменданту.")
        except ObjectDoesNotExist as exc:
            raise ValidationError("Автор или заявка не существует.") from exc

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)
