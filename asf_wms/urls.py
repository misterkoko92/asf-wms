from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path(
        "password-help/",
        TemplateView.as_view(template_name="password_help.html"),
        name="password_help",
    ),
    path("admin/", admin.site.urls),
    path("scan/", include("wms.scan_urls")),
    path("portal/", include("wms.portal_urls")),
    path("api/", include("api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
