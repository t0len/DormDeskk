from django.core.management.base import BaseCommand

from apps.housing.constants import BedState, RoomGender, RoomType
from apps.housing.models import Building, Bed, Room, Floor

class Comand(BaseCommand):
    help = "Создает тестовые данные"

    def handle(self, *args: object, **options: object):
        self.stdout.write("Создание данных")

        building, created = building.objects.get_or_create(
            name = "Главный корпус",
            defaults ={
                "address": "Ул. Пример 1",
                "description": "Главный корпус общежития",
                "is_active": True,
            }
        )

        if created:
            self.stdout.write(f"Создан корпус: {building.name}")

        for floor_number in range(1,3):
            floor, _ =Floor.objects.get_or_create(
                building = building,
                number = floor_number,
            )

            for room_number in range(1,3):
                room, _ = Room.objects.get_or_create(
                floor = floor,
                number = f"{floor.number}0{room_number}",
                defaults= {
                    "room_type": RoomType.DOUBLE,
                    "gender": RoomGender.MALE,
                    },
                )

        self.stdout.write(
            self.style.SUCCESS("Тестовыу Данные созданы")
        )