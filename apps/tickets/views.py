from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.tickets.constants import CLOSED_STATUSES
from apps.tickets.forms import TicketCommentForm, TicketForm
from apps.tickets.models import Ticket, TicketComment
from apps.tickets.services import (
    add_ticket_comment,
    create_ticket,
    get_tickets_for_student,
    residency_for_new_ticket,
)
from apps.users.models import User
from apps.users.services import is_student


def _require_student(user: User) -> None:
    if not is_student(user):
        raise PermissionDenied("Этот раздел доступен только студентам.")


def _add_service_errors(form: forms.BaseForm, error: ValidationError) -> None:
    if hasattr(error, "error_dict"):
        for field, errors in error.error_dict.items():
            form.add_error(
                field if field in form.fields else None,
                ValidationError(errors),
            )
    else:
        form.add_error(None, error)


def _render_ticket_detail(
    request: HttpRequest,
    ticket: Ticket,
    comment_form: TicketCommentForm | None = None,
    *,
    status: int = 200,
) -> HttpResponse:
    return render(
        request,
        "tickets/detail.html",
        {
            "ticket": ticket,
            "comments": ticket.comments.select_related("author"),
            "comment_form": comment_form
            if comment_form is not None
            else TicketCommentForm(),
            "can_comment": ticket.status not in CLOSED_STATUSES,
        },
        status=status,
    )


@login_required
@require_GET
def ticket_list(request: HttpRequest) -> HttpResponse:
    _require_student(request.user)
    return render(
        request,
        "tickets/list.html",
        {
            "tickets": get_tickets_for_student(request.user.pk),
            "active_residency": residency_for_new_ticket(request.user),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def ticket_create(request: HttpRequest) -> HttpResponse:
    _require_student(request.user)
    residency = residency_for_new_ticket(request.user)
    if residency is None:
        return render(
            request,
            "tickets/create.html",
            {"form": None},
            status=403 if request.method == "POST" else 200,
        )
    form = TicketForm(
        request.POST if request.method == "POST" else None,
        request.FILES or None,
        instance=Ticket(author=request.user, residency=residency),
    )
    if request.method == "POST" and form.is_valid():
        try:
            ticket = create_ticket(actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            return redirect("tickets:detail", pk=ticket.pk)
    return render(request, "tickets/create.html", {"form": form})


@login_required
@require_GET
def ticket_detail(request: HttpRequest, pk: int) -> HttpResponse:
    _require_student(request.user)
    ticket = get_object_or_404(get_tickets_for_student(request.user.pk), pk=pk)
    return _render_ticket_detail(request, ticket)


@login_required
@require_POST
def ticket_comment_create(request: HttpRequest, pk: int) -> HttpResponse:
    _require_student(request.user)
    ticket = get_object_or_404(get_tickets_for_student(request.user.pk), pk=pk)
    form = TicketCommentForm(
        request.POST,
        instance=TicketComment(ticket=ticket, author=request.user),
    )
    if form.is_valid():
        try:
            add_ticket_comment(
                ticket_id=ticket.pk,
                actor=request.user,
                text=form.cleaned_data["text"],
            )
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            return redirect("tickets:detail", pk=ticket.pk)
    return _render_ticket_detail(request, ticket, form, status=400)
