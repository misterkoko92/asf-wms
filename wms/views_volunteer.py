from collections import defaultdict
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.db.models import Max, Min
from django.forms import formset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .forms_volunteer import (
    VolunteerAccountForm,
    VolunteerAvailabilityForm,
    VolunteerAvailabilityWeekForm,
    VolunteerConstraintForm,
    VolunteerProfileForm,
)
from .models import VolunteerAvailability, VolunteerConstraint, VolunteerUnavailability
from .view_permissions import volunteer_required

DAY_NAMES = (
    _("Lundi"),
    _("Mardi"),
    _("Mercredi"),
    _("Jeudi"),
    _("Vendredi"),
    _("Samedi"),
    _("Dimanche"),
)


def _next_monday(today: date) -> date:
    days_ahead = (7 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def _max_iso_week(year: int) -> int:
    return date(year, 12, 28).isocalendar().week


def _iter_week_ranges(year: int):
    for week in range(1, _max_iso_week(year) + 1):
        start = date.fromisocalendar(year, week, 1)
        yield week, start, start + timedelta(days=6)


def _build_week_days(week_start: date):
    days = []
    for offset, day_name in enumerate(DAY_NAMES):
        day_date = week_start + timedelta(days=offset)
        days.append(
            {
                "date": day_date,
                "label": f"{day_name} {day_date.strftime('%d/%m/%Y')}",
            }
        )
    return days


def _latest_week_availability_map(*, profile, week_start, week_end):
    availability_map = {}
    availabilities = VolunteerAvailability.objects.filter(
        volunteer=profile,
        date__range=(week_start, week_end),
    ).order_by("date", "-created_at", "-id")
    for availability in availabilities:
        availability_map.setdefault(availability.date, availability)
    return availability_map


def _week_form_initials(*, profile, week_days, week_start, week_end):
    unavailability_dates = set(
        VolunteerUnavailability.objects.filter(
            volunteer=profile,
            date__range=(week_start, week_end),
        ).values_list("date", flat=True)
    )
    availability_map = _latest_week_availability_map(
        profile=profile,
        week_start=week_start,
        week_end=week_end,
    )
    initials = []
    for day in week_days:
        day_date = day["date"]
        initial = {
            "date": day_date,
            "availability": "unavailable",
            "start_time": "",
            "end_time": "",
        }
        if day_date in unavailability_dates:
            initials.append(initial)
            continue
        availability = availability_map.get(day_date)
        if availability is None:
            initials.append(initial)
            continue
        initial.update(
            {
                "availability": "available",
                "start_time": availability.start_time.strftime("%H:%M"),
                "end_time": availability.end_time.strftime("%H:%M"),
            }
        )
        initials.append(initial)
    return initials


def _resolve_week_start(request):
    if request.method == "POST":
        value = request.POST.get("week_start")
        if value:
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                pass

    base = _next_monday(timezone.localdate())
    week_param = request.GET.get("week")
    year_param = request.GET.get("year")
    try:
        year_value = int(year_param) if year_param else base.isocalendar().year
    except ValueError:
        year_value = base.isocalendar().year

    if week_param:
        try:
            week_value = int(week_param)
            if 1 <= week_value <= _max_iso_week(year_value):
                return date.fromisocalendar(year_value, week_value, 1)
        except ValueError:
            pass

    return base


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


@volunteer_required
def volunteer_availability_list(request):
    profile = request.volunteer_profile
    availabilities = profile.availabilities.all()
    return render(
        request,
        "benevole/availability_list.html",
        {"availabilities": availabilities, "profile": profile},
    )


@volunteer_required
def volunteer_availability_create(request):
    profile = request.volunteer_profile
    week_start = _resolve_week_start(request)
    week_days = _build_week_days(week_start)
    week_end = week_start + timedelta(days=6)
    week_meta = week_start.isocalendar()
    week_options = [
        {
            "week": week,
            "label": _("Semaine %(week)s") % {"week": week},
        }
        for week, _start, _end in _iter_week_ranges(week_meta.year)
    ]
    formset_class = formset_factory(VolunteerAvailabilityWeekForm, extra=0)

    if request.method == "POST":
        formset = formset_class(request.POST)
        if formset.is_valid():
            created = 0
            for form in formset:
                availability_choice = form.cleaned_data.get("availability")
                day_date = form.cleaned_data.get("date")
                if not day_date:
                    continue
                VolunteerAvailability.objects.filter(volunteer=profile, date=day_date).delete()
                if availability_choice != "available":
                    VolunteerUnavailability.objects.update_or_create(
                        volunteer=profile,
                        date=day_date,
                    )
                    continue
                VolunteerUnavailability.objects.filter(volunteer=profile, date=day_date).delete()
                VolunteerAvailability.objects.create(
                    volunteer=profile,
                    date=day_date,
                    start_time=form.cleaned_data["start_time"],
                    end_time=form.cleaned_data["end_time"],
                )
                created += 1
            messages.success(
                request,
                _("%(count)s disponibilite(s) enregistree(s).") % {"count": created},
            )
            return redirect("volunteer:availability_list")
    else:
        formset = formset_class(
            initial=_week_form_initials(
                profile=profile,
                week_days=week_days,
                week_start=week_start,
                week_end=week_end,
            )
        )

    for form, day in zip(formset.forms, week_days):
        form.day_label = day["label"]

    return render(
        request,
        "benevole/availability_week_form.html",
        {
            "formset": formset,
            "profile": profile,
            "week_end": week_end,
            "week_number": week_meta.week,
            "week_options": week_options,
            "week_start": week_start,
            "week_year": week_meta.year,
        },
    )


@volunteer_required
def volunteer_availability_edit(request, pk):
    profile = request.volunteer_profile
    availability = get_object_or_404(VolunteerAvailability, pk=pk, volunteer=profile)
    if request.method == "POST":
        form = VolunteerAvailabilityForm(
            request.POST,
            instance=availability,
            volunteer=profile,
        )
        if form.is_valid():
            updated_availability = form.save()
            VolunteerUnavailability.objects.filter(
                volunteer=profile,
                date=updated_availability.date,
            ).delete()
            messages.success(request, _("Disponibilite mise a jour."))
            return redirect("volunteer:availability_list")
    else:
        form = VolunteerAvailabilityForm(instance=availability, volunteer=profile)
    return render(
        request,
        "benevole/availability_form.html",
        {
            "availability": availability,
            "form": form,
            "profile": profile,
            "title": _("Modifier une disponibilite"),
        },
    )


@volunteer_required
def volunteer_availability_delete(request, pk):
    profile = request.volunteer_profile
    availability = get_object_or_404(VolunteerAvailability, pk=pk, volunteer=profile)
    if request.method == "POST":
        availability.delete()
        messages.success(request, _("Disponibilite supprimee."))
        return redirect("volunteer:availability_list")
    return render(
        request,
        "benevole/availability_confirm_delete.html",
        {"availability": availability, "profile": profile},
    )


@volunteer_required
def volunteer_availability_recap(request):
    profile = request.volunteer_profile
    week_start = _resolve_week_start(request)
    week_meta = week_start.isocalendar()
    week_end = week_start + timedelta(days=6)
    week_days = _build_week_days(week_start)
    week_options = [
        {
            "week": week,
            "label": _("Semaine %(week)s - du lundi %(start)s au dimanche %(end)s")
            % {
                "week": week,
                "start": start.strftime("%d/%m/%Y"),
                "end": end.strftime("%d/%m/%Y"),
            },
        }
        for week, start, end in _iter_week_ranges(week_meta.year)
    ]

    availability_rows = (
        VolunteerAvailability.objects.filter(date__range=(week_start, week_end))
        .values("volunteer_id", "date")
        .annotate(start=Min("start_time"), end=Max("end_time"))
    )
    availability_map = defaultdict(dict)
    for row in availability_rows:
        availability_map[row["volunteer_id"]][row["date"]] = (row["start"], row["end"])

    unavailability_rows = VolunteerUnavailability.objects.filter(
        date__range=(week_start, week_end)
    ).values("volunteer_id", "date")
    unavailability_map = defaultdict(set)
    for row in unavailability_rows:
        unavailability_map[row["volunteer_id"]].add(row["date"])

    recap_rows = []
    profiles = (
        type(profile)
        .objects.select_related("user")
        .order_by(
            "user__last_name",
            "user__first_name",
            "id",
        )
    )
    for volunteer_profile in profiles:
        full_name = volunteer_profile.user.get_full_name().strip()
        label = full_name or volunteer_profile.user.email or volunteer_profile.user.username
        days = []
        for day in week_days:
            day_date = day["date"]
            availability = availability_map.get(volunteer_profile.id, {}).get(day_date)
            if availability:
                days.append(
                    {
                        "status": "available",
                        "start": availability[0].strftime("%H:%M"),
                        "end": availability[1].strftime("%H:%M"),
                    }
                )
                continue
            if day_date in unavailability_map.get(volunteer_profile.id, set()):
                days.append({"status": "unavailable", "start": "", "end": ""})
                continue
            days.append({"status": "empty", "start": "", "end": ""})
        recap_rows.append({"days": days, "name": label})

    return render(
        request,
        "benevole/availability_recap.html",
        {
            "profile": profile,
            "recap_rows": recap_rows,
            "week_days": week_days,
            "week_end": week_end,
            "week_number": week_meta.week,
            "week_options": week_options,
            "week_start": week_start,
            "week_year": week_meta.year,
        },
    )
