from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.abstracts.models import TimeStampedModel
from apps.passes.constants import (
    DAY_PASS_END,
    DAY_PASS_START,
    MAX_FUTURE_PASSES,
    PassStatus,
    PassType,
)
from apps.residency.models import Residency
from apps.users.models import User


class GuestPass(TimeStampedModel):
    residency = models.ForeignKey(
        Residency,
        on_delete=models.CASCADE,
        related_name="guest_passes",
        verbose_name="Заселение",
    )
    guest_name = models.CharField(max_length=255, verbose_name="ФИО гостя")
    document_number = models.CharField(max_length=100, verbose_name="Номер документа")
    pass_type = models.CharField(
        max_length=20,
        choices=PassType.choices,
        default=PassType.DAY,
        verbose_name="Тип пропуска",
    )
    visit_date = models.DateField(verbose_name="Дата визита")
    time_from = models.TimeField(verbose_name="Время с", null=True, blank=True)
    time_to = models.TimeField(verbose_name="Время до", null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=PassStatus.choices,
        default=PassStatus.PENDING,
        verbose_name="Статус",
    )
    student_comment = models.TextField(blank=True, verbose_name="Комментарий студента")
    rejection_reason = models.TextField(blank=True, verbose_name="Причина отказа")
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_passes",
        verbose_name="Кто рассмотрел",
    )

    class Meta:
        verbose_name = "Гостевой пропуск"
        verbose_name_plural = "Гостевые пропуска"
        ordering = ["-visit_date"]

    def clean(self) -> None:
        super().clean()

        if hasattr(self, "residency") and self.residency.status != "active":
            raise ValidationError(
                "Пропуск можно создать только для активного заселения."
            )

        if (
            hasattr(self, "residency")
            and self.residency.start_date
            and self.residency.planned_end_date
        ):
            if not (
                self.residency.start_date
                <= self.visit_date
                <= self.residency.planned_end_date
            ):
                raise ValidationError(
                    "Дата визита должна быть в пределах дат вашего заселения."
                )

        if self.pass_type == PassType.DAY:
            if not self.time_from or not self.time_to:
                raise ValidationError(
                    "Для дневного пропуска обязательно укажите время 'с' и 'до'."
                )
            if self.time_from < DAY_PASS_START or self.time_to > DAY_PASS_END:
                start_str = DAY_PASS_START.strftime("%H:%M")
                end_str = DAY_PASS_END.strftime("%H:%M")
                raise ValidationError(
                    f"Дневной пропуск разрешён с {start_str} до {end_str}."
                )
            if self.time_from >= self.time_to:
                raise ValidationError(
                    "Время окончания визита должно быть позже времени начала."
                )

        if not self.pk:
            future_passes_count = GuestPass.objects.filter(
                residency=self.residency,
                visit_date__gte=timezone.now().date(),
                status__in=[PassStatus.PENDING, PassStatus.APPROVED],
            ).count()
            if future_passes_count >= MAX_FUTURE_PASSES:
                raise ValidationError(
                    f"Нельзя иметь больше {MAX_FUTURE_PASSES} пропусков "
                    "(на рассмотрении или одобренных) на будущие даты."
                )

    def __str__(self) -> str:
        return f"{self.guest_name} — {self.get_pass_type_display()} ({self.visit_date})"
