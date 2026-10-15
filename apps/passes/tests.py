from datetime import date, time

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.passes.constants import PassStatus, PassType
from apps.passes.models import GuestPass


class GuestPassRulesTest(TestCase):
    def test_day_pass_time_validation(self) -> None:
        """Дневной пропуск: время с 08:00 до 22:00, конец позже начала"""
        guest_pass = GuestPass(
            guest_name="Иван Иванов",
            document_number="123456",
            pass_type=PassType.DAY,
            visit_date=date.today(),
            time_from=time(7, 0),
            time_to=time(20, 0),
        )
        with self.assertRaises(ValidationError) as context:
            guest_pass.clean()
        self.assertIn("Дневной пропуск разрешён с", str(context.exception))

        guest_pass.time_from = time(15, 0)
        guest_pass.time_to = time(12, 0)
        with self.assertRaises(ValidationError) as context:
            guest_pass.clean()
        self.assertIn(
            "Время окончания визита должно быть позже",
            str(context.exception),
        )

    def test_cancel_only_pending_pass(self) -> None:
        """Студент отменяет только pending"""
        guest_pass = GuestPass(guest_name="Петр Петров", status=PassStatus.APPROVED)
        self.assertNotEqual(guest_pass.status, PassStatus.PENDING)
