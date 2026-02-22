from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from wms.views_next_frontend import frontend_log_event, next_frontend, ui_mode_set

urlpatterns = [
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path(
        "password-help/",
        TemplateView.as_view(template_name="password_help.html"),
        name="password_help",
    ),
    path("ui/mode/", ui_mode_set, name="ui_mode_set"),
    path("ui/mode/<str:mode>/", ui_mode_set, name="ui_mode_set_mode"),
    path("ui/frontend-log/", frontend_log_event, name="frontend_log_event"),
    path("app/", next_frontend, name="next_frontend_root"),
    path("app/<path:path>", next_frontend, name="next_frontend"),
    path("admin/", admin.site.urls),
    path("scan/", include("wms.scan_urls")),
    path("portal/", include("wms.portal_urls")),
    path("api/", include("api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
