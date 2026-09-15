"""
Deterministic eligibility matching between a logged-in user's profile and
the extracted Fact Ledger of a published scheme. This is rule-based (no LLM
call) so it runs instantly for the user's PDF report and never mutates the
verified fact data — it only reads it.

The matcher is deliberately conservative: misses (false negatives) are
preferable to telling a user they are eligible when the rule is ambiguous.
"""
from __future__ import annotations

from datetime import datetime

from db.models import User

_PENSION_AGE_BANDS = {60, 65, 67}
_DISABILITY_KEYWORDS = ("disab", "divyang", "handicap", "blind", "deaf", "ortho", "mental")
_WOMEN_KEYWORDS = ("woman", "women", "female", "girl", "mother", "widow", "pregnant", "maternal")
_LABOUR_KEYWORDS = ("labour", "labor", "worker", "construction", "shram")
_BPL_KEYWORDS = ("bpl", "below the poverty line", "below-poverty", "below poverty")


def age_from_dob(dob: str) -> int | None:
    """Approximate age in years from a YYYY-MM-DD string. None if unparseable."""
    if not dob:
        return None
    try:
        born = datetime.strptime(dob, "%Y-%m-%d").date()
    except ValueError:
        return None
    today = datetime.now().date()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _ledger_eligibility(ledger: dict | None) -> list[dict]:
    if not ledger:
        return []
    return ledger.get("eligibility") or []


def _criteria_values(ledger: dict | None) -> list[str]:
    values: list[str] = []
    for c in _ledger_eligibility(ledger):
        value = (c.get("value") or "").lower()
        condition = (c.get("condition_type") or "").lower()
        span = (c.get("source_span") or "").lower()
        values.append(f"{condition} {value} {span}")
    return values


def _age_bounds(ledger: dict | None) -> tuple[float | None, float | None]:
    """Parse explicit min/max age bounds from the ledger's eligibility criteria.

    Returns (lower, upper); either can be None when the scheme does not
    constrain that side (e.g. "60+" -> (60, None), "under 10" -> (None, 10),
    "18 to 40" -> (18, 40)).
    """
    lower: float | None = None
    upper: float | None = None
    for c in _ledger_eligibility(ledger):
        if (c.get("condition_type") or "").lower() != "age":
            continue
        try:
            value = float(c.get("value") or 0)
        except (TypeError, ValueError):
            continue
        operator = (c.get("operator") or "").strip()
        if operator in (">", ">=", "==", "upto", "until"):
            lower = value if lower is None else max(lower, value)
        elif operator in ("<", "<="):
            upper = value if upper is None else min(upper, value)
    # Numeric thresholds occasionally carry the age window (e.g. "18 to 40").
    thresholds = (ledger.get("numeric_thresholds") or []) if ledger else []
    for t in thresholds:
        context = ((t.get("context") or "") + (t.get("unit") or "")).lower()
        if "age" not in context:
            continue
        try:
            value = float(t.get("normalized_value") or 0)
        except (TypeError, ValueError):
            continue
        if value >= 18:
            lower = value if lower is None else max(lower, value)
        else:
            upper = value if upper is None else min(upper, value)
    return lower, upper


def _required_gender(ledger: dict | None) -> str | None:
    for c in _ledger_eligibility(ledger):
        if (c.get("condition_type") or "").lower() != "gender":
            continue
        value = (c.get("value") or "").strip()
        if value.lower() in ("male", "female", "women", "men", "girl", "boy"):
            return value.lower()
    return None


def _has_age_band_60_plus(ledger: dict | None) -> bool:
    for c in _ledger_eligibility(ledger):
        cond = (c.get("condition_type") or "").lower()
        if cond != "age":
            continue
        try:
            value = float(c.get("value") or 0)
        except (TypeError, ValueError):
            continue
        operator = (c.get("operator") or "").strip()
        if operator in (">", ">=", "==") and value >= 60:
            return True
    return False


def _income_gate(ledger: dict | None) -> bool:
    """True when the scheme explicitly gates on income / BPL status."""
    for c in _ledger_eligibility(ledger):
        cond = (c.get("condition_type") or "").lower()
        text = f"{c.get('value') or ''} {c.get('source_span') or ''}".lower()
        if cond == "income" or any(kw in text for kw in _BPL_KEYWORDS):
            return True
    thresholds = (ledger.get("numeric_thresholds") or []) if ledger else []
    return any("income" in ((t.get("context") or "") + (t.get("unit") or "")).lower() for t in thresholds)


def _user_income_ok(user: User, ledger: dict | None) -> bool:
    """Check the user's BPL status / annual income against an income gate.

    A strict gate failure returns False. If the gate cannot be evaluated
    (missing profile data) it returns False too — the conservative choice.
    """
    bpl = (user.bpl_status or "").lower() in ("yes", "bpl", "bpl-card")
    if _income_gate(ledger):
        bpl_gate = any(
            "bpl" in f"{c.get('value') or ''} {c.get('source_span') or ''}".lower()
            for c in _ledger_eligibility(ledger)
        )
        if bpl_gate:
            return bpl
        thresholds = (ledger.get("numeric_thresholds") or []) if ledger else []
        limits = [
            float(t.get("normalized_value") or 0)
            for t in thresholds
            if "income" in ((t.get("context") or "") + (t.get("unit") or "")).lower()
            and t.get("normalized_value") is not None
        ]
        if limits and user.annual_income is not None and user.annual_income > min(limits):
            return False
        return bpl or user.annual_income is not None
    return True


def match_scheme(user: User, doc: dict) -> tuple[bool, list[str]]:
    """doc: a Document row (must include .fact_ledger loaded). Returns
    (eligible, reasons)."""
    ledger = doc.fact_ledger.ledger_json if getattr(doc, "fact_ledger", None) else None
    category = (doc.category or "").lower()
    reasons: list[str] = []
    age = age_from_dob(user.dob)

    # 1) Explicit age window in the ledger — highest-confidence gate.
    age_lower, age_upper = _age_bounds(ledger)
    if age is not None:
        if age_upper is not None and age > age_upper:
            return False, [f"Age {age} exceeds the {int(age_upper)}-year age ceiling for {doc.title}."]
        if age_lower is not None and age < age_lower:
            return False, [f"Age {age} is below the {int(age_lower)}-year minimum for {doc.title}."]

    # 2) Explicit gender restriction.
    gender = _required_gender(ledger)
    if gender and (user.gender or "").lower() != gender:
        return False, [f"Scheme is restricted to {gender} applicants."]

    # 3) Pension / senior-citizen programmes.
    if age is not None and age >= 60:
        wants_seniors = category == "pension" or _has_age_band_60_plus(ledger)
        if wants_seniors:
            reasons.append(f"Age {age} meets the senior-citizen threshold for {doc.title}.")
            return True, reasons
    # Pension schemes with an explicit working-age window (e.g. APY 18–40).
    if category == "pension" and age is not None and (age_lower is not None or age_upper is not None):
        reasons.append(f"Age {age} falls within the scheme's age window for {doc.title}.")
        return True, reasons

    # 4) Disability schemes.
    if category == "disability" or any(
        kw in text for kw in _DISABILITY_KEYWORDS for text in _criteria_values(ledger)
    ):
        if (user.disability_status or "").lower() == "yes":
            reasons.append("Profile reports a disability status.")
            return True, reasons
        return False, ["Scheme targets disability support but profile reports no disability."]

    # 5) Women & child welfare.
    if category == "women_child" or any(
        kw in text for kw in _WOMEN_KEYWORDS for text in _criteria_values(ledger)
    ):
        if (user.gender or "").lower() == "female" and _user_income_ok(user, ledger):
            reasons.append("Scheme targets women and child welfare; profile matches.")
            return True, reasons
        return False, ["Scheme targets women and child welfare; profile does not match the target group."]

    # 6) Labour / construction workers.
    if category == "labour" or any(
        kw in text for kw in _LABOUR_KEYWORDS for text in _criteria_values(ledger)
    ):
        occupation = (user.employment_type or "").lower()
        if any(kw in occupation for kw in _LABOUR_KEYWORDS) or (user.bpl_status or "").lower() in (
            "yes",
            "bpl",
            "bpl-card",
        ):
            reasons.append("Employment type or BPL status matches the labour-worker target group.")
            return True, reasons

    # 6b) Occupation-led categories (e.g. PM-KISAN for farmers).
    occupation_keywords = {"agriculture": ("farmer", "kisan", "cultivat", "agricultur")}
    for category_key, kws in occupation_keywords.items():
        if category != category_key:
            continue
        if any(kw in (user.employment_type or "").lower() for kw in kws):
            reasons.append(f"Employment ({user.employment_type}) matches the {category} target group.")
            return True, reasons
        return False, [f"{doc.title} targets {category_key} professionals."]

    # 7) Income-gated schemes: BPL card first, then INR thresholds.
    income = user.annual_income
    has_bpl_gate = any(
        "bpl" in f"{c.get('value') or ''} {c.get('source_span') or ''}".lower()
        for c in _ledger_eligibility(ledger)
        if (c.get("condition_type") or "").lower() == "income"
    )
    if has_bpl_gate:
        if (user.bpl_status or "").lower() in ("yes", "bpl", "bpl-card"):
            reasons.append("Profile holds a Below Poverty Line card matching the scheme's target group.")
            return True, reasons
        return False, [f"{doc.title} requires a Below Poverty Line card."]

    thresholds = (ledger.get("numeric_thresholds") or []) if ledger else []
    income_thresholds = [
        t for t in thresholds if "income" in ((t.get("context") or "") + (t.get("unit") or "")).lower()
    ]
    if income is not None and income_thresholds and not _user_income_ok(user, ledger):
        return False, ["Reported income exceeds the scheme's income ceiling."]
    if income is not None and income_thresholds:
        for t in income_thresholds:
            try:
                limit = float(t.get("normalized_value") or 0)
            except (TypeError, ValueError):
                continue
            if income <= limit:
                reasons.append(
                    f"Reported annual income ₹{income:,.0f} is within the ₹{limit:,.0f} ceiling."
                )
                return True, reasons
        return False, ["Reported income exceeds the scheme's income ceiling."]

    # 8) State-restricted schemes.
    if user.state:
        state_values = [v for v in _criteria_values(ledger) if (v and user.state.lower() in v)]
        if state_values:
            reasons.append(f"Scheme applies to residents of {user.state}.")
            return True, reasons

    return False, []


def matched_schemes(user: User, documents: list) -> list[dict]:
    """Returns [{"document_id", "title", "category", "scheme_url", "reasons"}]."""
    out: list[dict] = []
    for doc in documents:
        if doc.status != "published" or not getattr(doc, "fact_ledger", None):
            continue
        eligible, reasons = match_scheme(user, doc)
        if not eligible:
            continue
        out.append(
            {
                "document_id": doc.id,
                "title": doc.title,
                "category": doc.category,
                "scheme_url": doc.scheme_url,
                "summary": (doc.fact_ledger.ledger_json or {}).get("summary", ""),
                "reasons": reasons,
            }
        )
    return out