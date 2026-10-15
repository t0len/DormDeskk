from django.db import models

TITLE_MAXIMUM_LENGTH = 100
CONSTANTS_MAXIMUM_LENGTH = 20
TICKET_COMMENT_MAXIMUM_LENGTH = 200


class TicketCategory(models.TextChoices):
    PLUMBING = "plumbing", "Сантехника"
    ELECTRICITY = "electricity", "Электрика"
    FURNITURE = "furniture", "Мебель"
    INTERNET = "internet", "Интернет"
    OTHER = "other", "Другое"


class TicketPriority(models.TextChoices):
    LOW = "low", "Низкий"
    MEDIUM = "medium", "Средний"
    HIGH = "high", "Высокий"


class TicketStatus(models.TextChoices):
    NEW = "new", "Новая"
    IN_PROGRESS = "in_progress", "В работе"
    DONE = "done", "Завершена"
    REJECTED = "rejected", "Отклонена"


CLOSED_STATUSES = frozenset({TicketStatus.DONE, TicketStatus.REJECTED})
ALLOWED_STATUS_TRANSITION = {
    TicketStatus.NEW: frozenset({TicketStatus.IN_PROGRESS, TicketStatus.REJECTED}),
    TicketStatus.IN_PROGRESS: CLOSED_STATUSES,
    TicketStatus.DONE: frozenset(),
    TicketStatus.REJECTED: frozenset(),
}
