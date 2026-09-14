"""
Stage: Translation. English simplified text -> Hindi / Tamil.

Uses the local generator model with explicit numeric-preservation
instructions, since this hardware budget (8GB RAM, ~13GB disk at the start
of this build) has no room for a dedicated translation model (IndicTrans2)
running alongside the two Ollama models already resident — see README for
that upgrade path on stronger hardware.

Translation is exactly as capable of dropping/altering a number as
simplification is, so callers MUST re-run the same deterministic tier-1
fact check (chains.numeric_utils.fact_survives) against translated output —
this module only produces the translation, it does not itself decide
pass/fail.
"""

from __future__ import annotations

import re

from chains.llm_provider import traced_generator_llm

_LANGUAGE_NAMES = {"hi": "Hindi", "ta": "Tamil"}
_REPETITION_PATTERN = re.compile(r"(.{4,40}?)(?:\s*\1){4,}", re.DOTALL)


_SCRIPT_RANGES = {
    "hi": (0x0900, 0x097F),  # Devanagari
    "ta": (0x0B80, 0x0BFF),  # Tamil
}
_MIN_SCRIPT_PURITY = 0.6  # fraction of alphabetic chars expected in-script


def script_purity(text: str, target_language: str) -> float:
    """Fraction of alphabetic characters in `text` that fall in the target
    language's expected Unicode block. Catches a real failure mode observed
    live: a 3B model producing script-mixed gibberish ("देliआरगाय निडि")
    that happens to keep every number intact and would otherwise pass the
    numeric-only fidelity check while being unreadable nonsense. Digits and
    punctuation are ignored (they're expected to stay ASCII per our own
    translation instructions); only cased/alphabetic characters count."""
    # Known limitation: this only catches gross script contamination (large
    # runs of untranslated English, or Latin letters bleeding mid-word). It
    # does NOT detect fluent-looking nonsense entirely within the correct
    # script — that needs a real language model/perplexity check, which is
    # out of scope for this deterministic tier. Treat this as a coarse
    # sanity check layered on top of the numeric fidelity check, not a
    # substitute for a human or LLM-judge review of translation quality.
    lo, hi = _SCRIPT_RANGES.get(target_language, (0, 0))
    alphabetic = [ch for ch in text if ch.isalpha()]
    if not alphabetic:
        return 1.0
    in_script = sum(1 for ch in alphabetic if lo <= ord(ch) <= hi)
    return in_script / len(alphabetic)


def has_repetition_loop(text: str) -> bool:
    """Detects the degenerate-loop failure mode observed live with the small
    local generator model on translation: the same short phrase repeated
    many times in a row instead of the model finishing its sentence. This is
    checked in addition to (not instead of) fact-fidelity checking, because
    a loop can technically still leave earlier facts intact while making the
    output unusable."""
    return bool(_REPETITION_PATTERN.search(text))

_TRANSLATION_PROMPT = """Translate the following plain-language Indian government scheme description into \
{language}. 

CRITICAL: keep every number, currency amount, date, and percentage EXACTLY as it appears in the English text — \
never change, round, or drop a number. It is fine to write numbers using standard digits (0-9) even in {language} \
text, if that is clearer. Keep the section headings, translated into {language}, so the structure is preserved.

English text:
{text}

Write ONLY the {language} translation, nothing else — no English preamble, no notes.
"""


def _translate_once(prompt: str, *, target_language: str, session_id: str, temperature: float) -> str:
    with traced_generator_llm(
        agent_name=f"translator-{target_language}",
        session_id=session_id,
        temperature=temperature,
        num_predict=1800,
    ) as llm:
        resp = llm.invoke(prompt)
    return resp.content.strip()


def translate_text(text: str, *, target_language: str, session_id: str, max_retries: int = 1) -> str:
    """Translates `text`, retrying (lower temperature, explicit warning
    added to the prompt) if the output degenerates into a repetition loop —
    a real failure mode observed with the small local generator model. This
    only guards against the loop failure; numeric fact-fidelity on the
    result is a separate check the caller (pipeline.py) runs afterward,
    since that requires the FactLedger this module doesn't have."""
    if target_language not in _LANGUAGE_NAMES:
        raise ValueError(f"unsupported target language: {target_language!r}")

    language_name = _LANGUAGE_NAMES[target_language]
    prompt = _TRANSLATION_PROMPT.format(language=language_name, text=text)

    output = _translate_once(prompt, target_language=target_language, session_id=session_id, temperature=0.2)

    attempt = 0
    while has_repetition_loop(output) and attempt < max_retries:
        attempt += 1
        retry_prompt = (
            prompt
            + "\n\nIMPORTANT: your previous attempt got stuck repeating the same phrase. "
            "Write complete, varied sentences and make sure the translation actually finishes."
        )
        output = _translate_once(
            retry_prompt, target_language=target_language, session_id=session_id, temperature=0.05
        )

    return output
