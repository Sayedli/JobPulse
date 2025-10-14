from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from django.conf import settings

from applications.models import JobPosting, ResumeVariant

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TailorResumeResult:
    resume_variant: ResumeVariant
    generated_file: Optional[Path]


def tailor_resume(job_posting: JobPosting, base_resume_text: str) -> TailorResumeResult:
    """
    Very lightweight tailoring strategy:
    - Emphasise the company + role in the summary.
    - Leave breadcrumbs for future integration with LLM tooling or document editors.
    """
    summary = (
        f"Targeting {job_posting.title} at {job_posting.company}. "
        f"Focus on matching projects to: {', '.join(job_posting.tags) or job_posting.description[:120]}"
    )

    variant = ResumeVariant.objects.create(
        job_posting=job_posting,
        headline=f"{job_posting.company} – {job_posting.title}",
        summary=summary,
    )

    generated_file = _persist_resume_stub(variant, base_resume_text)
    if generated_file:
        variant.file_path = str(generated_file)
        variant.save(update_fields=["file_path"])
    return TailorResumeResult(resume_variant=variant, generated_file=generated_file)


def _persist_resume_stub(variant: ResumeVariant, base_resume_text: str) -> Optional[Path]:
    resumes_dir = Path(settings.BASE_DIR) / "generated" / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{variant.id}_{variant.job_posting.company.lower().replace(' ', '-')}.txt"
    file_path = resumes_dir / filename

    try:
        tailored_content = (
            f"# Tailored Resume Stub\n\n"
            f"## Role: {variant.job_posting.title}\n"
            f"## Company: {variant.job_posting.company}\n\n"
            f"{base_resume_text}\n"
        )
        file_path.write_text(tailored_content, encoding="utf-8")
        return file_path
    except OSError:
        logger.exception("Failed to persist tailored resume for variant_id=%s", variant.id)
        return None
