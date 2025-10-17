from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from django.conf import settings

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

    if llm_result:
        summary = llm_result.content
    else:
        summary = (
            f"- Targeting {job_posting.title} at {job_posting.company}.\n"
            f"- Highlight experience that aligns with: "
            f"{', '.join(job_posting.tags) or job_posting.description[:120] or 'the job description'}.\n"
            "- Emphasise impact, metrics, and recent projects relevant to the stack."
        )

    variant = ResumeVariant.objects.create(
        application=application,
        job_posting=job_posting,
        user=application.user,
        headline=f"{job_posting.company} – {job_posting.title}",
        summary=summary,
    )

    if source_pdf_path:
        variant.source_pdf_path = str(source_pdf_path)
        variant.save(update_fields=["source_pdf_path"])

    generated_file = _persist_resume_stub(variant, resume_text, llm_result)
    if generated_file:
        variant.file_path = str(generated_file)
        variant.save(update_fields=["file_path"])
    return TailorResumeResult(
        resume_variant=variant,
        generated_file=generated_file,
        llm_used=llm_result is not None,
    )


def _persist_resume_stub(
    variant: ResumeVariant, base_resume_text: str, llm_result: Optional[llm.LLMResult]
) -> Optional[Path]:
    user_folder = str(variant.user_id) if variant.user_id else "shared"
    resumes_dir = Path(settings.BASE_DIR) / "generated" / "resumes" / user_folder
    resumes_dir.mkdir(parents=True, exist_ok=True)

    safe_company = variant.job_posting.company.lower().replace(" ", "-")
    filename = f"{variant.id}_{safe_company}.pdf"
    file_path = resumes_dir / filename

    lines: list[str] = [
        "Tailored Resume Draft",
        "",
        f"Role: {variant.job_posting.title}",
        f"Company: {variant.job_posting.company}",
        "",
        "Summary:",
    ]
    summary_lines = variant.summary.splitlines() or [variant.summary]
    lines.extend(summary_lines)
    lines.extend(["", "Base Resume Reference:"])
    lines.extend(base_resume_text.splitlines())
    if llm_result:
        lines.extend(["", "Generated via:", f"{llm_result.provider}:{llm_result.model}"])

    try:
        pdf_utils.write_text_pdf(file_path, lines, title=variant.headline)
        return file_path
    except OSError:
        logger.exception("Failed to persist tailored resume for variant_id=%s", variant.id)
        return None
