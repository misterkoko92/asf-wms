from django.urls import path

from . import views

app_name = "volunteer"

urlpatterns = [
    path("login/", views.volunteer_login, name="login"),
    path("logout/", views.volunteer_logout, name="logout"),
    path("change-password/", views.volunteer_change_password, name="change_password"),
    path("profil/", views.volunteer_profile, name="profile"),
    path("contraintes/", views.volunteer_constraints, name="constraints"),
    path("", views.volunteer_dashboard, name="dashboard"),
]
