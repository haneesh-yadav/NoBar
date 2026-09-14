"""
Stage 1: Ingest. Extract raw text from an uploaded scheme document.

The gov_myscheme dataset is documented as mostly text-copyable PDFs, so
pdfplumber (fast, no model, no OCR) is the primary path. A page is only sent
to OCR if pdfplumber recovers almost no text from it — i.e. it's a scanned
image — so we don't pay the OCR cost on the common case.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pdfplumber
try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

from chains.text_cleaning import clean_myscheme_text

_MIN_CHARS_PER_PAGE_BEFORE_OCR = 20


@dataclass
class IngestResult:
    text: str
    raw_text: str
    title_hint: str | None
    page_count: int
    ocr_pages_used: list[int]
    warnings: list[str]


def ingest_pdf(path: str | Path) -> IngestResult:
    path = Path(path)
    warnings: list[str] = []
    ocr_pages: list[int] = []
    page_texts: list[str] = []

    with pdfplumber.open(str(path)) as pdf:
        page_count = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            text = (page.extract_text() or "").strip()
            if len(text) < _MIN_CHARS_PER_PAGE_BEFORE_OCR:
                ocr_text = _ocr_page(path, i)
                if ocr_text:
                    ocr_pages.append(i + 1)
                    text = ocr_text
                else:
                    warnings.append(f"page {i + 1}: no extractable text (pdfplumber or OCR)")
            page_texts.append(text)

    raw_text = "\n\n".join(page_texts).strip()
    if not raw_text:
        warnings.append("document produced no extractable text at all")

    cleaned_text, title_hint = clean_myscheme_text(raw_text)
    if not cleaned_text:
        # Cleaning heuristics found no match (not a myscheme-template doc,
        # or the doc was empty) — fall back to the raw extracted text so we
        # never throw away real content because a pattern didn't match.
        cleaned_text = raw_text

    return IngestResult(
        text=cleaned_text,
        raw_text=raw_text,
        title_hint=title_hint,
        page_count=page_count,
        ocr_pages_used=ocr_pages,
        warnings=warnings,
    )


def _ocr_page(pdf_path: Path, page_index: int) -> str:
    """OCR fallback for scanned pages. Rare path — only hit when pdfplumber
    finds almost no embedded text on a page."""
    if convert_from_path is None or pytesseract is None:
        return ""
    try:
        images = convert_from_path(
            str(pdf_path), first_page=page_index + 1, last_page=page_index + 1, dpi=200
        )
        if not images:
            return ""
        return pytesseract.image_to_string(images[0]).strip()
    except Exception:
        # OCR is a best-effort fallback; never let it crash the pipeline.
        return ""
