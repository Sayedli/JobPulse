from __future__ import annotations

from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from django.db import models
from django.db.models import Prefetch

from applications.forms import (
    ApplicationStatusForm,
    AutoApplyConsentForm,
    CoverLetterForm,
    ResumeTailorForm,
    UserProfileForm,
)
from applications.models import (
    Application,
    ApplicationChecklistItem,
    CoverLetterVariant,
    JobDescriptionSnapshot,
    JobPosting,
    ResumeVariant,
    UserProfile,
)
from applications.services import (
    auto_apply,
    checklists,
    cover_letter,
    job_description,
    pdf_utils,
    resume,
)


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    status_filter = request.GET.get("status", "all")
    profile = _get_or_create_profile(request.user)

    applications_prefetch = Prefetch(
        "applications",
        queryset=Application.objects.filter(user=request.user)
        .select_related("job_posting")
        .prefetch_related(
            "checklist_items",
            "auto_apply_attempts",
            "resume_variants",
            "cover_letter_variants",
        ),
        to_attr="user_applications",
    )
    postings_qs = JobPosting.objects.select_related("source").prefetch_related(applications_prefetch)
    if status_filter != "all":
        postings_qs = postings_qs.filter(applications__status=status_filter, applications__user=request.user)
    postings = postings_qs.order_by("-last_seen_at", "company")[:100]

    cards: list[dict[str, Any]] = []
    for posting in postings:
        application = None
        if hasattr(posting, "user_applications") and posting.user_applications:
            application = posting.user_applications[0]
        cards.append(
            {
                "posting": posting,
                "application": application,
                "status_form": ApplicationStatusForm(instance=application)
                if application
                else ApplicationStatusForm(),
                "resume_form": ResumeTailorForm(),
                "cover_letter_form": CoverLetterForm(
                    initial={
                        "applicant_name": profile.display_name
                        or request.user.get_full_name()
                        or request.user.username,
                        "strengths": "Python, Django",
                    }
                ),
                "auto_apply_form": AutoApplyConsentForm(),
                "last_auto_apply": application.auto_apply_attempts.first() if application else None,
                "resume_versions": list(
                    application.resume_variants.order_by("-created_at")
                )
                if application
                else [],
                "cover_letter_versions": list(
                    application.cover_letter_variants.order_by("-created_at")
                )
                if application
                else [],
            }
        )

    raw_counts = (
        Application.objects.filter(user=request.user)
        .values("status")
        .order_by()
        .annotate(count=models.Count("id"))
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
        "profile_form": UserProfileForm(instance=profile),
    }
    return render(request, "dashboard.html", context)


@login_required
@require_POST
def create_application(request: HttpRequest, pk: int) -> HttpResponse:
    posting = get_object_or_404(JobPosting, pk=pk)
    application, created = Application.objects.get_or_create(
        job_posting=posting,
        user=request.user,
        defaults={"status": Application.Status.TODO},
    )
    checklists.ensure_default_checklist(application)

    if created:
        messages.success(request, f"Application pipeline created for {posting.company}.")
    else:
        messages.info(request, "Application already exists; refreshed checklist.")
    return redirect("applications:dashboard")


@login_required
@require_POST
def update_application_status(request: HttpRequest, pk: int) -> HttpResponse:
    application = get_object_or_404(Application, pk=pk, user=request.user)
    form = ApplicationStatusForm(request.POST, instance=application)
    if form.is_valid():
        form.save()
        messages.success(request, "Application status updated.")
    else:
        messages.error(request, "Could not update status. Please check the form inputs.")
    return redirect("applications:dashboard")


@login_required
@require_POST
def tailor_resume_view(request: HttpRequest, pk: int) -> HttpResponse:
    application = get_object_or_404(Application, pk=pk, user=request.user)
    form = ResumeTailorForm(request.POST, request.FILES)
    if form.is_valid():
        resume_pdf = form.cleaned_data["resume_pdf"]
        try:
            saved_path = pdf_utils.save_uploaded_pdf(request.user, resume_pdf)
            resume_text = pdf_utils.extract_text_from_pdf(resume_pdf)
        except pdf_utils.PdfProcessingError as exc:
            messages.error(request, f"Could not process PDF: {exc}")
            return redirect("applications:dashboard")

        result = resume.tailor_resume(application, resume_text, source_pdf_path=saved_path)
        generated_name = result.generated_file.name if result.generated_file else "Stored variant"
        suffix = "via LLM" if result.llm_used else "via template"
        messages.success(
            request,
            f"Tailored resume generated ({suffix}): {generated_name}. Source saved to {saved_path.name}.",
        )
    else:
        messages.error(request, "Resume tailoring failed. Upload a PDF smaller than 5 MB.")
    return redirect("applications:dashboard")


@login_required
@require_POST
def generate_cover_letter_view(request: HttpRequest, pk: int) -> HttpResponse:
    application = get_object_or_404(Application, pk=pk, user=request.user)
    form = CoverLetterForm(request.POST)
    if form.is_valid():
        strengths = [s.strip() for s in form.cleaned_data["strengths"].split(",") if s.strip()]
        profile = _get_or_create_profile(request.user)
        context = cover_letter.CoverLetterContext(
            applicant_name=form.cleaned_data["applicant_name"],
            strengths=strengths or ["software engineering projects"],
            signature=profile.cover_letter_signature or form.cleaned_data["applicant_name"],
            extra_notes=form.cleaned_data.get("extra_notes"),
        )
        letter = cover_letter.generate_cover_letter(
            application.job_posting, context, tone=form.cleaned_data["tone"]
        )
        cover_letter.attach_cover_letter(application, letter)
        cover_letter.persist_cover_letter_variant(application, letter)
        messages.success(request, "Cover letter drafted and saved as a new version.")
    else:
        messages.error(request, "Cover letter form invalid.")
    return redirect("applications:dashboard")


@login_required
@require_POST
def toggle_checklist_view(request: HttpRequest, pk: int) -> HttpResponse:
    item = get_object_or_404(ApplicationChecklistItem, pk=pk, application__user=request.user)
    checklists.toggle_checklist_item(item)
    messages.info(request, f"Checklist item '{item.label}' toggled.")
    return redirect("applications:dashboard")


@login_required
@require_POST
def auto_apply_view(request: HttpRequest, pk: int) -> HttpResponse:
    application = get_object_or_404(Application, pk=pk, user=request.user)
    form = AutoApplyConsentForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please acknowledge the automation safeguard checkbox.")
        return redirect("applications:dashboard")

    try:
        result = auto_apply.run_auto_apply(
            application,
            acknowledge_risk=form.cleaned_data["acknowledge_risk"],
        )
        messages.success(request, f"Automation executed: {result.notes}")
    except auto_apply.AutoApplySafetyError as exc:
        messages.warning(request, str(exc))
    except Exception as exc:  # pragma: no cover - depends on selenium runtime
        messages.error(request, f"Automation failed: {exc}")
    return redirect("applications:dashboard")


@login_required
def profile_settings(request: HttpRequest) -> HttpResponse:
    profile = _get_or_create_profile(request.user)
    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("applications:profile")
        messages.error(request, "Could not update profile. Please fix the errors below.")
    else:
        form = UserProfileForm(instance=profile)
    return render(request, "profile_settings.html", {"form": form})


@login_required
def download_resume_variant(request: HttpRequest, pk: int) -> HttpResponse:
    variant = get_object_or_404(ResumeVariant, pk=pk, application__user=request.user)
    file_path = _resolve_resume_path(variant)
    if not file_path:
        messages.error(request, "No file associated with this resume variant.")
        return redirect("applications:dashboard")

    response = FileResponse(file_path.open("rb"), as_attachment=True, filename=file_path.name)
    response["Content-Type"] = "application/pdf"
    return response


@login_required
def download_cover_letter_variant(request: HttpRequest, pk: int) -> HttpResponse:
    variant = get_object_or_404(CoverLetterVariant, pk=pk, application__user=request.user)
    if variant.file_path:
        file_path = Path(variant.file_path).resolve()
        base_dir = Path(settings.BASE_DIR).resolve()
        if base_dir in file_path.parents and file_path.exists():
            return FileResponse(file_path.open("rb"), as_attachment=True, filename=file_path.name)

    response = HttpResponse(variant.body, content_type="text/plain")
    response["Content-Disposition"] = f"attachment; filename=cover_letter_{variant.pk}.txt"
    return response


@login_required
def job_description_detail(request: HttpRequest, pk: int) -> JsonResponse:
    posting = get_object_or_404(JobPosting, pk=pk)
    refresh = request.GET.get("refresh") == "1"
    description = job_description.get_description(posting, refresh=refresh)
    snapshot = getattr(posting, "description_snapshot", None)
    if snapshot is None:
        snapshot = JobDescriptionSnapshot.objects.filter(job_posting=posting).first()
    return JsonResponse({
        "description": description,
        "source_url": posting.application_url,
        "fetched_at": snapshot.fetched_at.isoformat() if snapshot else timezone.now().isoformat(),
    })
def _get_or_create_profile(user) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _resolve_resume_path(variant: ResumeVariant) -> Path | None:
    if variant.file_path:
        file_path = Path(variant.file_path)
        if file_path.exists():
            return file_path

    application = variant.application
    if not application or not application.user_id:
        return None

    generated_dir = Path(settings.BASE_DIR) / "generated" / "resumes" / str(application.user_id)
    if not generated_dir.exists():
        return None

    candidates = sorted(generated_dir.glob("*.pdf"), key=lambda p: p.stat().st_ctime, reverse=True)
    return candidates[0] if candidates else None
