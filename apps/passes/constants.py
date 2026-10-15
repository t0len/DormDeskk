from datetime import time

from django.db import models

MAX_FUTURE_PASSES = 2
DAY_PASS_START = time(8, 0)
DAY_PASS_END = time(22, 0)


class PassType(models.TextChoices):
    DAY = "day", "Дневной"
    OVERNIGHT = "overnight", "Ночной"


class PassStatus(models.TextChoices):
    PENDING = "pending", "На рассмотрении"
    APPROVED = "approved", "Одобрен"
    REJECTED = "rejected", "Отклонён"
    CANCELLED = "cancelled", "Отменён"
