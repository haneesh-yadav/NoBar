"""
Stage 2: Fact Extraction. Turns raw (cleaned) document text into a structured
FactLedger — the object every later stage must be verified against.

Decomposed into two focused JSON-mode calls rather than one large tool-call
against a deeply nested schema: on the small local models this hardware
budget affords (3B params), a single call attempting to fill the whole
nested FactLedger reliably produced empty lists instead of failing loudly —
the model couldn't reason its way through the full schema at once. Two
narrower calls, each asked for a flat, example-shown JSON shape, are both
faster per-call and dramatically more reliable in practice (see
backend/tests/test_extraction.py).
"""

from __future__ import annotations

import logging
import time

from chains.json_utils import JSONParseError, parse_llm_json
from chains.llm_provider import traced_generator_llm
from chains.numeric_utils import fact_survives
from prism.client import trace_manual_step
from schemas.fact_ledger import (
    Benefit,
    Deadline,
    EligibilityCriterion,
    FactLedger,
    NumericThreshold,
)

logger = logging.getLogger("nobar.extraction")

_ELIGIBILITY_PROMPT_TEMPLATE = """Extract every eligibility criterion and numeric threshold from this Indian \
government welfare scheme document. Look specifically for: age limits, income limits (monthly or annual), \
land holding limits, caste/category requirements, occupation requirements, gender/marital status requirements, \
disability requirements, and residency requirements. Extract EVERY number you find that gates who can apply — \
do not stop after the first one; documents often list several income thresholds (e.g. one for the FAQ, a \
different one in the main eligibility section) and BOTH must be captured even if they seem to conflict.

Return ONLY valid JSON, no other text, matching exactly this shape:
{{
  "eligibility": [
    {{"condition_type": "age", "operator": ">=", "value": "60", "unit": "years", "source_span": "verbatim quote"}}
  ],
  "numeric_thresholds": [
    {{"raw_text": "Rs.4000", "normalized_value": 4000, "unit": "INR/month", "context": "what this number gates"}}
  ]
}}

If nothing applies to a list, return an empty list for it — never invent a fact not in the text.

Scheme title: {title}

Document:
{document}
"""

_REST_PROMPT_TEMPLATE = """Extract deadlines, benefits, required documents, and application steps from this \
Indian government welfare scheme document. Also write a one-sentence, jargon-free summary a person with no \
policy background could understand.

Return ONLY valid JSON, no other text, matching exactly this shape:
{{
  "scheme_name": "Old Age Pension Scheme",
  "summary": "one plain-language sentence",
  "deadlines": [
    {{"date_or_period": "31 March 2026", "description": "what happens by this date"}}
  ],
  "benefits": [
    {{"amount_or_description": "Rs 1500 per month", "frequency": "monthly"}}
  ],
  "required_documents": ["Aadhar Card", "Income Certificate"],
  "application_steps": ["Go to the official website", "Fill the form"]
}}

If nothing applies to a list, return an empty list for it — never invent a fact not in the text.

Scheme title: {title}

Document:
{document}
"""


def _validate_each(model_cls, items, field_name: str):
    """Small local models occasionally emit a list item with a null/missing
    required field instead of omitting the item entirely. One bad item
    should never take down the whole extraction — skip it and log, rather
    than letting a Pydantic ValidationError propagate and lose every other
    correctly-extracted fact in the document."""
    out = []
    for item in items:
        if not item:
            continue
        try:
            out.append(model_cls.model_validate(item))
        except Exception as exc:
            logger.warning("dropping malformed %s entry %r: %s", field_name, item, exc)
    return out


def _call_json(prompt: str, *, agent_name: str, session_id: str) -> dict:
    with traced_generator_llm(
        agent_name=agent_name, session_id=session_id, temperature=0.1, format="json", num_predict=2000
    ) as llm:
        t0 = time.time()
        resp = llm.invoke(prompt)
        latency_ms = int((time.time() - t0) * 1000)
    try:
        return parse_llm_json(resp.content)
    except JSONParseError:
        logger.warning("%s: JSON parse failed, retrying once with a stricter reminder", agent_name)
        retry_prompt = prompt + "\n\nReminder: respond with ONLY the JSON object, nothing else."
        with traced_generator_llm(
            agent_name=agent_name, session_id=session_id, temperature=0.0, format="json", num_predict=2000
        ) as llm:
            resp = llm.invoke(retry_prompt)
        return parse_llm_json(resp.content)


def extract_fact_ledger(
    document_text: str,
    *,
    session_id: str,
    title_hint: str | None = None,
) -> FactLedger:
    title = title_hint or "unknown"

    eligibility_json = _call_json(
        _ELIGIBILITY_PROMPT_TEMPLATE.format(title=title, document=document_text),
        agent_name="fact-extractor-eligibility",
        session_id=session_id,
    )
    rest_json = _call_json(
        _REST_PROMPT_TEMPLATE.format(title=title, document=document_text),
        agent_name="fact-extractor-rest",
        session_id=session_id,
    )

    eligibility = _validate_each(EligibilityCriterion, eligibility_json.get("eligibility", []), "eligibility")
    numeric_thresholds = _validate_each(
        NumericThreshold, eligibility_json.get("numeric_thresholds", []), "numeric_thresholds"
    )
    deadlines = _validate_each(Deadline, rest_json.get("deadlines", []), "deadlines")
    benefits = _validate_each(Benefit, rest_json.get("benefits", []), "benefits")

    ledger = FactLedger(
        scheme_name=rest_json.get("scheme_name") or title,
        summary=rest_json.get("summary", ""),
        eligibility=eligibility,
        numeric_thresholds=numeric_thresholds,
        deadlines=deadlines,
        benefits=benefits,
        required_documents=_coerce_to_strings(rest_json.get("required_documents", [])),
        application_steps=_coerce_to_strings(rest_json.get("application_steps", [])),
    )
    return _ground_against_source(ledger, document_text)


def _coerce_to_strings(items) -> list[str]:
    """required_documents/application_steps are supposed to be list[str],
    but a 3B model occasionally wraps each item in a small dict instead
    (e.g. {"step_number_or_description": "..."}). Extract a usable string
    from either shape rather than crashing the whole ledger over it."""
    out: list[str] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            # Take the first non-empty string value found in the dict.
            for v in item.values():
                if isinstance(v, str) and v.strip():
                    out.append(v.strip())
                    break
    return out


def _ground_against_source(ledger: FactLedger, source_text: str) -> FactLedger:
    """Extraction hallucination guard: a small local model will occasionally
    invent a plausible-sounding numeric threshold or deadline that never
    appears in the source document (observed live: a fabricated "31 March
    2026" deadline on a scheme with no deadline at all). This is a different
    failure mode than "dropped fact" — it's the extractor fabricating a fact,
    not the simplifier losing one — and the ledger-vs-simplified-text
    verification tiers downstream would never catch it, since a faithful
    simplification of a hallucinated fact still "matches" the ledger.

    So: every numeric threshold and deadline the extractor claims to have
    found must itself be checked against the SOURCE text with the same
    deterministic fact_survives() used later for the real verification
    layer. Anything that doesn't actually appear in the source is dropped
    and logged — never silently kept.
    """
    grounded_thresholds = []
    for t in ledger.numeric_thresholds:
        survived, reason = fact_survives(t.raw_text, source_text)
        if survived:
            grounded_thresholds.append(t)
        else:
            logger.warning(
                "extraction hallucination guard: dropping numeric_threshold %r — %s",
                t.raw_text,
                reason,
            )

    grounded_deadlines = []
    for d in ledger.deadlines:
        survived, reason = fact_survives(d.date_or_period, source_text)
        if survived:
            grounded_deadlines.append(d)
        else:
            logger.warning(
                "extraction hallucination guard: dropping deadline %r — %s",
                d.date_or_period,
                reason,
            )

    return ledger.model_copy(
        update={"numeric_thresholds": grounded_thresholds, "deadlines": grounded_deadlines}
    )
