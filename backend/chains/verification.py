"""
Stage 4: Verification. The core promise of NoBar — every fact in the ledger
must be checked against the simplified/translated output before it is ever
allowed to publish.

Two tiers, cheapest and most trustworthy first:
  1. Deterministic numeric/date/categorical diff (chains.numeric_utils) —
     no model call, runs on every fact, every document, every language.
  2. LLM-as-judge, using the VERIFIER model (a different model family than
     the generator that wrote the simplification, so it's never "the same
     model grading its own homework") — called ONLY for facts that failed
     tier 1, both to control cost/latency and because tier 1 failing is
     exactly the ambiguous case (paraphrase vs. genuine drop) a judge model
     is for.

(A third tier — a local NLI cross-encoder for bulk/dataset-scale checking —
is in the original design but deliberately deferred: this hardware has 8GB
RAM and ~13GB disk, and adding a torch/sentence-transformers dependency
purely for that would compete with the two Ollama models already resident.
The LLM-judge tier does the same job, just always via a live model call
instead of a cached embedding model — see README for the upgrade path.)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.config import settings
from chains.json_utils import JSONParseError, parse_llm_json
from chains.llm_provider import traced_verifier_llm
from chains.numeric_utils import fact_survives
from schemas.fact_ledger import FactLedger

logger = logging.getLogger("nobar.verification")


@dataclass
class FactCheckResult:
    fact_description: str
    raw_value: str
    tier: str  # "deterministic" | "llm_judge"
    preserved: bool
    reason: str


@dataclass
class VerificationReport:
    fidelity_score: float
    checks: list[FactCheckResult] = field(default_factory=list)
    missing_facts: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.fidelity_score >= settings.fact_fidelity_pass_threshold


def _collect_facts(ledger: FactLedger) -> list[tuple[str, str]]:
    """Returns [(human-readable description, raw value that must survive)]."""
    facts: list[tuple[str, str]] = []
    for e in ledger.eligibility:
        desc = f"Eligibility: {e.condition_type} {e.operator} {e.value} {e.unit or ''}".strip()
        facts.append((desc, e.value))
    for t in ledger.numeric_thresholds:
        facts.append((f"Numeric threshold: {t.context}", t.raw_text))
    for d in ledger.deadlines:
        facts.append((f"Deadline: {d.description}", d.date_or_period))
    for b in ledger.benefits:
        facts.append((f"Benefit: {b.amount_or_description}", b.amount_or_description))
    return facts


def _llm_judge_batch(
    uncertain: list[tuple[str, str]], target_text: str, *, session_id: str
) -> dict[str, tuple[bool, str]]:
    """Ask the verifier model to judge only the facts that failed the
    deterministic check. Returns raw_value -> (preserved, reason)."""
    if not uncertain:
        return {}

    facts_list = "\n".join(
        f'{i + 1}. {desc} (value: "{val}")' for i, (desc, val) in enumerate(uncertain)
    )
    prompt = f"""You are checking whether a plain-language rewrite preserved specific facts from the \
original document. For EACH numbered fact below, decide if it is conveyed ANYWHERE in the text below — even \
worded differently (e.g. "2 lakh" and "Rs 2,00,000" are the same fact; "before 60" and "under 60 years old" \
are the same fact). Be strict: if the number or date does not appear or was changed, mark it not preserved.

Respond with ONLY JSON in this shape:
{{"results": [{{"fact_number": 1, "preserved": true, "reason": "short reason"}}]}}

Facts to check:
{facts_list}

Text to check against:
{target_text}
"""
    try:
        with traced_verifier_llm(
            agent_name="fidelity-judge", session_id=session_id, temperature=0.0, format="json", num_predict=1200
        ) as llm:
            resp = llm.invoke(prompt)
        parsed = parse_llm_json(resp.content)
    except Exception as exc:
        logger.warning("verifier LLM judge call failed or returned invalid output (%s); failing closed", exc)
        return {val: (False, f"verifier LLM unavailable ({type(exc).__name__}) — failing closed") for _, val in uncertain}

    out: dict[str, tuple[bool, str]] = {}
    for r in parsed.get("results", []):
        idx = r.get("fact_number")
        if idx is None or not (1 <= idx <= len(uncertain)):
            continue
        _, val = uncertain[idx - 1]
        out[val] = (bool(r.get("preserved")), r.get("reason", ""))

    # Fail closed: any fact the judge didn't return a verdict for counts as
    # NOT preserved. We never let an ambiguous/missing verdict silently pass.
    for _, val in uncertain:
        if val not in out:
            out[val] = (False, "verifier gave no verdict for this fact — failing closed")
    return out


def verify_fact_fidelity(ledger: FactLedger, target_text: str, *, session_id: str) -> VerificationReport:
    facts = _collect_facts(ledger)
    if not facts:
        return VerificationReport(fidelity_score=100.0, checks=[], missing_facts=[])

    checks: list[FactCheckResult] = []
    tier1_failures: list[tuple[str, str]] = []

    for desc, val in facts:
        if not val:
            continue
        survived, reason = fact_survives(val, target_text)
        if survived:
            checks.append(FactCheckResult(desc, val, "deterministic", True, reason))
        else:
            tier1_failures.append((desc, val))

    judged = _llm_judge_batch(tier1_failures, target_text, session_id=session_id)
    for desc, val in tier1_failures:
        preserved, reason = judged.get(val, (False, "no verdict — failing closed"))
        checks.append(FactCheckResult(desc, val, "llm_judge", preserved, reason))

    total = len(checks)
    preserved_count = sum(1 for c in checks if c.preserved)
    score = (preserved_count / total * 100.0) if total else 100.0
    missing = [f"{c.fact_description} (value: {c.raw_value})" for c in checks if not c.preserved]

    return VerificationReport(fidelity_score=score, checks=checks, missing_facts=missing)
