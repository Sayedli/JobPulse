from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from django.conf import settings

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency fallback
    OpenAI = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LLMResult:
    content: str
    model: str
    provider: str


def is_llm_configured() -> bool:
    if settings.LLM_PROVIDER == "openai":
        return bool(settings.OPENAI_API_KEY) and OpenAI is not None
    logger.warning("Unsupported LLM provider configured: %s", settings.LLM_PROVIDER)
    return False


def _client() -> Optional[OpenAI]:
    if settings.LLM_PROVIDER == "openai":
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set; falling back to template output.")
            return None
        if OpenAI is None:
            logger.warning("openai package not installed; falling back to template output.")
            return None
        return OpenAI(api_key=settings.OPENAI_API_KEY)
    logger.warning("LLM provider %s not implemented.", settings.LLM_PROVIDER)
    return None


def generate_tailored_resume_summary(
    job_title: str, company: str, description: str, base_resume_highlights: str
) -> Optional[LLMResult]:
    client = _client()
    if client is None:
        return None

    prompt = (
        "You are an assistant that rewrites resume summaries to align with a specific job. "
        "Produce a concise bullet list (3-5 bullets) emphasising achievements.\n\n"
        f"Job Title: {job_title}\nCompany: {company}\nDescription: {description[:500]}\n"
        f"Resume Highlights:\n{base_resume_highlights[:800]}\n\n"
        "Return markdown bullet points only."
    )

    try:
        response = client.responses.create(
            model=settings.LLM_MODEL,
            input=prompt,
            temperature=0.4,
        )
    except Exception:  # pragma: no cover - API failure fallback
        logger.exception("LLM resume call failed; falling back to template output.")
        return None

    content = _extract_text(response)
    if not content:
        return None
    return LLMResult(content=content, model=settings.LLM_MODEL, provider=settings.LLM_PROVIDER)


def generate_cover_letter(
    job_title: str,
    company: str,
    strengths: list[str],
    tone: str,
    base_signature: str,
    extra_notes: Optional[str] = None,
) -> Optional[LLMResult]:
    client = _client()
    if client is None:
        return None

    prompt = (
        "Craft a personalised cover letter (approx 3 paragraphs) tailored to the role below. "
        "Keep the tone professional and aligned with the requested tone.\n\n"
        f"Job Title: {job_title}\nCompany: {company}\nStrengths: {', '.join(strengths)}\n"
        f"Preferred Tone: {tone}\nSignature: {base_signature}\n"
    )
    if extra_notes:
        prompt += f"Additional Notes: {extra_notes}\n"

    try:
        response = client.responses.create(
            model=settings.LLM_MODEL,
            input=prompt,
            temperature=0.6,
        )
    except Exception:  # pragma: no cover
        logger.exception("LLM cover letter generation failed.")
        return None

    content = _extract_text(response)
    if not content:
        return None
    return LLMResult(content=content, model=settings.LLM_MODEL, provider=settings.LLM_PROVIDER)


def _extract_text(response) -> str:
    """
    Handles the structured output format returned by openai>=1.0 responses API.
    """
    if not getattr(response, "output", None):
        return ""

    chunks = []
    for item in response.output:
        if getattr(item, "content", None):
            for block in item.content:
                if block.type == "output_text":
                    chunks.append(block.text)
    return "\n".join(chunks).strip()
