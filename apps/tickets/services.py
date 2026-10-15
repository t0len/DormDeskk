from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.residency.models import Residency
from apps.residency.services import active_residency_for
from apps.tickets.constants import (
    ALLOWED_STATUS_TRANSITION,
    CLOSED_STATUSES,
    TicketPriority,
)
from apps.tickets.models import Ticket, TicketComment
from apps.users.models import User
from apps.users.services import is_commandant, is_student


def residency_for_new_ticket(user: User) -> Residency | None:
    residency = active_residency_for(user)
    if residency is None:
        return None
    today = timezone.localdate()
    end_date = residency.actual_end_date or residency.planned_end_date
    if not residency.start_date <= today <= end_date:
        return None
    return residency


def create_ticket(
    *,
    actor: User,
    category: str,
    title: str,
    description: str,
    photo: UploadedFile | None = None,
    priority: str = TicketPriority.MEDIUM,
) -> Ticket:
    if not is_student(actor):
        raise PermissionDenied("Создать заявку может только студент.")
    residency = residency_for_new_ticket(actor)
    if residency is None:
        raise ValidationError("Для создания заявки нужно активное заселение.")
    return Ticket.objects.create(
        author=actor,
        residency=residency,
        category=category,
        title=title,
        description=description,
        photo=photo or "",
        priority=priority,
    )


@transaction.atomic
def add_ticket_comment(*, ticket_id: int, actor: User, text: str) -> TicketComment:
    if not is_student(actor) and not is_commandant(actor):
        raise PermissionDenied("Комментарии доступны студенту и коменданту.")
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
    if is_student(actor) and ticket.author_id != actor.pk:
        raise PermissionDenied("Нельзя комментировать чужую заявку.")
    return TicketComment.objects.create(ticket=ticket, author=actor, text=text)


@transaction.atomic
def change_ticket_status(
    *,
    ticket_id: int,
    actor: User,
    new_status: str,
    comment: str = "",
) -> Ticket:
    if not is_commandant(actor):
        raise PermissionDenied("Статус заявки меняет только комендант.")
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
    if new_status not in ALLOWED_STATUS_TRANSITION.get(ticket.status, frozenset()):
        raise ValidationError("Недопустимый переход статуса.")
    comment = comment.strip()
    if new_status in CLOSED_STATUSES and not comment:
        raise ValidationError("Для закрытия или отказа нужен комментарий.")
    ticket.status = new_status
    ticket.closed_at = timezone.now() if new_status in CLOSED_STATUSES else None
    ticket.save(update_fields=["status", "closed_at", "updated_at"])
    if comment:
        # Comment validation and status changes commit or roll back together.
        TicketComment.objects.create(ticket=ticket, author=actor, text=comment)
    return ticket


def get_tickets_for_student(student_id: int) -> QuerySet[Ticket]:
    return Ticket.objects.filter(author_id=student_id).select_related(
        "residency__bed__room__floor__building",
        "assigned_to",
    )
