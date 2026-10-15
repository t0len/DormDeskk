from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, View

from apps.passes.constants import PassStatus
from apps.passes.forms import GuestPassForm
from apps.passes.models import GuestPass
from apps.residency.services import active_residency_for
from apps.users.services import is_security, is_student


class PassListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = GuestPass
    template_name = "passes/list.html"
    context_object_name = "passes"

    def test_func(self) -> bool:
        return is_student(self.request.user)

    def get_queryset(self) -> QuerySet[GuestPass]:
        residency = active_residency_for(self.request.user)
        if not residency:
            return GuestPass.objects.none()
        return GuestPass.objects.filter(residency=residency)


class PassCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = GuestPass
    form_class = GuestPassForm
    template_name = "passes/create.html"
    success_url = reverse_lazy("passes:list")

    def test_func(self) -> bool:
        return is_student(self.request.user)

    def form_valid(self, form: GuestPassForm) -> HttpResponse:
        residency = active_residency_for(self.request.user)
        form.instance.residency = residency
        return super().form_valid(form)


class PassDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = GuestPass
    template_name = "passes/detail.html"
    context_object_name = "guest_pass"

    def test_func(self) -> bool:
        return is_student(self.request.user)

    def get_queryset(self) -> QuerySet[GuestPass]:
        residency = active_residency_for(self.request.user)
        return GuestPass.objects.filter(residency=residency)


class PassCancelView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self) -> bool:
        return is_student(self.request.user)

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        residency = active_residency_for(request.user)
        guest_pass = get_object_or_404(GuestPass, pk=pk, residency=residency)

        if guest_pass.status == PassStatus.PENDING:
            guest_pass.status = PassStatus.CANCELLED
            guest_pass.save(update_fields=["status"])

        return HttpResponseRedirect(reverse_lazy("passes:list"))


class SecurityTodayPassesView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = GuestPass
    template_name = "passes/security_today.html"
    context_object_name = "passes"

    def test_func(self) -> bool:
        return is_security(self.request.user)

    def get_queryset(self) -> QuerySet[GuestPass]:
        today = date.today()
        return GuestPass.objects.filter(
            status=PassStatus.APPROVED,
            visit_date=today,
            residency__bed__room__floor__building__security=self.request.user,
        ).select_related("residency__bed__room", "residency__student")
