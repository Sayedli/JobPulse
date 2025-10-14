from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from applications.models import Application, JobPosting


@dataclass(slots=True)
class CoverLetterContext:
    applicant_name: str
    strengths: list[str]
    signature: str
    extra_notes: Optional[str] = None


def generate_cover_letter(
    job_posting: JobPosting, context: CoverLetterContext, *, tone: str = "enthusiastic"
) -> str:
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

    closing = (
        f"\n\nThank you for your time and consideration.\n\n{context.signature}"
    )

    if tone == "formal":
        intro = intro.replace("excited", "interested")

    body = intro + middle
    if context.extra_notes:
        body += f"\n\nAdditional context: {context.extra_notes}"
    return body + closing


def attach_cover_letter(application: Application, content: str) -> Application:
    application.cover_letter = content
    application.save(update_fields=["cover_letter"])
    return application
