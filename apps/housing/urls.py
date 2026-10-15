from django.urls import path

from apps.housing.view import BuildingListView, BuildingDetailView, RoomDetailView


app_name = "housing"

urlpatterns: list = [
    path("", BuildingListView.as_view(), name = "building_list"),
    path("/building/<int:pk>", BuildingDetailView.as_view(), name = "building_detail"),
    path("/rooms/<int:pk>", RoomDetailView.as_view(), name="room_detail")
]