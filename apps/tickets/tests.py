from datetime import timedelta
from io import BytesIO

from PIL import Image

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.residency.constants import ResidencyStatus
from apps.residency.models import Residency
from apps.tickets.constants import (
    TICKET_COMMENT_MAXIMUM_LENGTH,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from apps.tickets.models import Ticket, TicketComment
from apps.tickets.services import (
    add_ticket_comment,
    change_ticket_status,
    create_ticket,
)
from apps.users.constants import Role
from apps.users.models import User


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)
class TicketTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.student = User.objects.create_user(email="student@test.local")
        cls.other = User.objects.create_user(email="other@test.local")
        cls.commandant = User.objects.create_user(
            email="commandant@test.local",
            role=Role.COMMANDANT,
        )
        cls.security = User.objects.create_user(
            email="security@test.local",
            role=Role.SECURITY,
        )
        # Only the housing contract is used; housing behavior is tested by its owner.
        building = apps.get_model("housing", "Building").objects.create(
            name="Корпус 1",
            address="Университетская, 1",
        )
        floor = apps.get_model("housing", "Floor").objects.create(
            building=building,
            number=1,
        )
        room = apps.get_model("housing", "Room").objects.create(
            floor=floor,
            number="101",
        )
        bed = apps.get_model("housing", "Bed").objects.create(
            room=room,
            number=1,
            status="normal",
        )
        today = timezone.localdate()
        cls.residency = Residency.objects.create(
            student=cls.student,
            bed=bed,
            start_date=today - timedelta(days=10),
            planned_end_date=today + timedelta(days=30),
        )

    def _ticket(self) -> Ticket:
        return create_ticket(
            actor=self.student,
            category=TicketCategory.PLUMBING,
            title="Течёт кран",
            description="Кран в комнате протекает.",
        )

    def _change(self, ticket: Ticket, status: str, comment: str = "") -> Ticket:
        return change_ticket_status(
            ticket_id=ticket.pk,
            actor=self.commandant,
            new_status=status,
            comment=comment,
        )

    def test_student_creates_with_photo_and_comments(self) -> None:
        self.client.force_login(self.student)
        url = reverse("tickets:create")
        self.assertEqual(self.client.get(url).status_code, 200)
        invalid = self.client.post(
            url,
            {
                "category": TicketCategory.PLUMBING,
                "title": "Течёт кран",
                "description": "",
                "priority": TicketPriority.HIGH,
            },
        )
        self.assertContains(invalid, "Течёт кран")
        self.assertTrue(invalid.context["form"].errors)
        self.assertFalse(Ticket.objects.exists())
        image = BytesIO()
        Image.new("RGB", (4, 4), "white").save(image, format="PNG")
        response = self.client.post(
            url,
            {
                "category": TicketCategory.PLUMBING,
                "title": "Течёт кран",
                "description": "Кран протекает.",
                "priority": TicketPriority.HIGH,
                "photo": SimpleUploadedFile("tap.png", image.getvalue(), "image/png"),
                "status": TicketStatus.DONE,
                "author": self.other.pk,
            },
        )
        ticket = Ticket.objects.get()
        self.assertRedirects(response, reverse("tickets:detail", args=[ticket.pk]))
        self.assertEqual(ticket.author, self.student)
        self.assertEqual(ticket.residency, self.residency)
        self.assertEqual(ticket.status, TicketStatus.NEW)
        self.assertTrue(ticket.photo.storage.exists(ticket.photo.name))
        self.assertContains(self.client.get(reverse("tickets:list")), ticket.title)
        comment_url = reverse("tickets:comments_create", args=[ticket.pk])
        self.assertEqual(self.client.get(comment_url).status_code, 405)
        response = self.client.post(comment_url, {"text": "Вода всё ещё течёт."})
        self.assertRedirects(response, reverse("tickets:detail", args=[ticket.pk]))
        self.assertEqual(ticket.comments.get().author, self.student)
        invalid = self.client.post(comment_url, {"text": " "})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(ticket.comments.count(), 1)

    def test_no_residency_and_role_or_ownership_bypasses(self) -> None:
        ticket = self._ticket()
        detail = reverse("tickets:detail", args=[ticket.pk])
        comments = reverse("tickets:comments_create", args=[ticket.pk])
        self.assertEqual(self.client.get(detail).status_code, 302)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse("tickets:list")), ticket.title)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.post(comments, {"text": "Чужой"}).status_code, 404)
        self.assertIsNone(self.client.get(reverse("tickets:create")).context["form"])
        self.assertEqual(
            self.client.post(reverse("tickets:create"), {}).status_code, 403
        )
        for actor in (self.commandant, self.security):
            with self.subTest(role=actor.role):
                self.client.force_login(actor)
                self.assertEqual(
                    self.client.get(reverse("tickets:list")).status_code, 403
                )
                self.assertEqual(
                    self.client.post(comments, {"text": "Текст"}).status_code, 403
                )
                with self.assertRaises(PermissionDenied):
                    create_ticket(
                        actor=actor,
                        category=TicketCategory.OTHER,
                        title="Test",
                        description="Test",
                    )
        self.assertFalse(TicketComment.objects.exists())

    def test_model_rejects_wrong_author_inactive_dates_and_initial_status(self) -> None:
        today = timezone.localdate()
        cases = [
            {"author": self.other},
            {"author": self.security},
            {"status": TicketStatus.DONE, "closed_at": timezone.now()},
            {"title": " "},
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides):
                data = {
                    "author": self.student,
                    "residency": self.residency,
                    "category": TicketCategory.OTHER,
                    "title": "Test",
                    "description": "Test",
                }
                data.update(overrides)
                with self.assertRaises(ValidationError):
                    Ticket.objects.create(**data)
        for changes in (
            {"status": ResidencyStatus.ENDED},
            {"start_date": today + timedelta(days=1)},
            {"planned_end_date": today - timedelta(days=1)},
        ):
            with self.subTest(changes=changes):
                Residency.objects.filter(pk=self.residency.pk).update(**changes)
                with self.assertRaises(ValidationError):
                    self._ticket()
                self.client.force_login(self.student)
                self.assertIsNone(
                    self.client.get(reverse("tickets:create")).context["form"]
                )
                self.assertEqual(
                    self.client.post(reverse("tickets:create"), {}).status_code, 403
                )
                Residency.objects.filter(pk=self.residency.pk).update(
                    status=ResidencyStatus.ACTIVE,
                    start_date=self.residency.start_date,
                    planned_end_date=self.residency.planned_end_date,
                )

    def test_lifecycle_rejection_and_closed_comment_rules(self) -> None:
        ticket = self._ticket()
        with self.assertRaises(ValidationError):
            self._change(ticket, TicketStatus.DONE, "Нельзя пропускать этап.")
        self._change(ticket, TicketStatus.IN_PROGRESS)
        for comment in ("", " "):
            with self.assertRaises(ValidationError):
                self._change(ticket, TicketStatus.DONE, comment)
        ticket = self._change(ticket, TicketStatus.DONE, "Кран заменён.")
        self.assertIsNotNone(ticket.closed_at)
        self.assertEqual(ticket.comments.get().text, "Кран заменён.")
        with self.assertRaises(ValidationError):
            self._change(ticket, TicketStatus.IN_PROGRESS)
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("tickets:comments_create", args=[ticket.pk]),
            {"text": "Ещё текст"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ticket.comments.count(), 1)
        for initial in (TicketStatus.NEW, TicketStatus.IN_PROGRESS):
            rejected = self._ticket()
            if initial == TicketStatus.IN_PROGRESS:
                self._change(rejected, initial)
            with self.assertRaises(ValidationError):
                self._change(rejected, TicketStatus.REJECTED)
            rejected = self._change(
                rejected, TicketStatus.REJECTED, "Нужна замена узла."
            )
            self.assertEqual(rejected.status, TicketStatus.REJECTED)
            with self.assertRaises(ValidationError):
                self._change(rejected, TicketStatus.IN_PROGRESS)

    def test_services_restrict_actors_and_rollback_invalid_closing_comment(
        self,
    ) -> None:
        ticket = self._ticket()
        for actor in (self.student, self.security):
            with self.assertRaises(PermissionDenied):
                change_ticket_status(
                    ticket_id=ticket.pk,
                    actor=actor,
                    new_status=TicketStatus.IN_PROGRESS,
                )
        for actor in (self.other, self.security):
            with self.assertRaises(PermissionDenied):
                add_ticket_comment(ticket_id=ticket.pk, actor=actor, text="Текст")
        self._change(ticket, TicketStatus.IN_PROGRESS)
        with self.assertRaises(ValidationError):
            self._change(
                ticket,
                TicketStatus.DONE,
                "x" * (TICKET_COMMENT_MAXIMUM_LENGTH + 1),
            )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)
        self.assertIsNone(ticket.closed_at)
        self.assertFalse(ticket.comments.exists())

    def test_existing_ticket_can_be_processed_after_checkout(self) -> None:
        ticket = self._ticket()
        self.residency.status = ResidencyStatus.ENDED
        self.residency.actual_end_date = timezone.localdate()
        self.residency.save()
        self._change(ticket, TicketStatus.IN_PROGRESS)
        self._change(ticket, TicketStatus.DONE, "Починено после выезда.")
        with self.assertRaises(ValidationError):
            self._ticket()

    def test_admin_search_inline_comment_and_status_confirmation(self) -> None:
        ticket = self._ticket()
        self.client.force_login(self.commandant)
        changelist = reverse("admin:tickets_ticket_changelist")
        response = self.client.get(
            changelist,
            {
                "q": self.student.email,
                "category__exact": TicketCategory.PLUMBING,
                "residency__bed__room__floor__building__id__exact": (
                    self.residency.bed.room.floor.building_id
                ),
            },
        )
        self.assertContains(response, ticket.title)
        change_url = reverse("admin:tickets_ticket_change", args=[ticket.pk])
        self.assertContains(self.client.get(change_url), ticket.title)
        response = self.client.post(
            change_url,
            {
                "category": ticket.category,
                "title": ticket.title,
                "description": ticket.description,
                "priority": ticket.priority,
                "assigned_to": self.commandant.pk,
                "new_comment": "Мастер назначен.",
                "comments-TOTAL_FORMS": "0",
                "comments-INITIAL_FORMS": "0",
                "comments-MIN_NUM_FORMS": "0",
                "comments-MAX_NUM_FORMS": "0",
                "_save": "Сохранить",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ticket.comments.get().text, "Мастер назначен.")
        selection = {"_selected_action": [ticket.pk]}
        self.client.post(changelist, {**selection, "action": "take_in_work"})
        response = self.client.post(
            changelist,
            {
                **selection,
                "action": "complete_ticket",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="comment"')
        response = self.client.post(
            changelist,
            {
                **selection,
                "action": "complete_ticket",
                "confirm": "1",
                "comment": " ",
            },
        )
        self.assertEqual(response.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)
        self.client.post(
            changelist,
            {
                **selection,
                "action": "complete_ticket",
                "confirm": "1",
                "comment": "Работы завершены.",
            },
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.DONE)
        self.assertEqual(ticket.comments.count(), 2)
        rejected = self._ticket()
        self.client.post(
            changelist,
            {
                "_selected_action": [rejected.pk],
                "action": "reject_ticket",
                "confirm": "1",
                "comment": "Повреждение не подтверждено.",
            },
        )
        rejected.refresh_from_db()
        self.assertEqual(rejected.status, TicketStatus.REJECTED)

    def test_security_cannot_access_ticket_admin_even_with_broad_user_permissions(
        self,
    ) -> None:
        ticket = self._ticket()
        self.client.force_login(self.security)
        for url in (
            reverse("admin:tickets_ticket_changelist"),
            reverse("admin:tickets_ticket_add"),
            reverse("admin:tickets_ticket_change", args=[ticket.pk]),
            reverse("admin:tickets_ticket_delete", args=[ticket.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.client.post(
            reverse("admin:tickets_ticket_changelist"),
            {
                "action": "take_in_work",
                "_selected_action": [ticket.pk],
            },
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.NEW)
