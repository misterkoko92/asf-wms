from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from .view_permissions import volunteer_required

TEMPLATE_LOGIN = "benevole/login.html"
TEMPLATE_CHANGE_PASSWORD = "benevole/change_password.html"  # nosec B105  # pragma: allowlist secret

ERROR_LOGIN_REQUIRED = _("Email et mot de passe requis.")
ERROR_LOGIN_INVALID = _("Identifiants invalides.")
ERROR_ACCOUNT_INACTIVE = _("Compte inactif.")
ERROR_ACCOUNT_NOT_ACTIVE = _("Compte bénévole non activé.")
MESSAGE_PASSWORD_UPDATED = _("Mot de passe mis à jour.")  # nosec B105


def _get_volunteer_profile(user):
    return getattr(user, "volunteer_profile", None)


def _safe_next_url(request, next_url):
    candidate = (next_url or "").strip()
    if not candidate:
        return ""
    if not url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return ""
    return candidate


def _authenticate_volunteer_user(request, identifier, password):
    user = get_user_model().objects.filter(email__iexact=identifier).first()
    username = user.username if user else identifier
    return authenticate(request, username=username, password=password)


def _set_profile_password_changed(profile):
    if profile and profile.must_change_password:
        profile.must_change_password = False
        profile.save(update_fields=["must_change_password"])


@require_http_methods(["GET", "POST"])
def volunteer_login(request):
    if request.user.is_authenticated:
        profile = _get_volunteer_profile(request.user)
        if profile and profile.is_active:
            return redirect(
                "volunteer:change_password"
                if profile.must_change_password
                else "volunteer:dashboard"
            )

    errors = []
    identifier = ""
    next_url = _safe_next_url(request, request.GET.get("next"))
    if request.method == "POST":
        identifier = (request.POST.get("identifier") or "").strip()
        password = request.POST.get("password") or ""
        next_url = _safe_next_url(request, request.POST.get("next"))
        if not identifier or not password:
            errors.append(ERROR_LOGIN_REQUIRED)
        else:
            user = _authenticate_volunteer_user(request, identifier, password)
            if not user:
                errors.append(ERROR_LOGIN_INVALID)
            elif not user.is_active:
                errors.append(ERROR_ACCOUNT_INACTIVE)
            else:
                profile = _get_volunteer_profile(user)
                if not profile or not profile.is_active:
                    errors.append(ERROR_ACCOUNT_NOT_ACTIVE)
                else:
                    login(request, user)
                    if profile.must_change_password:
                        return redirect("volunteer:change_password")
                    return redirect(next_url or "volunteer:dashboard")

    return render(
        request,
        TEMPLATE_LOGIN,
        {"errors": errors, "identifier": identifier, "next": next_url},
    )


@login_required(login_url="volunteer:login")
def volunteer_logout(request):
    logout(request)
    return redirect("volunteer:login")


@volunteer_required
@require_http_methods(["GET", "POST"])
def volunteer_change_password(request):
    form = SetPasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        _set_profile_password_changed(request.volunteer_profile)
        messages.success(request, MESSAGE_PASSWORD_UPDATED)
        return redirect("volunteer:dashboard")
    return render(request, TEMPLATE_CHANGE_PASSWORD, {"form": form})


@volunteer_required
def volunteer_dashboard(request):
    return HttpResponse("Volunteer dashboard")
