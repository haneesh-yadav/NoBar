"""
Stage 3: Simplification. Rewrites the source document into plain language,
grounded explicitly in the FactLedger so the model is reminded exactly which
facts it must not drop while rewriting.

Readability is checked with textstat (Flesch-Kincaid grade level) as a
cheap, deterministic signal — separate from, and in addition to, the Fact
Fidelity verification layer, which checks content correctness rather than
reading difficulty.
"""

from __future__ import annotations

try:
    import textstat
except Exception:
    textstat = None

from chains.llm_provider import traced_generator_llm
from schemas.fact_ledger import FactLedger

TARGET_GRADE_LEVEL = 7  # roughly a plain-language / newspaper reading level


def _safe_reading_grade(text: str) -> float:
    """textstat's syllable counter raises KeyError on words absent from its
    CMU dictionary — proper nouns like "Uttarakhand" reliably trigger this.
    Readability is a secondary signal to the Fact Fidelity Score, not the
    thing gating publish, so a scoring hiccup should degrade to "unknown"
    rather than crash the whole pipeline."""
    if not text:
        return 99.0
    try:
        return textstat.flesch_kincaid_grade(text)
    except (KeyError, Exception):
        return -1.0  # sentinel: readability unavailable, not "text is unreadable"

_SIMPLIFICATION_PROMPT_TEMPLATE = """Rewrite this Indian government welfare scheme description in plain, \
simple language that anyone can understand — aim for around a {grade}th-grade reading level. Short sentences. \
No legal or bureaucratic jargon. Explain any term a normal person might not know.

CRITICAL: every single fact below MUST appear somewhere in your rewrite, with the same numbers, amounts, and \
dates — do not round, drop, or change any of them, even if it makes a sentence longer:

{facts_block}

Write the plain-language version now. Structure it with these sections, in this order, using clear headings: \
"Who can apply", "What you get", "Documents needed", "How to apply". Do not include a "Sources" or "FAQ" \
section unless there is a genuine deadline to mention.

Original document (for context and any wording you should preserve, e.g. the exact scheme name):
{document}
"""


def _facts_block(ledger: FactLedger) -> str:
    lines: list[str] = []
    for e in ledger.eligibility:
        lines.append(f"- Eligibility: {e.condition_type} {e.operator} {e.value} {e.unit or ''}".strip())
    for t in ledger.numeric_thresholds:
        lines.append(f"- Number: {t.raw_text} ({t.context})")
    for d in ledger.deadlines:
        lines.append(f"- Deadline: {d.date_or_period} — {d.description}")
    for b in ledger.benefits:
        freq = f", {b.frequency}" if b.frequency else ""
        lines.append(f"- Benefit: {b.amount_or_description}{freq}")
    if ledger.required_documents:
        lines.append(f"- Required documents: {', '.join(ledger.required_documents)}")
    return "\n".join(lines) if lines else "(no structured facts extracted — rewrite faithfully from the document text)"


def simplify_document(
    document_text: str,
    ledger: FactLedger,
    *,
    session_id: str,
    target_grade: int = TARGET_GRADE_LEVEL,
) -> tuple[str, float]:
    """Returns (simplified_text, flesch_kincaid_grade)."""
    prompt = _SIMPLIFICATION_PROMPT_TEMPLATE.format(
        grade=target_grade,
        facts_block=_facts_block(ledger),
        document=document_text,
    )
    with traced_generator_llm(
        agent_name="simplifier", session_id=session_id, temperature=0.3, num_predict=1800
    ) as llm:
        resp = llm.invoke(prompt)

    simplified_text = resp.content.strip()
    grade = _safe_reading_grade(simplified_text)
    return simplified_text, grade


def retry_with_corrective_feedback(
    document_text: str,
    ledger: FactLedger,
    previous_attempt: str,
    missing_facts: list[str],
    *,
    session_id: str,
    target_grade: int = TARGET_GRADE_LEVEL,
) -> tuple[str, float]:
    """Used by the verification layer's retry loop: tells the model exactly
    which facts it dropped last time, rather than starting from scratch."""
    missing_block = "\n".join(f"- {m}" for m in missing_facts)
    prompt = (
        _SIMPLIFICATION_PROMPT_TEMPLATE.format(
            grade=target_grade, facts_block=_facts_block(ledger), document=document_text
        )
        + f"""

Your previous attempt was missing these facts — make sure ALL of them appear this time, with exact numbers:
{missing_block}

Your previous attempt:
{previous_attempt}
"""
    )
    with traced_generator_llm(
        agent_name="simplifier-retry", session_id=session_id, temperature=0.2, num_predict=1800
    ) as llm:
        resp = llm.invoke(prompt)

    simplified_text = resp.content.strip()
    grade = _safe_reading_grade(simplified_text)
    return simplified_text, grade
