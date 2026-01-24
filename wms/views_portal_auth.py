from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_http_methods

from .portal_helpers import get_association_profile
from .view_permissions import association_required

@require_http_methods(["GET", "POST"])
def portal_login(request):
    if request.user.is_authenticated:
        profile = get_association_profile(request.user)
        if profile:
            return redirect("portal:portal_dashboard")

    errors = []
    identifier = ""
    next_url = request.GET.get("next") or ""
    if request.method == "POST":
        identifier = (request.POST.get("identifier") or "").strip()
        password = request.POST.get("password") or ""
        next_url = (request.POST.get("next") or "").strip()
        if not identifier or not password:
            errors.append("Email et mot de passe requis.")
        else:
            user = get_user_model().objects.filter(email__iexact=identifier).first()
            username = user.username if user else identifier
            user = authenticate(request, username=username, password=password)
            if not user:
                errors.append("Identifiants invalides.")
            elif not user.is_active:
                errors.append("Compte inactif.")
            elif not get_association_profile(user):
                errors.append("Compte non active par ASF.")
            else:
                login(request, user)
                profile = get_association_profile(user)
                if profile and profile.must_change_password:
                    return redirect("portal:portal_change_password")
                return redirect(next_url or "portal:portal_dashboard")

    return render(
        request,
        "portal/login.html",
        {"errors": errors, "identifier": identifier, "next": next_url},
    )


@login_required(login_url="portal:portal_login")
def portal_logout(request):
    logout(request)
    return redirect("portal:portal_login")


@require_http_methods(["GET", "POST"])
def portal_set_password(request, uidb64, token):
    user = None
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = get_user_model().objects.filter(pk=uid).first()
    except (TypeError, ValueError, OverflowError):
        user = None

    if not user or not default_token_generator.check_token(user, token):
        return render(request, "portal/set_password.html", {"invalid": True})

    form = SetPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        profile = get_association_profile(user)
        if profile and profile.must_change_password:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        login(request, user)
        return redirect("portal:portal_dashboard")

    return render(request, "portal/set_password.html", {"form": form, "invalid": False})


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_change_password(request):
    form = SetPasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        profile = request.association_profile
        if profile.must_change_password:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        messages.success(request, "Mot de passe mis a jour.")
        return redirect("portal:portal_dashboard")
    return render(request, "portal/change_password.html", {"form": form})
