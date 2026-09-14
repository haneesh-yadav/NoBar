"""
Stage: WCAG formatting + automated audit. Turns the plain-language text into
a semantic, accessible HTML document, then actually checks it with axe-core
(via a jsdom-based Node tool — see backend/wcag_tool/) rather than assuming
"semantic HTML" is automatically compliant.
"""

from __future__ import annotations

import html as html_escape
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

_WCAG_TOOL_DIR = Path(__file__).resolve().parent.parent / "wcag_tool"
_KNOWN_SECTION_HEADINGS = [
    "Who can apply",
    "What you get",
    "Documents needed",
    "How to apply",
]


@dataclass
class WcagAuditResult:
    violations: list[dict]
    violations_count: int
    serious_or_critical_count: int
    passes_count: int
    skipped_checks: list[str]
    ran_successfully: bool
    error: str | None = None


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """Splits the model's plain-language output into (heading, body) pairs
    using the known section headings we asked the simplifier to use. Falls
    back to a single unnamed section if none of the expected headings are
    found, so formatting never throws away content."""
    pattern = "|".join(re.escape(h) for h in _KNOWN_SECTION_HEADINGS)
    matches = list(re.finditer(rf"(?:^|\n)\s*({pattern})\s*:?\s*\n", text))
    if not matches:
        return [("Details", text.strip())]

    sections: list[tuple[str, str]] = []
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append(("Overview", preamble))

    for i, m in enumerate(matches):
        heading = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append((heading, body))

    return sections


def _body_to_html(body: str) -> str:
    """Renders a section body as a <p> per paragraph, or a <ul> if every
    non-empty line looks like a list item (bullet, dash, or numbered)."""
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    if not lines:
        return ""

    bullet_pattern = re.compile(r"^(?:[-*•]|\d+[\.\)])\s+")
    if len(lines) > 1 and all(bullet_pattern.match(ln) for ln in lines):
        items = "".join(
            f"<li>{html_escape.escape(bullet_pattern.sub('', ln))}</li>" for ln in lines
        )
        return f"<ul>{items}</ul>"

    return "".join(f"<p>{html_escape.escape(ln)}</p>" for ln in lines)


def simplified_text_to_html(
    *,
    title: str,
    simplified_text: str,
    lang: str = "en",
    fidelity_score: float | None = None,
) -> str:
    sections = _split_into_sections(simplified_text)
    escaped_title = html_escape.escape(title)

    nav_items = "".join(
        f'<li><a href="#section-{i}">{html_escape.escape(h)}</a></li>'
        for i, (h, _) in enumerate(sections)
    )
    section_html = "".join(
        f'<section id="section-{i}" aria-labelledby="heading-{i}">'
        f'<h2 id="heading-{i}">{html_escape.escape(h)}</h2>'
        f"{_body_to_html(b)}"
        f"</section>"
        for i, (h, b) in enumerate(sections)
    )

    trust_banner = ""
    if fidelity_score is not None:
        trust_banner = (
            f'<p class="trust-report" role="status">Fact fidelity checked: '
            f"{fidelity_score:.0f}%.</p>"
        )

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escaped_title} — Plain Language Version</title>
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to main content</a>
  <header>
    <h1>{escaped_title}</h1>
    {trust_banner}
  </header>
  <nav aria-label="Table of contents">
    <ul>{nav_items}</ul>
  </nav>
  <main id="main-content">
    {section_html}
  </main>
</body>
</html>"""


def run_axe_audit(html_document: str) -> WcagAuditResult:
    script = _WCAG_TOOL_DIR / "audit.js"
    if not script.exists():
        return WcagAuditResult([], 0, 0, 0, [], False, error=f"audit tool not found at {script}")

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html_document)
        tmp_path = f.name

    try:
        proc = subprocess.run(
            ["node", str(script), tmp_path],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_WCAG_TOOL_DIR),
        )
        if proc.returncode != 0:
            return WcagAuditResult([], 0, 0, 0, [], False, error=proc.stderr.strip()[:2000])
        data = json.loads(proc.stdout)
        return WcagAuditResult(
            violations=data.get("violations", []),
            violations_count=data.get("violations_count", 0),
            serious_or_critical_count=data.get("serious_or_critical_count", 0),
            passes_count=data.get("passes_count", 0),
            skipped_checks=data.get("skipped_checks", []),
            ran_successfully=True,
        )
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return WcagAuditResult([], 0, 0, 0, [], False, error=str(exc))
    finally:
        Path(tmp_path).unlink(missing_ok=True)
