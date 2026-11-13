"""Read and normalize source data. TODO: implement functions."""
from pathlib import Path
import re
import unicodedata

from pypdf import PdfReader

from .models import DocumentPage


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """TODO: extract each physical page; keep its page number and source.

    Detect and record pages with no text. OCR, when needed, is a separate step.
    """

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    reader = PdfReader(str(path))

    pages: list[DocumentPage] = []

    for page_number, pdf_page in enumerate(reader.pages, start=1):
        raw_text = pdf_page.extract_text() or ""
        normalized = normalize_text(raw_text)

        cleaned = clean_page_artifacts(normalized)

        page = DocumentPage(
            document_id=document_id,
            source=source,
            page=page_number,
            text=cleaned,
            metadata={
                "has_text": bool(cleaned),
                "extraction_status": (
                "success" if cleaned else "empty"
            ),
            },
        )

        pages.append(page)

    return pages


def normalize_text(text: str) -> str:
    """TODO: normalize Unicode and whitespace without discarding useful structure."""
    if not text:
        return ""

    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")  
    text = text.replace("\u00A0", " ")  
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t\f\v]+", " ", line)
        lines.append(line.strip())
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
def clean_page_artifacts(text: str) -> str:
    """Remove known page numbers and running headers/footers."""

    cleaned_lines = []

    for line in text.splitlines():
        stripped = line.strip()

        if not stripped:
            cleaned_lines.append("")
            continue

        # Remove standalone printed page numbers.
        if re.fullmatch(r"\d{1,3}", stripped):
            continue

        # Remove known running headers and footers.
        if re.fullmatch(
            r"DATA MANAGEMENT\s+\d{1,3}",
            stripped,
            flags=re.IGNORECASE,
        ):
            continue

        if re.fullmatch(
            r"\d{1,3}\s+ROY WOOD",
            stripped,
            flags=re.IGNORECASE,
        ):
            continue

        if re.fullmatch(
            r"INTRODUCTION TO IS\s+\d{1,3}",
            stripped,
            flags=re.IGNORECASE,
        ):
            continue

        cleaned_lines.append(stripped)

    cleaned_text = "\n".join(cleaned_lines)

    # Remove excessive blank lines.
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)

    return cleaned_text.strip()