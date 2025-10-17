from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Sequence

import markdown
import requests
from bs4 import BeautifulSoup

from django.utils import timezone

from applications.models import JobPosting, JobSource

logger = logging.getLogger(__name__)

SIMPLIFY_JOBS_README = (
    "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/master/README.md"
)


@dataclass(slots=True)
class ParsedJob:
    company: str
    title: str
    locations: str
    application_url: str
    posted: str | None = None
    notes: str | None = None
    tags: List[str] | None = None

    @property
    def external_id(self) -> str:
        slug_base = f"{self.company}-{self.title}"
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", slug_base.lower()).strip("-")
        digest = hashlib.sha1(self.application_url.encode("utf-8")).hexdigest()[:10]
        combined = f"{slug}-{digest}" if slug else digest
        return combined[:512]


def fetch_simplify_jobs_markdown(url: str = SIMPLIFY_JOBS_README) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def parse_simplify_jobs(markdown_text: str) -> Sequence[ParsedJob]:
    html = markdown.markdown(markdown_text, extensions=["tables"])
    soup = BeautifulSoup(html, "html.parser")

    target_headers = [
        h
        for h in soup.find_all(re.compile("^h[1-4]$"))
        if "software engineering" in h.get_text(strip=True).lower()
        and "new grad" in h.get_text(strip=True).lower()
    ]
    if not target_headers:
        logger.warning("Simplify Jobs README format changed; header not found.")
        return []

    table = target_headers[0].find_next("table")
    if table is None:
        logger.warning("Simplify Jobs README format changed; table not found.")
        return []

    jobs: list[ParsedJob] = []
    rows = table.find_all("tr")
    for row in rows[1:]:  # skip header row
        cells = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
        if len(cells) < 4:
            continue
        link = row.find("a")
        application_url = link["href"].strip() if link and link.has_attr("href") else ""
        note_text = cells[5] if len(cells) > 5 else None
        posted = cells[4] if len(cells) > 4 else None
        jobs.append(
            ParsedJob(
                company=cells[0],
                title=cells[1],
                locations=cells[2],
                application_url=application_url,
                posted=posted,
                notes=note_text,
            )
        )
    return jobs


def upsert_jobs(source: JobSource, parsed_jobs: Iterable[ParsedJob]) -> tuple[int, int]:
    created = 0
    updated = 0

    for job in parsed_jobs:
        is_remote = "remote" in (job.locations or "").lower()
        defaults = {
            "title": job.title,
            "company": job.company,
            "locations": job.locations,
            "application_url": job.application_url,
            "description": job.notes or "",
            "tags": job.tags or [],
            "last_seen_at": timezone.now(),
            "is_active": True,
            "is_remote": is_remote,
        }
        posting, was_created = JobPosting.objects.update_or_create(
            source=source,
            external_id=job.external_id,
            defaults=defaults,
        )
        if job.posted:
            posting.description = defaults["description"]
            try:
                posting.posted_at = _parse_date(job.posted)
            except ValueError:
                logger.debug("Could not parse posted date '%s'", job.posted)
        posting.save()

        if was_created:
            created += 1
        else:
            updated += 1

    return created, updated


def sync_simplify_jobs(
    source_slug: str = "simplify-jobs", markdown_url: str | None = None
) -> tuple[int, int]:
    source, _ = JobSource.objects.get_or_create(
        slug=source_slug,
        defaults={
            "name": "Simplify Jobs – New Grad",
            "description": "Parsed from SimplifyJobs/New-Grad-Positions README",
            "homepage_url": "https://github.com/SimplifyJobs/New-Grad-Positions",
        },
    )

    markdown_text = fetch_simplify_jobs_markdown(url=markdown_url or SIMPLIFY_JOBS_README)
    parsed_jobs = parse_simplify_jobs(markdown_text)
    created, updated = upsert_jobs(source, parsed_jobs)

    source.last_synced_at = timezone.now()
    source.save(update_fields=["last_synced_at"])
    logger.info(
        "Synchronised Simplify Jobs feed. created=%s updated=%s slug=%s",
        created,
        updated,
        source.slug,
    )
    return created, updated


def _parse_date(date_text: str | None):
    if not date_text:
        raise ValueError("Empty date")
    normalized = date_text.strip()
    # Common formats used in Simplify README (e.g., 2024-09-01, Sept 1)
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%b %d", "%b %d %Y"):
        try:
            dt = datetime.strptime(normalized, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=datetime.utcnow().year)
            return dt.date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {date_text}")
