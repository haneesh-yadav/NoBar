"""
The full document pipeline: ingest -> extract -> simplify -> verify, with
the retry-on-failure gate that is the actual enforcement mechanism behind
"guarantees critical facts survive the rewrite." A document that still fails
fidelity after retries is marked needs_review and is NEVER marked published —
this function has no code path that silently ships a low-fidelity rewrite.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings
from prism.client import prism_session
from chains.extraction import extract_fact_ledger
from chains.ingest import ingest_pdf
from chains.numeric_utils import fact_survives
from chains.simplification import retry_with_corrective_feedback, simplify_document
from chains.translation import _MIN_SCRIPT_PURITY, script_purity, translate_text
from chains.tts import TTSUnavailableError, synthesize_speech, tts_available
from chains.verification import VerificationReport, verify_fact_fidelity
from chains.wcag_formatter import WcagAuditResult, run_axe_audit, simplified_text_to_html
from schemas.fact_ledger import FactLedger

logger = logging.getLogger("nobar.pipeline")


@dataclass
class LanguageVersion:
    language: str
    text: str
    html: str
    audio_path: str | None
    translation_fidelity_score: float | None  # None for English (source language, no translation check needed)
    translation_issues: list[str] = field(default_factory=list)
    verified: bool = True  # False => shown in UI as "machine-translated, unverified", never silently hidden


@dataclass
class PipelineResult:
    session_id: str
    title: str | None
    source_text: str
    ledger: FactLedger
    simplified_text: str
    reading_grade: float
    verification: VerificationReport
    retries_used: int
    status: str  # "published" | "needs_review"
    ingest_warnings: list[str] = field(default_factory=list)
    wcag_audit: WcagAuditResult | None = None
    language_versions: dict[str, LanguageVersion] = field(default_factory=dict)


def run_pipeline(
    pdf_path: str,
    *,
    session_id: str | None = None,
    languages: tuple[str, ...] = ("en",),
    audio_dir: str | None = None,
) -> PipelineResult:
    """languages: which language versions to produce. "en" (the simplified
    text itself) is always available; "hi"/"ta" trigger the translation
    stage — but only after the English version has passed the fidelity
    gate, since translating a rewrite we already know dropped a fact would
    just compound the problem instead of catching it."""
    session_id = session_id or str(uuid.uuid4())
    with prism_session(session_id):
        return _run_pipeline(
            pdf_path, session_id=session_id, languages=languages, audio_dir=audio_dir
        )


def _run_pipeline(
    pdf_path: str,
    *,
    session_id: str,
    languages: tuple[str, ...],
    audio_dir: str | None,
) -> PipelineResult:
    logger.info("pipeline start: session=%s file=%s", session_id, pdf_path)

    ingest_result = ingest_pdf(pdf_path)
    if not ingest_result.text:
        raise ValueError(f"no extractable text from {pdf_path}: {ingest_result.warnings}")

    ledger = extract_fact_ledger(
        ingest_result.text, session_id=session_id, title_hint=ingest_result.title_hint
    )

    simplified_text, grade = simplify_document(ingest_result.text, ledger, session_id=session_id)
    report = verify_fact_fidelity(ledger, simplified_text, session_id=session_id)

    retries_used = 0
    while not report.passed and retries_used < settings.max_simplification_retries:
        retries_used += 1
        logger.info(
            "session=%s: fidelity %.1f%% below threshold %.1f%%, retry %d/%d with corrective feedback",
            session_id,
            report.fidelity_score,
            settings.fact_fidelity_pass_threshold,
            retries_used,
            settings.max_simplification_retries,
        )
        simplified_text, grade = retry_with_corrective_feedback(
            ingest_result.text,
            ledger,
            simplified_text,
            report.missing_facts,
            session_id=session_id,
        )
        report = verify_fact_fidelity(ledger, simplified_text, session_id=session_id)

    status = "published" if report.passed else "needs_review"
    if status == "needs_review":
        logger.warning(
            "session=%s: fidelity %.1f%% still below threshold after %d retries — "
            "routing to human review, NOT publishing",
            session_id,
            report.fidelity_score,
            retries_used,
        )
    else:
        logger.info("session=%s: PUBLISHED, fidelity %.1f%%", session_id, report.fidelity_score)

    title = ingest_result.title_hint or ledger.scheme_name
    result = PipelineResult(
        session_id=session_id,
        title=title,
        source_text=ingest_result.text,
        ledger=ledger,
        simplified_text=simplified_text,
        reading_grade=grade,
        verification=report,
        retries_used=retries_used,
        status=status,
        ingest_warnings=ingest_result.warnings,
    )

    # Only spend translation/TTS/WCAG effort on documents that actually
    # passed the fact-fidelity gate. A needs_review document goes to a human
    # first — translating or narrating a rewrite we already know dropped a
    # fact would just produce more unverified artifacts, not fewer.
    if status != "published":
        return result

    en_html = simplified_text_to_html(
        title=title, simplified_text=simplified_text, lang="en", fidelity_score=report.fidelity_score
    )
    wcag_result = run_axe_audit(en_html)
    result.wcag_audit = wcag_result

    en_audio_path = None
    if tts_available() and audio_dir:
        try:
            en_audio_path = synthesize_speech(
                simplified_text, language="en", output_path=str(Path(audio_dir) / f"{session_id}_en.mp3")
            )
        except TTSUnavailableError as exc:
            logger.warning("session=%s: English TTS failed (%s) — text version still available", session_id, exc)

    result.language_versions["en"] = LanguageVersion(
        language="en",
        text=simplified_text,
        html=en_html,
        audio_path=en_audio_path,
        translation_fidelity_score=None,
    )

    for lang in languages:
        if lang == "en":
            continue
        result.language_versions[lang] = _build_translated_version(
            ledger, simplified_text, title, lang, session_id=session_id, audio_dir=audio_dir
        )

    return result


def _numeric_fidelity_against_translation(
    ledger: FactLedger, translated: str, *, lang: str
) -> tuple[float, list[str]]:
    issues: list[str] = []
    survived = 0
    total = 0
    for fact in ledger.all_numeric_facts():
        total += 1
        ok, reason = fact_survives(fact, translated)
        if ok:
            survived += 1
        else:
            issues.append(f"{fact}: {reason}")
    numeric_score = (survived / total * 100.0) if total else 100.0

    # Numeric survival alone isn't sufficient: a translation can keep every
    # digit intact while being script-mixed gibberish around them (observed
    # live). Fold script purity in as a hard multiplier so garbled output
    # can never report a clean 100%.
    purity = script_purity(translated, lang)
    if purity < _MIN_SCRIPT_PURITY:
        issues.append(
            f"only {purity:.0%} of alphabetic characters are in the expected {lang} script "
            f"(threshold {_MIN_SCRIPT_PURITY:.0%}) — output looks script-mixed/garbled"
        )
        numeric_score = min(numeric_score, purity * 100.0)

    return numeric_score, issues


def _build_translated_version(
    ledger: FactLedger,
    simplified_text: str,
    title: str,
    lang: str,
    *,
    session_id: str,
    audio_dir: str | None,
) -> LanguageVersion:
    # Translation gets the same fact-fidelity gate the English simplification
    # got — a translation is exactly as capable of dropping/altering a
    # number as a rewrite is (observed live: a degenerate repetition loop
    # that dropped a currency amount entirely), and deserves the same
    # guarantee, not a free pass because it happened in a later stage.
    translated = translate_text(simplified_text, target_language=lang, session_id=session_id)
    translation_score, issues = _numeric_fidelity_against_translation(ledger, translated, lang=lang)

    retries = 0
    while translation_score < settings.fact_fidelity_pass_threshold and retries < settings.max_simplification_retries:
        retries += 1
        logger.info(
            "session=%s: %s translation fidelity %.1f%% below threshold, retry %d/%d",
            session_id, lang, translation_score, retries, settings.max_simplification_retries,
        )
        translated = translate_text(simplified_text, target_language=lang, session_id=session_id)
        translation_score, issues = _numeric_fidelity_against_translation(ledger, translated, lang=lang)

    verified = translation_score >= settings.fact_fidelity_pass_threshold
    if not verified:
        logger.warning(
            "session=%s: %s translation still %.1f%% after %d retries — marking UNVERIFIED, "
            "not silently hiding it: %s",
            session_id, lang, translation_score, retries, issues,
        )

    html_doc = simplified_text_to_html(
        title=title, simplified_text=translated, lang=lang, fidelity_score=translation_score
    )

    audio_path = None
    if tts_available() and audio_dir:
        try:
            audio_path = synthesize_speech(
                translated, language=lang, output_path=str(Path(audio_dir) / f"{session_id}_{lang}.mp3")
            )
        except TTSUnavailableError as exc:
            logger.warning("session=%s: %s TTS failed (%s) — text version still available", session_id, lang, exc)

    return LanguageVersion(
        language=lang,
        text=translated,
        html=html_doc,
        audio_path=audio_path,
        translation_fidelity_score=translation_score,
        translation_issues=issues,
        verified=verified,
    )
