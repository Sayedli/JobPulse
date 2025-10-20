from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from django.conf import settings

from django.utils import timezone

from applications.models import Application, ResumeVariant
from applications.services import llm, pdf_utils

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TailorResumeResult:
    resume_variant: ResumeVariant
    generated_file: Optional[Path]
    llm_used: bool


def tailor_resume(
    application: Application, resume_text: str, *, source_pdf_path: Optional[Path] = None
) -> TailorResumeResult:
    """Tailor resume content for a specific application.

    Args:
        application: The associated application.
        resume_text: Plain text extracted from the uploaded resume PDF.
        source_pdf_path: Optional path to the archived PDF file.

    Returns:
        TailorResumeResult containing the stored variant metadata.
    """
    job_posting = application.job_posting
    llm_result = llm.generate_tailored_resume_summary(
        job_title=job_posting.title,
        company=job_posting.company,
        description=job_posting.description or "No description supplied.",
        base_resume_highlights=resume_text,
    )

    summary = _build_summary(job_posting, llm_result)

    file_path = _persist_resume_pdf(
        application=application,
        headline=f"{job_posting.company} – {job_posting.title}",
        summary_text=summary,
        resume_text=resume_text,
        llm_result=llm_result,
    )

    variant = ResumeVariant.objects.create(
        application=application,
        job_posting=job_posting,
        user=application.user,
        headline=f"{job_posting.company} – {job_posting.title}",
        summary=summary,
        file_path=str(file_path) if file_path else "",
        source_pdf_path=str(_relative_path(source_pdf_path)) if source_pdf_path else "",
    )

    absolute_path = Path(settings.BASE_DIR) / file_path if file_path else None

    return TailorResumeResult(
        resume_variant=variant,
        generated_file=absolute_path,
        llm_used=llm_result is not None,
    )


def _persist_resume_pdf(
    application: Application,
    headline: str,
    resume_text: str,
    summary_text: str,
    llm_result: Optional[llm.LLMResult],
) -> Optional[Path]:
    user = application.user
    user_folder = str(user.id) if user else "shared"
    resumes_dir = Path(settings.BASE_DIR) / "generated" / "resumes" / user_folder
    resumes_dir.mkdir(parents=True, exist_ok=True)

    job_posting = application.job_posting
    safe_company = job_posting.company.lower().replace(" ", "-")
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{safe_company}.pdf"
    file_path = resumes_dir / filename

    lines = _compose_resume_lines(job_posting, summary_text, resume_text, llm_result)

    try:
        pdf_utils.write_text_pdf(file_path, lines, title=headline)
        return file_path.relative_to(settings.BASE_DIR)
    except OSError:
        logger.exception("Failed to persist tailored resume PDF for application_id=%s", application.id)
        return None


def _build_summary(job_posting, llm_result: Optional[llm.LLMResult]) -> str:
    if llm_result and llm_result.content:
        return llm_result.content
    highlight = (
        ', '.join(job_posting.tags)
        if job_posting.tags
        else (job_posting.description[:150] if job_posting.description else "the job description")
    )
    return (
        f"- Targeting {job_posting.title} at {job_posting.company}.\n"
        f"- Highlight experience that aligns with {highlight}.\n"
        "- Emphasise impact, metrics, and recent projects relevant to the stack."
    )


def _compose_resume_lines(
    job,
    summary_text: str,
    resume_text: str,
    llm_result: Optional[llm.LLMResult],
) -> list[str]:
    generated_at = timezone.now().strftime("%Y-%m-%d %H:%M")

    lines: list[str] = []
    lines.append(f"{job.company} – {job.title}")
    if job.locations:
        lines.append(job.locations)
    if job.application_url:
        lines.append(f"Application: {job.application_url}")
    lines.append(f"Generated: {generated_at}")
    lines.append("")

    lines.append("Summary Highlights")
    summary_points = [pt.strip("-• ") for pt in summary_text.splitlines() if pt.strip()]
    if not summary_points:
        summary_points = [summary_text.strip()]
    for point in summary_points[:6]:
        lines.append(f"• {point}")
    lines.append("")

    lines.append("Suggested Resume Emphasis")
    emphasis = _extract_resume_snippets(resume_text)
    for snippet in emphasis:
        lines.append(f"• {snippet}")
    lines.append("")

    if llm_result:
        lines.extend(
            [
                "Model Provenance",
                f"Provider: {llm_result.provider}",
                f"Model: {llm_result.model}",
            ]
        )

    return lines


def _extract_resume_snippets(resume_text: str, max_items: int = 10) -> list[str]:
    if not resume_text:
        return ["Review original resume for detailed accomplishments."]

    cleaned = [line.strip() for line in resume_text.splitlines() if line.strip()]
    snippets: list[str] = []
    for line in cleaned:
        normalized = line.strip("-• ")
        if not normalized:
            continue
        snippets.append(normalized)
        if len(snippets) >= max_items:
            break

    if not snippets:
        truncated = resume_text.replace("\n", " ")[:200]
        snippets = [truncated + "…"] if truncated else []

    return snippets or ["Review original resume for detailed accomplishments."]


def _relative_path(path: Path | None) -> Path | None:
    if not path:
        return None
    try:
        return path.relative_to(settings.BASE_DIR)
    except ValueError:
        return path
