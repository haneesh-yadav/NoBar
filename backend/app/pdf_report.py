"""
Generates the user's personal "Entitlement & Profile Report" PDF.

This PDF contains every user detail NoBar has access to once the citizen signs
in — demographic/profile fields plus which verified schemes they match, have
saved, or have applied to — and is the deliverable a citizen can carry to a
CSC (Common Service Centre) or human helper.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)  # noqa: F401  # (kept for forward-compat typing; user passed as dict)

_NAVY = colors.HexColor("#1e3a8a")
_SLATE = colors.HexColor("#334155")
_LIGHT = colors.HexColor("#e2e8f0")


def _clean(value: Any) -> str:
    """Cast to a latin-1-safe string so reportlab never hits an unsupported glyph."""
    text = "" if value is None else str(value)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _maybe(pairs: list[tuple[str, Any]]) -> str:
    return _clean(pairs[0][1]) if pairs and (pairs[0][1] != "" and pairs[0][1] is not None) else "—"


def build_user_report_pdf(
    user: dict,
    *,
    matched: list[dict],
    saved: list[dict],
    applications: list[dict],
) -> bytes:
    """user: plain dict of profile fields (see users._user_dict output)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="NoBar Entitlement & Profile Report",
        author="NoBar",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleX", parent=styles["Title"], fontSize=17, textColor=_NAVY, spaceAfter=2, alignment=TA_CENTER
    )
    subtitle_style = ParagraphStyle(
        "SubtitleX", parent=styles["Normal"], fontSize=9, textColor=_SLATE, alignment=TA_CENTER, spaceAfter=10
    )
    h2 = ParagraphStyle("H2X", parent=styles["Heading2"], fontSize=12, textColor=_NAVY, spaceAfter=6)
    body = ParagraphStyle("BodyX", parent=styles["Normal"], fontSize=9.5, leading=13, spaceAfter=4)

    story = [
        Paragraph("NoBar — Entitlement & Profile Report", title_style),
        Paragraph(
            _clean(f"Generated for {user["full_name"] or user["email"]} on {datetime.now().strftime('%d %b %Y, %H:%M')}"),
            subtitle_style,
        ),
        Spacer(1, 6),
    ]

    # --- 1. Personal details ---
    story.append(Paragraph("1. Your Profile Details", h2))
    rows = [
        ["Full name", _maybe([("", user["full_name"])])],
        ["Email (login ID)", _clean(user["email"])],
        ["Date of birth", _maybe([("", user["dob"])])],
        ["Gender", _maybe([("", user["gender"])])],
        ["Marital status", _maybe([("", user["marital_status"])])],
        ["Disability status", _maybe([("", user["disability_status"])]).capitalize()],
        ["Disability type", _maybe([("", user["disability_type"])])],
        ["Caste category", _maybe([("", user["caste_category"])])],
        ["BPL / Below Poverty Line", _maybe([("", user["bpl_status"])]).capitalize()],
        [
            "Annual income (INR)",
            (_clean(f"INR {user['annual_income']:,.0f}") if user["annual_income"] is not None else "—"),
        ],
        ["Employment type", _maybe([("", user["employment_type"])])],
        ["State", _maybe([("", user["state"])])],
        ["District", _maybe([("", user["district"])])],
        ["Pincode", _maybe([("", user["pincode"])])],
        ["Aadhaar (masked)", _maybe([("", user["aadhaar_masked"])])],
    ]
    table = Table(rows, colWidths=[55 * mm, 115 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), _LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94a3b8")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 12))

    # --- 2. Eligibility snapshot ---
    story.append(Paragraph("2. Eligibility Snapshot", h2))
    snapshot = []
    if user["disability_status"] == "yes":
        snapshot.append(
            f"• Recognised as a person with disability ({_clean(user['disability_type'] or 'unspecified')})."
        )
    if user["bpl_status"] not in ("", "no"):
        snapshot.append("• BPL certificate holder — applicable for poverty-linked schemes.")
    if user["annual_income"] is not None:
        snapshot.append(f"• Reports annual income of INR {user['annual_income']:,.0f}.")
    if user["caste_category"]:
        snapshot.append(f"• Belongs to social category: {_clean(user['caste_category'])}.")
    if user["state"]:
        snapshot.append(
            f"• Resident of {_clean(user['state'])} ({_clean(user['district'] or 'district not set')})."
        )
    story.extend(
        [Paragraph(text, body) for text in snapshot]
        or [Paragraph("No demographic markers set — update your profile for tailored matching.", body)]
    )
    story.append(Spacer(1, 12))

    # --- 3. Matched schemes ---
    story.append(Paragraph(f"3. Schemes You Match ({len(matched)})", h2))
    if not matched:
        story.append(Paragraph("No verified scheme matched from the current profile yet.", body))
    for item in matched:
        link = _clean(item.get("scheme_url") or "")
        title = _clean(item.get("title") or "Scheme")
        summary = _clean(item.get("summary") or "")
        reasons = "; ".join(_clean(r) for r in item.get("reasons") or [])
        text = f"<b>{title}</b> — {summary}"
        if link:
            text += f" <link href='{link}'>[Official site: myscheme.gov.in]</link>"
        story.append(Paragraph(text, body))
        if reasons:
            story.append(Paragraph(f"<i>Why: {reasons}</i>", body))
    story.append(Spacer(1, 10))

    # --- 4. Saved schemes ---
    story.append(Paragraph(f"4. Saved Schemes ({len(saved)})", h2))
    if not saved:
        story.append(Paragraph("No schemes saved yet.", body))
    for item in saved:
        story.append(Paragraph(
            f"• <b>{_clean(item.get('title') or 'Scheme')}</b> — {_clean(item.get('category') or 'general')}",
            body,
        ))
    story.append(Spacer(1, 10))

    # --- 5. Applications ---
    story.append(Paragraph(f"5. My Applications ({len(applications)})", h2))
    if not applications:
        story.append(Paragraph("No scheme applications recorded yet.", body))
    for item in applications:
        story.append(Paragraph(
            f"• <b>{_clean(item.get('title') or 'Scheme')}</b> — status: {_clean(item.get('status') or 'submitted').upper()} ({_clean(item.get('applied_at') or '')})",
            body,
        ))

    story.append(Spacer(1, 16))
    story.append(
        Paragraph(
            "<i>This report is generated automatically by NoBar from your login profile and the "
            "verified scheme library. Eligibility shown is a conservative hint from the extracted "
            "fact ledger — always confirm the latest criteria and apply on the official portal "
            "(myscheme.gov.in) before relying on it.</i>",
            ParagraphStyle("Footnote", parent=body, fontSize=8, textColor=colors.HexColor("#64748b")),
        )
    )

    doc.build(story)
    return buffer.getvalue()