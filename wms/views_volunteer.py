from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from .forms_volunteer import (
    VolunteerAccountForm,
    VolunteerConstraintForm,
    VolunteerProfileForm,
)
from .models import VolunteerConstraint
from .view_permissions import volunteer_required


@volunteer_required
def volunteer_dashboard(request):
    profile = request.volunteer_profile
    recent_availabilities = profile.availabilities.order_by("-date", "-start_time")[:5]
    return render(
        request,
        "benevole/dashboard.html",
        {
            "profile": profile,
            "recent_availabilities": recent_availabilities,
        },
    )


@volunteer_required
def volunteer_profile(request):
    profile = request.volunteer_profile
    if request.method == "POST":
        account_form = VolunteerAccountForm(request.POST, instance=request.user)
        profile_form = VolunteerProfileForm(request.POST, instance=profile)
        if account_form.is_valid() and profile_form.is_valid():
            account_form.save()
            profile_form.save()
            messages.success(request, _("Coordonnees mises a jour."))
            return redirect("volunteer:profile")
    else:
        account_form = VolunteerAccountForm(instance=request.user)
        profile_form = VolunteerProfileForm(instance=profile)
    return render(
        request,
        "benevole/profile.html",
        {
            "account_form": account_form,
            "profile": profile,
            "profile_form": profile_form,
        },
    )


@volunteer_required
def volunteer_constraints(request):
    profile = request.volunteer_profile
    constraints, _created = VolunteerConstraint.objects.get_or_create(volunteer=profile)
    if request.method == "POST":
        form = VolunteerConstraintForm(request.POST, instance=constraints)
        if form.is_valid():
            form.save()
            messages.success(request, _("Contraintes mises a jour."))
            return redirect("volunteer:constraints")
    else:
        form = VolunteerConstraintForm(instance=constraints)
    return render(
        request,
        "benevole/constraints.html",
        {"form": form, "profile": profile},
    )
