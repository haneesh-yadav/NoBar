"""
Scheme link helpers. NoBar documents are sourced from the Indian Government's
MyScheme portal (myscheme.gov.in), so the default "official site" link for a
scheme resolves to that scheme's page on MyScheme. The exact slug is not
always recoverable from the extracted PDF, so we link to the MyScheme search
for the scheme title — a live, functional page that lands on the official
portal. A more specific URL can always be set on the Document.scheme_url
column directly (e.g. https://www.myscheme.gov.in/schemes/<slug>).
"""

from __future__ import annotations

from urllib.parse import quote_plus

MYSCHEME_BASE = "https://www.myscheme.gov.in"


def myscheme_search_url(title: str) -> str:
    query = (title or "").strip()
    if not query:
        return ""
    return f"{MYSCHEME_BASE}/search?keyword={quote_plus(query)}"


def build_scheme_url(title: str, source_text: str = "", requested: str = "") -> str:
    """Pick the best official link for a scheme document.

    1. Explicit requested URL (user/admin provided) wins.
    2. Any myscheme.gov.in URL found verbatim in the source document.
    3. Fall back to a MyScheme search URL built from the scheme title.
    """
    if (requested or "").strip():
        return requested.strip()
    if source_text:
        import re

        match = re.search(r"https?://(?:www\.)?myscheme\.gov\.in/[A-Za-z0-9_/.-]+", source_text)
        if match:
            return match.group(0)
    return myscheme_search_url(title)