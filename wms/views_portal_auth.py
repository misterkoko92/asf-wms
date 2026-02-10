from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode
from django.views.decorators.http import require_http_methods

from .portal_helpers import get_association_profile
from .view_permissions import association_required

TEMPLATE_LOGIN = "portal/login.html"
TEMPLATE_SET_PASSWORD = "portal/set_password.html"  # nosec B105
TEMPLATE_CHANGE_PASSWORD = "portal/change_password.html"  # nosec B105

ERROR_LOGIN_REQUIRED = "Email et mot de passe requis."
ERROR_LOGIN_INVALID = "Identifiants invalides."
ERROR_ACCOUNT_INACTIVE = "Compte inactif."
ERROR_ACCOUNT_NOT_ACTIVE = "Compte non active par ASF."
MESSAGE_PASSWORD_UPDATED = "Mot de passe mis a jour."  # nosec B105


def _build_login_context(*, errors, identifier, next_url):
    return {"errors": errors, "identifier": identifier, "next": next_url}


def _authenticate_portal_user(request, identifier, password):
    user = get_user_model().objects.filter(email__iexact=identifier).first()
    username = user.username if user else identifier
    return authenticate(request, username=username, password=password)


def _set_profile_password_changed(profile):
    if profile and profile.must_change_password:
        profile.must_change_password = False
        profile.save(update_fields=["must_change_password"])


def _get_user_from_uidb64(uidb64):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
        return None
    return get_user_model().objects.filter(pk=uid).first()


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


@require_http_methods(["GET", "POST"])
def portal_login(request):
    if request.user.is_authenticated:
        profile = get_association_profile(request.user)
        if profile:
            return redirect("portal:portal_dashboard")

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
            user = _authenticate_portal_user(request, identifier, password)
            if not user:
                errors.append(ERROR_LOGIN_INVALID)
            elif not user.is_active:
                errors.append(ERROR_ACCOUNT_INACTIVE)
            else:
                profile = get_association_profile(user)
                if not profile:
                    errors.append(ERROR_ACCOUNT_NOT_ACTIVE)
                    return render(
                        request,
                        TEMPLATE_LOGIN,
                        _build_login_context(
                            errors=errors,
                            identifier=identifier,
                            next_url=next_url,
                        ),
                    )
                login(request, user)
                if profile and profile.must_change_password:
                    return redirect("portal:portal_change_password")
                return redirect(next_url or "portal:portal_dashboard")

    return render(
        request,
        TEMPLATE_LOGIN,
        _build_login_context(errors=errors, identifier=identifier, next_url=next_url),
    )


@login_required(login_url="portal:portal_login")
def portal_logout(request):
    logout(request)
    return redirect("portal:portal_login")


@require_http_methods(["GET", "POST"])
def portal_set_password(request, uidb64, token):
    user = _get_user_from_uidb64(uidb64)

    if not user or not default_token_generator.check_token(user, token):
        return render(request, TEMPLATE_SET_PASSWORD, {"invalid": True})

    form = SetPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        _set_profile_password_changed(get_association_profile(user))
        login(request, user)
        return redirect("portal:portal_dashboard")

    return render(request, TEMPLATE_SET_PASSWORD, {"form": form, "invalid": False})


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_change_password(request):
    form = SetPasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        _set_profile_password_changed(request.association_profile)
        messages.success(request, MESSAGE_PASSWORD_UPDATED)
        return redirect("portal:portal_dashboard")
    return render(request, TEMPLATE_CHANGE_PASSWORD, {"form": form})
