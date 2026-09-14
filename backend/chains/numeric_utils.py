"""
Tier 1 of the verification layer: deterministic numeric/date fidelity checking.

No model calls here — this is regex + normalization, and it is the cheapest,
fastest, most trustworthy check we have. It runs on every document, every
language, every time. It is also the backbone of the PRISM custom regex
guardrail (the same normalization logic mirrors what the guardrail rule should
flag on).

Handles the Indian numbering system (lakh = 100,000; crore = 10,000,000),
currency symbols (₹, Rs., INR), percentages, comma-grouped numbers (both
Indian "2,00,000" and Western "200,000" grouping), and common date formats.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_LAKH = 100_000
_CRORE = 10_000_000

# Hindi/Tamil translations may keep numerals in ASCII digits (as we instruct
# the translator to do) but translate the scale WORD ("lakh"/"crore") into
# the target script. The deterministic checker must recognize those too, or
# every correctly-translated large amount would be a false-negative tier-1
# failure, escalating unnecessarily to the LLM judge tier for documents that
# actually preserved the fact correctly.
_LAKH_WORDS = "lakh|lakhs|lac|lacs|लाख|லட்சம்"
_CRORE_WORDS = "crore|crores|करोड़|கோடி"
_SCALE_WORDS = f"{_LAKH_WORDS}|{_CRORE_WORDS}"

_MONTHS = (
    "january|february|march|april|may|june|july|august|september|"
    "october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)

# Order matters: more specific patterns first.
_NUMBER_PATTERNS = [
    # ₹1,00,000 or Rs. 1,00,000 or INR 100000, optionally followed by lakh/crore
    re.compile(
        rf"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*({_SCALE_WORDS})?",
        re.IGNORECASE,
    ),
    # "2 lakh", "1.5 crore", or the same in Devanagari/Tamil script, with or
    # without a currency symbol/word around it (e.g. "2 लाख रुपये")
    re.compile(rf"\b([\d,]+(?:\.\d+)?)\s*({_SCALE_WORDS})\b", re.IGNORECASE),
    # Percentages: "40%", "40 percent"
    re.compile(r"\b([\d]+(?:\.\d+)?)\s*(%|percent\b)", re.IGNORECASE),
    # Dates: "31 March 2026", "31st March, 2026"
    re.compile(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTHS})\.?,?\s+(\d{{4}})\b",
        re.IGNORECASE,
    ),
    # Dates: "March 31, 2026"
    re.compile(
        rf"\b({_MONTHS})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b",
        re.IGNORECASE,
    ),
    # Dates: dd/mm/yyyy or dd-mm-yyyy
    re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b"),
    # Bare comma-grouped or plain numbers (age, counts, years) — kept last, least specific
    re.compile(r"\b(\d{1,3}(?:,\d{2,3})*(?:\.\d+)?)\b"),
]

_MONTH_TO_NUM = {
    m: i + 1
    for i, m in enumerate(
        [
            "jan", "feb", "mar", "apr", "may", "jun",
            "jul", "aug", "sep", "oct", "nov", "dec",
        ]
    )
}


def _month_to_int(name: str) -> int | None:
    key = name.strip().lower()[:3]
    return _MONTH_TO_NUM.get(key)


@dataclass(frozen=True)
class NormalizedFact:
    raw_text: str
    kind: str  # "currency" | "percent" | "date" | "number"
    normalized: str  # human-readable canonical form, kept for debugging/display
    comparison_key: str  # what fact_survives actually compares on

    @staticmethod
    def make(raw_text: str, kind: str, value_repr: str, comparison_key: str) -> "NormalizedFact":
        return NormalizedFact(raw_text, kind, value_repr, comparison_key)


_LAKH_WORD_SET = {w.lower() for w in _LAKH_WORDS.split("|")}
_CRORE_WORD_SET = {w.lower() for w in _CRORE_WORDS.split("|")}


def _normalize_amount(num_str: str, scale_word: str | None) -> float:
    value = float(num_str.replace(",", ""))
    if scale_word:
        w = scale_word.lower()
        if w in _LAKH_WORD_SET or w.startswith("lakh"):
            value *= _LAKH
        elif w in _CRORE_WORD_SET or w.startswith("crore"):
            value *= _CRORE
    return value


def extract_normalized_facts(text: str) -> list[NormalizedFact]:
    """Extract every number/currency/percent/date in `text`, normalized to a
    canonical comparable form so the same real-world fact expressed two
    different ways (₹2,00,000 vs 2 lakh rupees) compares equal."""
    if not text:
        return []

    found: list[NormalizedFact] = []
    consumed_spans: list[tuple[int, int]] = []

    def overlaps(span: tuple[int, int]) -> bool:
        return any(a < span[1] and span[0] < b for a, b in consumed_spans)

    for idx, pattern in enumerate(_NUMBER_PATTERNS):
        for m in pattern.finditer(text):
            span = m.span()
            if overlaps(span):
                continue

            groups = m.groups()
            raw = m.group(0)

            try:
                if idx == 0 or idx == 1:  # currency / lakh-crore
                    value = _normalize_amount(groups[0], groups[1])
                    # Currency and bare numbers of the same magnitude must be
                    # treated as the same fact: a source "Rs 1,500" survives
                    # just fine as a target "1,500" even without a currency
                    # marker (common after translation), so they share one
                    # AMOUNT: comparison key regardless of the display `kind`.
                    found.append(NormalizedFact.make(raw, "currency", f"INR:{value:.2f}", f"AMOUNT:{value:.2f}"))
                elif idx == 2:  # percent
                    value = float(groups[0])
                    found.append(NormalizedFact.make(raw, "percent", f"PCT:{value:.2f}", f"PCT:{value:.2f}"))
                elif idx == 3:  # "31 March 2026"
                    day, month, year = groups
                    mm = _month_to_int(month)
                    if mm:
                        key = f"DATE:{int(year):04d}-{mm:02d}-{int(day):02d}"
                        found.append(NormalizedFact.make(raw, "date", key, key))
                elif idx == 4:  # "March 31, 2026"
                    month, day, year = groups
                    mm = _month_to_int(month)
                    if mm:
                        key = f"DATE:{int(year):04d}-{mm:02d}-{int(day):02d}"
                        found.append(NormalizedFact.make(raw, "date", key, key))
                elif idx == 5:  # dd/mm/yyyy
                    d, mo, y = groups
                    year = int(y) if len(y) == 4 else 2000 + int(y)
                    key = f"DATE:{year:04d}-{int(mo):02d}-{int(d):02d}"
                    found.append(NormalizedFact.make(raw, "date", key, key))
                else:  # bare number
                    value = float(groups[0].replace(",", ""))
                    found.append(NormalizedFact.make(raw, "number", f"NUM:{value:.2f}", f"AMOUNT:{value:.2f}"))
            except (ValueError, TypeError):
                continue

            consumed_spans.append(span)

    return found


def fact_survives(raw_fact: str, target_text: str) -> tuple[bool, str]:
    """Check whether `raw_fact` (a value/threshold string from the Fact
    Ledger) is recoverable inside `target_text` (the simplified/translated
    output). Returns (survived, reason).

    Numeric/date/currency facts are compared via normalized value equality.
    Purely categorical facts (e.g. "Scheduled Caste") fall back to a
    case-insensitive substring/token check.
    """
    source_facts = extract_normalized_facts(raw_fact)

    if source_facts:
        target_facts = extract_normalized_facts(target_text)
        target_keys = {f.comparison_key for f in target_facts}
        for sf in source_facts:
            if sf.comparison_key in target_keys:
                return True, f"matched {sf.kind} value {sf.raw_text!r}"
        return False, (
            f"none of the numeric/date values in {raw_fact!r} "
            f"({[f.raw_text for f in source_facts]}) were found in the output"
        )

    # No number/date detected — categorical fact. Fall back to fuzzy containment.
    needle = raw_fact.strip().lower()
    haystack = target_text.lower()
    if needle and needle in haystack:
        return True, "exact categorical phrase match"

    # Token overlap fallback for near-paraphrase categorical facts.
    needle_tokens = set(re.findall(r"[a-z]+", needle))
    if not needle_tokens:
        return True, "no comparable content (empty/non-alphanumeric fact)"
    haystack_tokens = set(re.findall(r"[a-z]+", haystack))
    overlap = needle_tokens & haystack_tokens
    ratio = len(overlap) / len(needle_tokens)
    if ratio >= 0.6:
        return True, f"token overlap {ratio:.0%} — likely paraphrase"
    return False, f"categorical phrase {raw_fact!r} not found (token overlap {ratio:.0%})"
