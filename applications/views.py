from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.db import models
from django.db.models import Prefetch
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from applications.forms import ApplicationStatusForm, CoverLetterForm, ResumeTailorForm
from applications.models import Application, ApplicationChecklistItem, JobPosting
from applications.services import checklists, cover_letter, resume


def dashboard(request: HttpRequest) -> HttpResponse:
    status_filter = request.GET.get("status", "all")

    postings_qs = JobPosting.objects.select_related("source").prefetch_related(
        Prefetch(
            "application",
            queryset=Application.objects.prefetch_related("checklist_items"),
        )
    )
    if status_filter != "all":
        postings_qs = postings_qs.filter(application__status=status_filter)
    postings = postings_qs.order_by("-last_seen_at", "company")[:100]

    cards = []
    for posting in postings:
        try:
            application = posting.application
        except Application.DoesNotExist:
            application = None
        cards.append(
            {
                "posting": posting,
                "application": application,
                "status_form": ApplicationStatusForm(instance=application)
                if application
                else ApplicationStatusForm(),
                "resume_form": ResumeTailorForm(),
                "cover_letter_form": CoverLetterForm(
                    initial={"applicant_name": "Your Name", "strengths": "Python, Django"}
                ),
            }
        )

    raw_counts = (
        Application.objects.values("status")
        .order_by()
        .annotate(count=models.Count("id"))  # type: ignore[name-defined]
    )
    status_map = {entry["status"]: entry["count"] for entry in raw_counts}
    status_summaries = [
        {"value": value, "label": label, "count": status_map.get(value, 0)}
        for value, label in Application.Status.choices
    ]

    context = {
        "cards": cards,
        "status_filter": status_filter,
        "status_summaries": status_summaries,
        "application_status_choices": Application.Status.choices,
    }
    return render(request, "dashboard.html", context)


@require_POST
def create_application(request: HttpRequest, pk: int) -> HttpResponse:
    posting = get_object_or_404(JobPosting, pk=pk)
    application, created = Application.objects.get_or_create(job_posting=posting)
    checklists.ensure_default_checklist(application)

    if created:
        messages.success(request, f"Application pipeline created for {posting.company}.")
    else:
        messages.info(request, "Application already exists; refreshed checklist.")
    return redirect("dashboard")


@require_POST
def update_application_status(request: HttpRequest, pk: int) -> HttpResponse:
    application = get_object_or_404(Application, pk=pk)
    form = ApplicationStatusForm(request.POST, instance=application)
    if form.is_valid():
        form.save()
        messages.success(request, "Application status updated.")
    else:
        messages.error(request, "Could not update status. Please check the form inputs.")
    return redirect("dashboard")


@require_POST
def tailor_resume_view(request: HttpRequest, pk: int) -> HttpResponse:
    application = get_object_or_404(Application, pk=pk)
    form = ResumeTailorForm(request.POST)
    if form.is_valid():
        base_resume_text = form.cleaned_data["base_resume_text"] or _load_base_resume()
        result = resume.tailor_resume(application.job_posting, base_resume_text)
        generated_name = result.generated_file.name if result.generated_file else "Stored variant"
        messages.success(request, f"Tailored resume generated: {generated_name}.")
    else:
        messages.error(request, "Resume tailoring failed. Please provide valid text.")
    return redirect("dashboard")


@require_POST
def generate_cover_letter_view(request: HttpRequest, pk: int) -> HttpResponse:
    application = get_object_or_404(Application, pk=pk)
    form = CoverLetterForm(request.POST)
    if form.is_valid():
        strengths = [s.strip() for s in form.cleaned_data["strengths"].split(",") if s.strip()]
        context = cover_letter.CoverLetterContext(
            applicant_name=form.cleaned_data["applicant_name"],
            strengths=strengths or ["software engineering projects"],
            signature=form.cleaned_data["applicant_name"],
            extra_notes=form.cleaned_data.get("extra_notes"),
        )
        letter = cover_letter.generate_cover_letter(
            application.job_posting, context, tone=form.cleaned_data["tone"]
        )
        cover_letter.attach_cover_letter(application, letter)
        messages.success(request, "Cover letter drafted and attached to application.")
    else:
        messages.error(request, "Cover letter form invalid.")
    return redirect("dashboard")


@require_POST
def toggle_checklist_view(request: HttpRequest, pk: int) -> HttpResponse:
    item = get_object_or_404(ApplicationChecklistItem, pk=pk)
    checklists.toggle_checklist_item(item)
    messages.info(request, f"Checklist item '{item.label}' toggled.")
    return redirect("dashboard")


def _load_base_resume() -> str:
    base_path: Path = getattr(settings, "BASE_RESUME_PATH")
    if base_path.exists():
        return base_path.read_text(encoding="utf-8")
    return "Replace this placeholder with your resume content."
