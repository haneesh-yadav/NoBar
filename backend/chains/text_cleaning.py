"""
The myscheme.gov.in corpus (Dataset/data/gov_myscheme) is a browser "print to
PDF" export of a single-page React app, so every document carries identical
UI chrome baked into the extracted text: sign-out modals, tab labels
concatenated with no whitespace, and a government-portal footer. Left in,
this junk burns tokens and confuses small local models trying to extract
facts. This module strips it deterministically, before any model ever sees
the text.

This is intentionally narrow and defensive: every removal is anchored on an
exact, observed phrase from this specific site template. If a document
doesn't match the pattern (e.g. it's not from myscheme.gov.in), the relevant
step is a no-op and the original text passes through unchanged — we never
guess-strip content we're not sure is boilerplate.
"""

from __future__ import annotations

import re

import ftfy

_HEADER_BLOCK = re.compile(
    r"Are you sure you want to sign out\?.*?Check Eligibility",
    re.DOTALL | re.IGNORECASE,
)

_FOOTER_MARKERS = [
    "Was this helpful?",
    "News and\nUpdates",
    "News and Updates",
]

_MOJIBAKE_FIXES = {
    "ï»¿": "",
    "Â©": "©",
}

# ftfy handles clean single-pass mojibake, but a few PDFs in this corpus have
# lossy font-encoding artifacts around curly quotes that no decode round-trip
# can recover (the original byte is gone, not just misdecoded). These never
# touch numbers/dates, only cosmetic punctuation, so a blunt cleanup is safe:
# we care about fact fidelity, not typographic perfection.
_RESIDUAL_ARTIFACTS = re.compile(r"â€[\u200b\u200c\u200d]?")
_ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff]")


def clean_myscheme_text(raw_text: str) -> tuple[str, str | None]:
    """Returns (cleaned_body, title_hint).

    title_hint is the scheme title as it appears before the sign-out modal
    junk (e.g. "Old Age Pension Scheme"), which is more reliable than asking
    the LLM to re-derive it from a noisy body.
    """
    if not raw_text:
        return raw_text, None

    text = ftfy.fix_text(raw_text)
    for bad, good in _MOJIBAKE_FIXES.items():
        text = text.replace(bad, good)
    text = _RESIDUAL_ARTIFACTS.sub('"', text)
    text = _ZERO_WIDTH.sub("", text)

    title_hint: str | None = None
    header_match = _HEADER_BLOCK.search(text)
    if header_match:
        title_hint = text[: header_match.start()].strip() or None
        text = text[header_match.end():]

    # Drop the tag/state salad between the header block and the first real
    # content marker. On this template, real prose always starts right after
    # a "Details" section marker — but because this is a print of a React
    # app with no whitespace between concatenated tab/tag labels (e.g.
    # "...WelfareDetailsDetailsChief Minister..."), `Details` is NOT a
    # standalone word here, so a \b-anchored regex never matches. Use a
    # literal substring search instead, and consume any repeated adjacent
    # "Details" tokens (observed to appear back-to-back in some documents).
    idx = text.find("Details")
    if 0 <= idx < 200:
        cursor = idx
        while text[cursor:cursor + len("Details")] == "Details":
            cursor += len("Details")
        text = text[cursor:]

    for marker in _FOOTER_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
            break

    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip(), title_hint
