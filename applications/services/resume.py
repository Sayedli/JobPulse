from __future__ import annotations

import logging
from collections import Counter
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

    summary_points = _extract_summary_points(summary_text)
    if summary_points:
        lines.append("SUMMARY HIGHLIGHTS")
        for point in summary_points[:6]:
            lines.append(f"• {point}")
        lines.append("")

    emphasis = _extract_resume_snippets(resume_text)
    requirements = _extract_job_requirements(job.description or "")
    if requirements:
        alignments = _build_alignment_lines(requirements, emphasis)
        if alignments:
            lines.append("ROLE ALIGNMENT CHECKLIST")
            for alignment in alignments:
                lines.append(f"• {alignment}")
            lines.append("")

    lines.append("RECENT IMPACT HIGHLIGHTS")
    for snippet in emphasis[:10]:
        lines.append(f"• {snippet}")
    lines.append("")

    skills = _derive_skill_keywords(resume_text)
    if skills:
        lines.append("SKILLS TO SURFACE")
        lines.append(", ".join(skills))
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


def _extract_summary_points(summary_text: str) -> list[str]:
    if not summary_text:
        return []
    points: list[str] = []
    for raw in summary_text.splitlines():
        cleaned = raw.strip()
        if not cleaned:
            continue
        cleaned = cleaned.lstrip("-•* ")
        if cleaned:
            points.append(cleaned)
    if points:
        return points
    cleaned = summary_text.strip()
    return [cleaned] if cleaned else []


STOPWORDS = {
    "and",
    "the",
    "with",
    "for",
    "from",
    "that",
    "this",
    "will",
    "have",
    "into",
    "your",
    "their",
    "about",
    "work",
    "team",
    "able",
    "experience",
    "using",
    "related",
    "skills",
    "ability",
    "strong",
    "across",
    "build",
    "developers",
    "engineers",
}


def _extract_job_requirements(description: str, max_items: int = 8) -> list[str]:
    if not description:
        return []
    lines: list[str] = []
    for raw in description.splitlines():
        line = raw.strip()
        if not line:
            continue
        bullet = False
        if line[0] in "-•*–":
            bullet = True
            line = line.lstrip("-•*– ").strip()
        elif len(line) > 2 and line[0].isdigit():
            bullet = True
            line = line.lstrip("0123456789. )(").strip()
        if bullet or len(line) <= 140:
            cleaned = line.rstrip(";")
            if cleaned:
                lines.append(cleaned)
        if len(lines) >= max_items:
            break
    if not lines:
        sentences = [part.strip() for part in description.split(".") if part.strip()]
        lines = sentences[:max_items]
    return lines


def _build_alignment_lines(requirements: list[str], accomplishments: list[str]) -> list[str]:
    if not requirements:
        return []
    keyword_cache = {_normalize_keywords(req): req for req in requirements}
    acc_keyword_cache = [_normalize_keywords(acc) for acc in accomplishments]
    used_accomplishments: set[int] = set()
    alignments: list[str] = []

    for requirement in requirements[:6]:
        req_keywords = _normalize_keywords(requirement)
        best_idx = None
        best_score = 0
        for idx, acc_keywords in enumerate(acc_keyword_cache):
            if idx in used_accomplishments:
                continue
            if not acc_keywords:
                continue
            overlap = len(req_keywords & acc_keywords)
            if overlap > best_score:
                best_score = overlap
                best_idx = idx
        if best_idx is not None and best_score > 0:
            used_accomplishments.add(best_idx)
            highlight = accomplishments[best_idx]
            alignments.append(f"{requirement} → Highlight: {highlight}")
        else:
            focus = ", ".join(sorted(req_keywords - STOPWORDS)) if req_keywords else requirement
            if not focus:
                focus = requirement
            alignments.append(
                f"{requirement} → Plan: Map a measurable win that demonstrates ownership of this requirement."
            )
    return alignments


def _normalize_keywords(text: str) -> set[str]:
    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9\+#/][A-Za-z0-9\+#/]{1,}", text)
        if len(token) > 2
    ]
    return {token for token in tokens if token not in STOPWORDS}


def _derive_skill_keywords(resume_text: str, max_items: int = 12) -> list[str]:
    if not resume_text:
        return []
    skills: list[str] = []
    for line in resume_text.splitlines():
        lower = line.lower()
        if any(keyword in lower for keyword in ("skill", "technolog", "stack", "proficien")) or ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                candidates = re.split(r"[;,/•\-]", parts[1])
            else:
                candidates = re.split(r"[;,/•\-]", line)
            for candidate in candidates:
                cleaned = candidate.strip()
                if len(cleaned) < 2:
                    continue
                if cleaned.lower() in STOPWORDS:
                    continue
                skills.append(cleaned)
    if not skills:
        tokens = [
            token
            for token in re.findall(r"[A-Z][A-Za-z0-9\+#/]{1,}", resume_text)
            if len(token) > 1
        ]
        skills = tokens

    if not skills:
        return []

    counts = Counter(token.strip() for token in skills if token.strip())
    ordered = [item for item, _ in counts.most_common(max_items)]
    deduped: list[str] = []
    seen: set[str] = set()
    for item in ordered:
        key = item.lower()
        if key in seen:
            continue
        deduped.append(item)
        seen.add(key)
        if len(deduped) >= max_items:
            break
    return deduped
