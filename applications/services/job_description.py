from __future__ import annotations

import logging
import re
from datetime import timedelta

import requests
from bs4 import BeautifulSoup
from django.utils import timezone

from applications.models import JobDescriptionSnapshot, JobPosting

logger = logging.getLogger(__name__)


FETCH_TIMEOUT = 15
MAX_TEXT_LENGTH = 4000
RECENT_WINDOW = timedelta(days=7)


def get_description(job_posting: JobPosting, *, refresh: bool = False) -> str:
    snapshot = getattr(job_posting, "description_snapshot", None)
    if snapshot and not refresh:
        if snapshot.fetched_at and snapshot.fetched_at >= timezone.now() - RECENT_WINDOW:
            return snapshot.extracted_text

    extracted = _fetch_remote_description(job_posting)
    if not extracted:
        extracted = job_posting.description or "Description unavailable."

    snapshot, _ = JobDescriptionSnapshot.objects.update_or_create(
        job_posting=job_posting,
        defaults={
            "extracted_text": extracted[:MAX_TEXT_LENGTH],
            "source_url": job_posting.application_url,
            "fetched_at": timezone.now(),
        },
    )
    return snapshot.extracted_text


def _fetch_remote_description(job_posting: JobPosting) -> str:
    if not job_posting.application_url:
        return job_posting.description or ""

    try:
        response = requests.get(job_posting.application_url, timeout=FETCH_TIMEOUT)
        response.raise_for_status()
    except Exception:
        logger.warning("Failed to fetch job description for %s", job_posting, exc_info=True)
        return job_posting.description or ""

    soup = BeautifulSoup(response.text, "html.parser")

    for selector in ("article", "section", "main", "div.job-description", "div.description"):
        node = soup.select_one(selector)
        if node and len(_text_content(node)) > 120:
            return _clean_text(_text_content(node))

    paragraphs = soup.find_all("p")
    body_text = _clean_text("\n".join(_text_content(p) for p in paragraphs))
    if len(body_text) > 120:
        return body_text
    return job_posting.description or ""


def _text_content(element) -> str:
    text = element.get_text(separator=" ", strip=True)
    return text or ""


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"(?<=\.)\s+", " ", text)
    return text.strip()
