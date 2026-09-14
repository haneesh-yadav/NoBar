"""
Thin wrapper around the PRISM (Block Convey) SDK (`prismtrace-sdk`, imported
as `prismtrace`).

Per the build brief: if PRISMTRACE_PROJECT_ID / PRISMTRACE_API_KEY are not
set, this module becomes a documented no-op rather than crashing the
pipeline, so the app is developable before real PRISM credentials exist.
`settings.prism_enabled` is the single source of truth for whether tracing
is actually active — check the backend startup logs for a warning if traces
aren't showing up in the PRISM dashboard.

Symbols used here are exactly the documented PRISM SDK surface:
  - PRISMtraceCallbackHandler  (LangChain integration)
  - PRISMtrace                  (manual client: .trace_llm())
Auth header used internally by the SDK is X-PRISMtrace-Key, not Bearer.
"""

from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator, Optional

from app.config import settings

logger = logging.getLogger("nobar.prism")

_warned = False


def _warn_once() -> None:
    global _warned
    if not _warned:
        logger.warning(
            "PRISM is not configured (PRISMTRACE_PROJECT_ID / PRISMTRACE_API_KEY "
            "missing from backend/.env). Running with PRISM tracing DISABLED — "
            "no traces will appear in the PRISM dashboard until these are set."
        )
        _warned = True


@lru_cache(maxsize=1)
def get_prism_callback_handler():
    """Build one shared LangChain callback handler for the process."""
    if not settings.prism_enabled:
        _warn_once()
        return None
    try:
        from prismtrace import PRISMtraceCallbackHandler

        return PRISMtraceCallbackHandler(
            api_key=settings.prismtrace_api_key,
            project_id=settings.prismtrace_project_id,
            host=settings.prismtrace_host,
            agent_name="nobar-pipeline",
        )
    except Exception:
        logger.exception("Failed to construct PRISM callback handler (continuing without tracing)")
        return None


@contextmanager
def prism_session(session_id: str) -> Iterator[None]:
    """Every other function in this module treats PRISM failures as
    non-fatal (see module docstring). This one has to work harder to keep
    that guarantee: it wraps the *caller's* pipeline code (via `yield`), so
    a naive `try/except` around the whole thing would also swallow real
    pipeline exceptions raised inside the `with` block, not just PRISM's
    own connection failures. Instead we drive `prismtrace.session()`'s
    __enter__/__exit__ by hand so only PRISM's own failures are caught."""
    if not settings.prism_enabled:
        yield
        return
    try:
        import prismtrace
    except Exception:
        logger.exception("PRISM SDK unavailable (continuing without tracing)")
        yield
        return

    try:
        session_cm = prismtrace.session(session_id)
        session_cm.__enter__()
    except Exception:
        logger.exception("Failed to start PRISM session (continuing without tracing)")
        yield
        return

    try:
        yield
    except BaseException:
        try:
            session_cm.__exit__(*sys.exc_info())
        except Exception:
            logger.exception("Failed to close PRISM session (non-fatal)")
        raise
    else:
        try:
            session_cm.__exit__(None, None, None)
        except Exception:
            logger.exception("Failed to close PRISM session (non-fatal)")


def close_prism() -> None:
    handler = get_prism_callback_handler()
    if handler is not None:
        handler.close()
    get_prism_callback_handler.cache_clear()


@lru_cache
def _manual_client():
    from prismtrace import PRISMtrace

    return PRISMtrace(
        api_key=settings.prismtrace_api_key,
        project_id=settings.prismtrace_project_id,
        host=settings.prismtrace_host,
    )


def trace_manual_step(
    *,
    model: str,
    input_text: str,
    output_text: str,
    latency_ms: int,
    session_id: str,
    agent_id: str,
) -> Optional[dict]:
    """For pipeline steps that are NOT LangChain LLM calls (Ollama-prompted
    translation, TTS synthesis, the deterministic/NLI verification tiers)
    but that should still appear in the PRISM audit trail so a document's
    full trajectory — not just its chat turns — is observable end to end."""
    if not settings.prism_enabled:
        _warn_once()
        return None
    try:
        client = _manual_client()
        return client.trace_llm(
            model=model,
            input_messages=[{"role": "user", "content": input_text}],
            output=output_text,
            latency_ms=latency_ms,
            session_id=session_id,
            agent_id=agent_id,
        )
    except Exception:
        logger.exception("PRISM manual trace failed (non-fatal, pipeline continues)")
        return None


def trace_pipeline_scores(*, session_id: str, scores: dict) -> Optional[dict]:
    """Send the completed pipeline evaluation without customer document text."""
    if not settings.prism_enabled:
        _warn_once()
        return None
    try:
        client = _manual_client()
        return client.trace_llm(
            model="nobar-pipeline-evaluation",
            input_messages=[],
            output="pipeline evaluation completed",
            latency_ms=0,
            session_id=session_id,
            agent_name="nobar-pipeline",
            metadata={"evaluation": scores},
        )
    except Exception:
        logger.exception("PRISM pipeline score trace failed (non-fatal, pipeline continues)")
        return None