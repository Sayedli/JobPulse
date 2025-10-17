from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import IO, Iterable
import unicodedata

from django.conf import settings
from django.utils.text import slugify

from PyPDF2 import PdfReader
from fpdf import FPDF


class PdfProcessingError(Exception):
    """Raised when we fail to parse or persist a resume PDF."""


def save_uploaded_pdf(user, uploaded_file) -> Path:
    """
    Persist the uploaded PDF under generated/resumes/<user_id>/source/.
    Returns the path on disk.
    """
    user_folder = Path(settings.BASE_DIR) / "generated" / "resumes" / str(user.id) / "source"
    user_folder.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    original_name = uploaded_file.name or "resume.pdf"
    stem = slugify(Path(original_name).stem) or "resume"
    filename = f"{timestamp}_{stem}.pdf"
    destination = user_folder / filename

    with destination.open("wb") as output:
        for chunk in uploaded_file.chunks():
            output.write(chunk)

    uploaded_file.seek(0)
    return destination


def extract_text_from_pdf(uploaded_file: IO[bytes]) -> str:
    """
    Extract plain text from the uploaded PDF using PyPDF2.
    """
    try:
        uploaded_file.seek(0)
        reader = PdfReader(uploaded_file)
    except Exception as exc:  # pragma: no cover - PyPDF2 specific
        raise PdfProcessingError("Unable to read PDF file.") from exc

    text_parts = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # pragma: no cover - PyPDF2 specific
            raise PdfProcessingError("Failed to extract text from PDF page.") from exc
        text_parts.append(text)

    uploaded_file.seek(0)
    extracted = "\n".join(text_parts)
    extracted = re.sub(r"\n{3,}", "\n\n", extracted).strip()
    if not extracted:
        raise PdfProcessingError("The uploaded PDF appears to contain no extractable text.")
    return extracted


def write_text_pdf(
    destination: Path,
    lines: Iterable[str],
    *,
    title: str | None = None,
) -> Path:
    """
    Render text content to a simple PDF at the given destination.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    font_family = "Helvetica"
    pdf.set_font(font_family, size=12)

    if title:
        safe_title = _coerce_ascii(title)
        pdf.set_title(safe_title)
        pdf.set_font(font_family, "B", 14)
        pdf.multi_cell(0, 10, safe_title)
        pdf.ln(4)
        pdf.set_font(font_family, size=12)

    for raw_line in lines:
        line = _coerce_ascii(raw_line)
        pdf.multi_cell(0, 8, line if line else " ")

    pdf.output(str(destination))
    return destination
def _coerce_ascii(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    stripped = normalized.encode("ascii", "ignore").decode("ascii")
    return stripped if stripped else text.replace("–", "-")
