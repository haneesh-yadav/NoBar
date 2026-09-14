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
from functools import lru_cache
from typing import Optional

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


def get_prism_callback_handler(*, agent_name: str, session_id: str):
    """Returns a PRISMtraceCallbackHandler for use as a LangChain callback,
    or None if PRISM isn't configured. LangChain is fine with an empty
    callback list, so callers should do `callbacks=[h] if h else []`."""
    if not settings.prism_enabled:
        _warn_once()
        return None
    try:
        from prismtrace import PRISMtraceCallbackHandler

        return PRISMtraceCallbackHandler(
            api_key=settings.prismtrace_api_key,
            project_id=settings.prismtrace_project_id,
            host=settings.prismtrace_host,
            agent_name=agent_name,
            session_id=session_id,
        )
    except Exception:
        logger.exception("Failed to construct PRISM callback handler (continuing without tracing)")
        return None


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
            output_message=output_text,
            latency_ms=latency_ms,
            session_id=session_id,
            agent_id=agent_id,
        )
    except Exception:
        logger.exception("PRISM manual trace failed (non-fatal, pipeline continues)")
        return None
