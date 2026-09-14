"""
The Fact Ledger is the canonical, structured extraction of every legally/
practically load-bearing fact in a scheme document: who qualifies, by what
numeric thresholds, by when, for what benefit, with what paperwork.

This is the object the verification layer checks against. Every field that
matters for eligibility must carry a `source_span` (a verbatim quote from the
source document) so a human reviewer — or the deterministic/NLI/LLM-judge
verification tiers — can trace every extracted fact back to where it came from.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

# NOTE: condition_type/operator are deliberately plain free-text strings, not
# enums. Tried enum-constrained + deeply nested tool-calling schemas first —
# on a 3B local model (the hardware budget here has no room for anything
# bigger, see README) that forced schema silently produced empty lists
# instead of failing loudly. Free text extracted via explicit JSON-mode
# prompting, then loosely normalized downstream, is far more reliable with
# small local models than a rigid schema the model can't reason its way into.


class EligibilityCriterion(BaseModel):
    condition_type: str = Field(
        ..., description="e.g. 'age', 'income', 'occupation', 'location', 'caste_category', 'disability_status'"
    )
    operator: str = Field(..., description="e.g. '<', '<=', '==', '>=', '>', 'in', 'not_in'")
    value: str = Field(..., description="The threshold/value, as text, e.g. '60', 'BPL', 'Scheduled Caste'")
    unit: Optional[str] = Field(None, description="e.g. 'years', 'INR/annum', '%'")
    source_span: str = Field(..., description="Verbatim quote from the source document this was extracted from")


class NumericThreshold(BaseModel):
    raw_text: str = Field(..., description="Exact text as it appeared, e.g. '₹2,00,000 per annum'")
    normalized_value: float = Field(..., description="Numeric value normalized to a plain float, e.g. 200000.0")
    unit: str = Field(..., description="e.g. 'INR', 'years', 'percent', 'acres'")
    context: str = Field(..., description="What this number gates, e.g. 'maximum annual family income'")


class Deadline(BaseModel):
    date_or_period: str = Field(..., description="e.g. '31 March 2026' or 'within 60 days of application'")
    description: str


class Benefit(BaseModel):
    amount_or_description: str
    frequency: Optional[str] = Field(None, description="e.g. 'monthly', 'one-time', 'per academic year'")


class FactLedger(BaseModel):
    scheme_name: str
    summary: str = Field(..., description="One-sentence, jargon-free summary of what the scheme does")
    eligibility: list[EligibilityCriterion] = Field(default_factory=list)
    numeric_thresholds: list[NumericThreshold] = Field(default_factory=list)
    deadlines: list[Deadline] = Field(default_factory=list)
    benefits: list[Benefit] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    application_steps: list[str] = Field(default_factory=list)

    def all_numeric_facts(self) -> list[str]:
        """Every raw numeric string that MUST survive simplification/translation."""
        out: list[str] = []
        for t in self.numeric_thresholds:
            out.append(t.raw_text)
        for e in self.eligibility:
            if e.value:
                out.append(e.value)
        for d in self.deadlines:
            out.append(d.date_or_period)
        for b in self.benefits:
            out.append(b.amount_or_description)
        return out
