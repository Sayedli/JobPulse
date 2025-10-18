from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import IO, Iterable
import unicodedata
import textwrap

from django.conf import settings
from django.utils.text import slugify

from PyPDF2 import PdfReader
from fpdf import FPDF


FONT_DIR = Path(settings.BASE_DIR) / "static" / "fonts"
FONT_REGULAR = FONT_DIR / "DejaVuSans.ttf"
FONT_BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"


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
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    font_family = _resolve_font(pdf)
    pdf.set_font(font_family, size=12)

    if title:
        safe_title = _coerce_ascii(title)
        pdf.set_title(safe_title)
        pdf.set_font(font_family, "B", 18)
        pdf.multi_cell(0, 12, safe_title.upper())
        pdf.ln(4)
        pdf.set_font(font_family, size=12)

    for raw_line in lines:
        wrapped_segments = _wrap_for_pdf(raw_line)
        for segment in wrapped_segments:
            pdf.multi_cell(0, 8, segment if segment else " ")

    pdf.output(str(destination))
    return destination


def _coerce_ascii(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    replacements = {
        "–": "-",
        "—": "-",
        "•": "-",
        "·": "-",
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "′": "'",
        "″": '"',
    }
    converted: list[str] = []
    for ch in normalized:
        if ord(ch) < 128:
            converted.append(ch)
        else:
            converted.append(replacements.get(ch, " "))
    ascii_text = "".join(converted)
    ascii_text = re.sub(r"\s+", " ", ascii_text).strip()
    if not ascii_text:
        return normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text


def _resolve_font(pdf: FPDF) -> str:
    try:
        if FONT_REGULAR.exists():
            if "DejaVu" not in pdf.fonts:
                pdf.add_font("DejaVu", "", str(FONT_REGULAR), uni=True)
            if FONT_BOLD.exists() and "DejaVuB" not in pdf.fonts:
                pdf.add_font("DejaVu", "B", str(FONT_BOLD), uni=True)
            return "DejaVu"
    except Exception:
        pass
    return "Helvetica"


def _wrap_for_pdf(text: str, width: int = 95) -> list[str]:
    sanitized = _coerce_ascii(text)
    if not sanitized:
        return [""]
    max_width = max(10, width)
    lines: list[str] = []
    words = sanitized.split()

    current: list[str] = []
    current_len = 0

    def flush_current():
        nonlocal current, current_len
        if current:
            lines.append(" ".join(current))
            current = []
            current_len = 0

    for word in words:
        if len(word) >= max_width:
            flush_current()
            for chunk in _chunk_word(word, max_width - 1):
                lines.append(chunk)
            continue
        prospective = current_len + len(word) + (1 if current else 0)
        if prospective > max_width:
            flush_current()
        current.append(word)
        current_len = sum(len(w) for w in current) + max(0, len(current) - 1)

    flush_current()
    return lines or [sanitized]


def _chunk_word(word: str, chunk_size: int) -> list[str]:
    size = max(1, chunk_size)
    return [word[i : i + size] for i in range(0, len(word), size)]
