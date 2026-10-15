from django.conf import settings
from django.conf.urls import include, path
from django.conf.urls.static import static
from django.contrib import admin

admin.site.site_header = "DormDesk"
admin.site.site_title = "DormDesk"
admin.site.index_title = "Общежитие"


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.abstracts.urls")),
    path("housing/", include("apps.housing.urls")),
    path("tickets/", include("apps.tickets.urls")),
    path("residency/", include("apps.residency.urls")),
    path("passes/", include("apps.passes.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
