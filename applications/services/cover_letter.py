from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pathlib import Path
from typing import Optional

from django.conf import settings
from django.utils import timezone

from applications.models import Application, CoverLetterVariant, JobPosting
from applications.services import llm, pdf_utils


@dataclass(slots=True)
class CoverLetterContext:
    applicant_name: str
    strengths: list[str]
    signature: str
    extra_notes: Optional[str] = None


def generate_cover_letter(
    job_posting: JobPosting, context: CoverLetterContext, *, tone: str = "enthusiastic"
) -> str:
    llm_result = llm.generate_cover_letter(
        job_title=job_posting.title,
        company=job_posting.company,
        strengths=context.strengths,
        tone=tone,
        base_signature=context.signature,
        extra_notes=context.extra_notes,
    )
    if llm_result:
        return llm_result.content

    strengths = ", ".join(context.strengths)
    intro = (
        f"Dear Hiring Team at {job_posting.company},\n\n"
        f"I am excited to apply for the {job_posting.title} role. "
        f"My background includes {strengths} and a passion for solving challenging problems."
    )
    middle = (
        f"\n\nDuring my recent projects, I aligned closely with the focus areas "
        f"highlighted in this opportunity. I thrive in collaborative environments and "
        f"am eager to contribute to {job_posting.company}'s mission."
    )
    closing = f"\n\nThank you for your time and consideration.\n\n{context.signature}"
    body = intro + middle
    if context.extra_notes:
        body += f"\n\nAdditional context: {context.extra_notes}"
    return body + closing


def attach_cover_letter(application: Application, content: str) -> Application:
    application.cover_letter = content
    application.save(update_fields=["cover_letter"])
    return application


def persist_cover_letter_variant(
    application: Application,
    content: str,
    *,
    subject: str | None = None,
) -> CoverLetterVariant:
    if subject is None:
        subject = f"{application.job_posting.title}"
    variant = CoverLetterVariant.objects.create(
        application=application,
        user=application.user,
        subject=subject,
        body=content,
    )

    file_path = _write_cover_letter_file(application, variant, content)
    if file_path:
        variant.file_path = str(file_path)
        variant.save(update_fields=["file_path"])
    return variant


def _write_cover_letter_file(
    application: Application, variant: CoverLetterVariant, content: str
) -> Optional[Path]:
    base_dir = Path(settings.BASE_DIR) / "generated" / "cover_letters" / str(application.user_id)
    base_dir.mkdir(parents=True, exist_ok=True)
    safe_company = application.job_posting.company.lower().replace(" ", "-")
    filename = f"cl_{variant.id}_{safe_company}.pdf"
    file_path = base_dir / filename

    lines = _compose_cover_letter_lines(application, variant, content)

    try:
        pdf_utils.write_text_pdf(file_path, lines, title=variant.subject or "Cover Letter")
        return file_path
    except OSError:
        return None


def _compose_cover_letter_lines(
    application: Application, variant: CoverLetterVariant, content: str
) -> list[str]:
    job = application.job_posting
    generated = timezone.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = []
    lines.append(f"{job.company} – {job.title}")
    if job.locations:
        lines.append(job.locations)
    if job.application_url:
        lines.append(f"Application: {job.application_url}")
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.extend(content.splitlines())
    return lines
