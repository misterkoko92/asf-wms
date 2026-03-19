from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import include, path
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView

urlpatterns = [
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path(
        "favicon.ico",
        RedirectView.as_view(url=staticfiles_storage.url("scan/icon.png"), permanent=False),
    ),
    path(
        "password-help/",
        TemplateView.as_view(template_name="password_help.html"),
        name="password_help",
    ),
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("scan/", include("wms.scan_urls")),
    path("portal/", include("wms.portal_urls")),
    path("benevole/", include("wms.volunteer_urls")),
    path("planning/", include("wms.planning_urls")),
    path("api/", include("api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
