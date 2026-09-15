"""
"Ask NoBar" — a grounded question-answering assistant for a single scheme.

Every answer is anchored to the *verified Fact Ledger* extracted by the
pipeline (ages, income ceilings, benefit amounts, document lists, steps).
The assistant never draws on general model knowledge for the numbers.

Two engines, same guarantee:
  * LLM engine: a small local model (settings.effective_assistant_model)
    answers with our explicit "answer only from these verified facts"
    prompt. The call goes through traced_generator_llm + prism_session, so
    it is fully observable in the PRISM dashboard like the pipeline.
  * Fallback engine: a deterministic, intent-matched answer built straight
    from the ledger JSON. Used whenever Ollama is down, a model is missing,
    or the call times out — so the citizen still gets a correct, grounded
    answer (marked engine="fallback" so the UI is honest about provenance).

This is the public, user-facing AI surface of the app: a citizen can ask
"Am I eligible?" or "What documents do I need?" in plain words and get a
simple answer plus a pointer to the official site.
"""

from __future__ import annotations

import logging
import re
import uuid
from types import SimpleNamespace

from app.config import settings
from chains.llm_provider import traced_generator_llm
from prism.client import prism_session

logger = logging.getLogger("nobar.assistant")

_LANG_NAMES = {"en": "English", "hi": "Hindi", "ta": "Tamil"}

_INTENT_ELIGIBILITY = re.compile(
    r"\b(eligible|eligib|qualif|am i|could i|criteria|criterion|get it|can i apply)\b|"
    r"\b(age|too old|too young)\b"
)
_INTENT_DOCS = re.compile(r"\b(documents?|certificates?|papers?|proof|aadhaar|pan cards?|bank passbook)\b")
_INTENT_BENEFITS = re.compile(
    r"\b(benefit|money|how much|amount|pension|payment|monthly|income support|financial|worth)\b|₹|rs?\.?\s?\d"
)
_INTENT_APPLY = re.compile(
    r"\b(apply|process|how do i|how can i|steps|form|submit|deadline|when does|where do i)\b"
)


def _as_text(value, indent: str = "") -> str:
    """Render any ledger fragment (list/dict/scalar) as compact human text."""
    if value is None:
        return ""
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                bits = [v for k, v in item.items() if v not in (None, "", [])]
                parts.append(" ".join(str(b) for b in bits).strip())
            else:
                parts.append(str(item).strip())
        return (indent + "\n").join(p for p in parts if p)
    if isinstance(value, dict):
        parts = [f"{k}: {v}" for k, v in value.items() if v not in (None, "", [])]
        return indent + "\n".join(parts)
    return str(value)


def _ledger_snapshot(ledger: dict) -> str:
    """Compose a short, human-readable truth block from the ledger JSON."""
    out: list[str] = []
    if ledger.get("summary"):
        out.append(f"Summary: {ledger['summary']}")
    if ledger.get("eligibility"):
        out.append("Eligibility criteria:\n" + _as_text(ledger["eligibility"], "- "))
    if ledger.get("benefits"):
        out.append("Benefits:\n" + _as_text(ledger["benefits"], "- "))
    if ledger.get("numeric_thresholds"):
        out.append("Key numbers:\n" + _as_text(ledger["numeric_thresholds"], "- "))
    if ledger.get("required_documents"):
        out.append("Documents needed:\n" + _as_text(ledger["required_documents"], "- "))
    if ledger.get("application_steps"):
        out.append("How to apply:\n" + _as_text(ledger["application_steps"], str(1) + ". "))
    if ledger.get("deadlines"):
        out.append("Deadlines / timing:\n" + _as_text(ledger["deadlines"], "- "))
    return "\n".join(out) or "(no verified facts are recorded for this scheme yet)"


def _profile_summary(user: dict | None) -> str:
    if not user:
        return ""
    age: str = ""
    if user.get("dob"):
        from app.eligibility import age_from_dob

        y = age_from_dob(user["dob"])
        age = str(y) if y is not None else ""
    return (
        "The logged-in citizen's profile on file is: "
        f"age {age or 'not given'}, gender {user.get('gender') or 'not given'}, "
        f"BPL card {'yes' if (user.get('bpl_status') or '').lower() in ('yes', 'bpl', 'bpl-card') else 'no'}, "
        f"annual income {'₹' + format(user.get('annual_income') or 0, ',') if user.get('annual_income') else 'not given'}, "
        f"employment {user.get('employment_type') or 'not given'}, "
        f"state {user.get('state') or 'not given'}."
    )


def matched_verdict(user: dict | None, doc) -> tuple[bool | None, list[str]]:
    """Deterministic, explanation-producing eligibility check for the profile
    on file. Returns (matched, reasons) or (None, []) when not logged in."""
    if not user:
        return None, []
    try:
        from app.eligibility import match_scheme

        u = SimpleNamespace(
            dob=user.get("dob") or "",
            gender=user.get("gender") or "",
            disability_status=user.get("disability_status") or "",
            bpl_status=user.get("bpl_status") or "",
            annual_income=user.get("annual_income"),
            employment_type=user.get("employment_type") or "",
            state=user.get("state") or "",
        )
        return match_scheme(u, doc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("matched_verdict failed (%s); continuing unpinned", exc)
        return None, []


def build_grounded_prompt(doc, ledger: dict, user: dict | None, question: str, language: str) -> str:
    lang_name = _LANG_NAMES.get(language, "English")
    verdict_block = ""
    if user:
        matched, reasons = matched_verdict(user, doc)
        if matched is not None:
            reason_txt = " ".join(reasons) or "no specific reason recorded"
            verdict_block = (
                "\nThe deterministic eligibility check for this citizen against this scheme says: "
                f"{'MATCHED' if matched else 'NOT MATCHED'} ({reason_txt}). "
                "Use this as ground truth when the citizen asks whether they are eligible.\n"
            )
    url = getattr(doc, "scheme_url", "") or ""
    return f"""You are NoBar's scheme assistant for Indian citizens. You answer ONLY from the verified facts below. Follow these rules strictly:
- Answer in {lang_name}.
- NEVER invent benefit amounts, minimum/maximum ages, income ceilings, document names, or deadlines that are not in the verified facts.
- If the verified facts do NOT answer the question, say so in one line and point the citizen to the official page: {url}
- Keep the answer under 120 words, in very simple language a first-time reader can follow. Use short sentences and plain words.
- Never give legal or medical advice.

===== VERIFIED FACTS FOR: {doc.title} =====
{_ledger_snapshot(ledger)}
{_profile_summary(user)}
{verdict_block}
===== END OF VERIFIED FACTS =====

Question from citizen: {question}
Answer:"""


def build_grounded_answer(doc, ledger: dict, user: dict | None, question: str) -> str:
    """Deterministic fallback answer derived directly from the ledger. No model."""
    q = question.lower()
    title = doc.title
    url = getattr(doc, "scheme_url", "") or ""

    matched, reasons = matched_verdict(user, doc)

    def verdict() -> str:
        if matched is None:
            return ""
        if matched:
            return f"\n\nChecking against the profile on this account: you appear eligible. {' '.join(reasons) if reasons else ''}"
        return f"\n\nChecking against the profile on this account: you do not appear eligible. {' '.join(reasons) if reasons else ''}"

    if _INTENT_ELIGIBILITY.search(q):
        cr = _as_text(ledger.get("eligibility") or [], "  - ")
        body = f"Here are the verified eligibility criteria for {title}:\n  - {cr}" if cr else (
            f"No eligibility criteria are recorded for {title} yet."
        )
        return body + verdict() + f"\n\nOfficial page: {url}"

    if _INTENT_DOCS.search(q):
        docs = _as_text(ledger.get("required_documents") or [], "  - ")
        return (
            f"Documents you will typically need for {title}:\n  - {docs}"
            if docs
            else f"No document list is recorded for {title} yet. Official page: {url}"
        )

    if _INTENT_BENEFITS.search(q):
        benefits = _as_text(ledger.get("benefits") or [], "  - ")
        numbers = _as_text(ledger.get("numeric_thresholds") or [], "  - ")
        out = f"What {title} provides:\n  - {benefits}" if benefits else f"No benefit amounts are recorded for {title} yet."
        if numbers:
            out += f"\n\nKey numbers:\n  - {numbers}"
        return out

    if _INTENT_APPLY.search(q):
        steps = _as_text(ledger.get("application_steps") or [], "  1. ")
        timing = _as_text(ledger.get("deadlines") or [], "  - ")
        out = f"To apply for {title}:\n 1. {steps}" if steps else f"No application steps are recorded for {title} yet."
        if timing:
            out += f"\n\nTiming:\n  - {timing}"
        return out + f"\n\nRun the application on the official page: {url}"

    # Default: a grounded summary plus pointers.
    summary = ledger.get("summary") or "No summary is recorded for this scheme yet."
    benefits = " ".join(
        b.get("amount_or_description", "") for b in (ledger.get("benefits") or []) if isinstance(b, dict)
    )
    out = f"{summary}"
    if benefits:
        out += f" Benefits include: {benefits}."
    return out + f"\n\nFor eligibility, documents or steps, ask me more specifically, or see the official page: {url}"


def _invoke_with_timeout(llm, prompt: str, timeout_s: int):
    """Call llm.invoke(), aborting to None if the model exceeds timeout_s.

    LangChain's ChatOllama streams tokens, so a read-timeout resets on every
    chunk and a slow cold-start model can hold the request open indefinitely.
    We cap the whole call instead so the citizen always gets an answer (the
    grounded fallback) within a couple of seconds of the cap.
    """
    import concurrent.futures

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="assistant-llm")
    try:
        future = pool.submit(llm.invoke, prompt)
        return future.result(timeout=timeout_s)
    except concurrent.futures.TimeoutError:
        return None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def answer_question(doc, ledger: dict, user: dict | None, question: str, language: str = "en") -> dict:
    """Run the assistant for one question. Always returns grounded text."""
    session_id = str(uuid.uuid4())
    answer: str | None = None
    engine = "fallback"
    with prism_session(session_id):
        try:
            prompt = build_grounded_prompt(doc, ledger, user, question, language)
            with traced_generator_llm(
                agent_name="nobar-assistant",
                session_id=session_id,
                temperature=0.25,
                model=settings.effective_assistant_model,
                num_predict=420,
                request_timeout=35,
            ) as llm:
                resp = _invoke_with_timeout(llm, prompt, 25)
                if resp is not None:
                    text = (resp.content or "").strip()
                    text = "\n".join(line for line in text.splitlines() if line.strip()).strip()
                    if len(text) >= 12:
                        answer = text
                        engine = "llm"
                    else:
                        logger.warning("assistant returned an empty/trivial answer; using grounded fallback")
        except Exception as exc:  # noqa: BLE001 — Ollama down/missing model/timeout → grounded fallback
            logger.warning("assistant LLM call failed (%s: %s); using grounded fallback", type(exc).__name__, exc)

    if answer is None:
        answer = build_grounded_answer(doc, ledger, user, question)
        engine = "fallback"

    matched, reasons = matched_verdict(user, doc)
    return {
        "answer": answer,
        "engine": engine,
        "grounded": True,
        "language": language,
        "session_id": session_id,
        "matched": matched,
        "reasons": reasons,
    }