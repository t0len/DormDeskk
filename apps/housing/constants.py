from django.db import models

class RoomType(models.TextChoices):
    DOUBLE = "double", "двухместная"
    TRIPLE = "triple", "трехместная"
    QUAD = "quad", "четырехместная"

class BedState(models.TextChoices):
    NORMAL = "normal", "Впорядке"
    OUT_OF_SERVICE = "out_of_service", "Снят с эксплуатации"

class RoomGender(models.TextChoices):
    MALE = "male", "Мужская"
    FEMALE = "female", "Женская"

