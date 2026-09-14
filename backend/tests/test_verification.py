"""
Unit tests for the verification layer's deterministic tier, and the
gating logic in verify_fact_fidelity — using a synthetic FactLedger so
these run in milliseconds with no model calls (fact_survives is pure
regex/normalization, no LLM). The LLM-judge tier only triggers when the
deterministic tier fails, so as long as every fact here is deterministically
checkable, this proves the gate end to end without needing Ollama running.
"""

from schemas.fact_ledger import Benefit, Deadline, EligibilityCriterion, FactLedger, NumericThreshold
from chains.verification import verify_fact_fidelity


def _sample_ledger() -> FactLedger:
    return FactLedger(
        scheme_name="Test Pension Scheme",
        summary="A test scheme for elderly citizens.",
        eligibility=[
            EligibilityCriterion(condition_type="age", operator=">=", value="60", unit="years", source_span="60 years"),
        ],
        numeric_thresholds=[
            NumericThreshold(raw_text="₹2,00,000", normalized_value=200000, unit="INR/annum", context="max annual income"),
        ],
        deadlines=[
            Deadline(date_or_period="31 March 2026", description="last date to apply"),
        ],
        benefits=[
            Benefit(amount_or_description="₹1,500 per month", frequency="monthly"),
        ],
        required_documents=["Aadhaar Card"],
        application_steps=["Visit the nearest office"],
    )


def test_full_fidelity_passes_when_every_fact_present():
    ledger = _sample_ledger()
    good_text = (
        "You can apply if you are 60 years or older. Your family income must be below "
        "2 lakh rupees a year. Apply before 31 March 2026. You will receive Rs 1,500 every month. "
        "You need an Aadhaar Card. Visit the nearest office to apply."
    )
    report = verify_fact_fidelity(ledger, good_text, session_id="test")
    assert report.fidelity_score == 100.0
    assert report.passed
    assert report.missing_facts == []


def test_dropped_numeric_fact_fails_the_gate():
    """The core promise of NoBar: if a rewrite drops a number, the gate must
    catch it and refuse to pass, regardless of how good the prose reads."""
    ledger = _sample_ledger()
    bad_text = (
        "You can apply if you are a senior citizen. There is an income limit to qualify. "
        "Apply before the deadline. You will receive a monthly pension. "
        "You need an Aadhaar Card. Visit the nearest office to apply."
    )
    report = verify_fact_fidelity(ledger, bad_text, session_id="test")
    assert report.fidelity_score < 100.0
    assert not report.passed
    # The dropped numeric threshold must show up by name in missing_facts,
    # not just as a lowered score — a human reviewer needs to know exactly
    # what to fix.
    assert any("200,000" in m or "max annual income" in m for m in report.missing_facts)


def test_empty_ledger_trivially_passes():
    empty = FactLedger(scheme_name="Empty", summary="")
    report = verify_fact_fidelity(empty, "any text at all", session_id="test")
    assert report.fidelity_score == 100.0
    assert report.passed
