"""
Single place that constructs LLM clients, as context managers that guarantee
the PRISM trace handler is flushed even if the calling code raises.

Everything else in the pipeline asks for "the generator" or "the verifier"
through here rather than instantiating ChatOllama directly, so:
  1. Model choice is swappable via Settings without touching pipeline code
     (e.g. upgrading to a bigger model on better hackathon-day hardware).
  2. A PRISM callback handler is attached uniformly to every LLM call.

Generator and verifier are deliberately different model families (Gemma vs
Qwen) so the verification layer is never "the same model grading its own
homework."
"""

from __future__ import annotations

from contextlib import contextmanager

from langchain_ollama import ChatOllama

from app.config import settings
from prism.client import get_prism_callback_handler


@contextmanager
def traced_generator_llm(*, agent_name: str, session_id: str, temperature: float = 0.2, **extra):
    handler = get_prism_callback_handler(agent_name=agent_name, session_id=session_id)
    # repeat_penalty guards against a real failure mode observed with these
    # small local models: degenerating into a repeated-phrase loop (e.g.
    # translation output looping the same 3-word phrase hundreds of times
    # instead of finishing the sentence), which both wastes the token budget
    # and silently drops whatever fact should have come after the loop
    # started. 1.3 is a mild default; callers can still override it.
    extra.setdefault("repeat_penalty", 1.3)
    llm = ChatOllama(
        model=settings.generator_model,
        base_url=settings.ollama_host,
        temperature=temperature,
        callbacks=[handler] if handler else [],
        **extra,
    )
    try:
        yield llm
    finally:
        if handler is not None:
            handler.flush()


@contextmanager
def traced_verifier_llm(*, agent_name: str, session_id: str, temperature: float = 0.0, **extra):
    handler = get_prism_callback_handler(agent_name=agent_name, session_id=session_id)
    llm = ChatOllama(
        model=settings.verifier_model,
        base_url=settings.ollama_host,
        temperature=temperature,
        callbacks=[handler] if handler else [],
        **extra,
    )
    try:
        yield llm
    finally:
        if handler is not None:
            handler.flush()
