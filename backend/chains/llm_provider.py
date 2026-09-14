"""
Single place that constructs LLM clients with PRISM callbacks.

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
from typing import Any

from langchain_ollama import ChatOllama

from app.config import settings
from prism.client import get_prism_callback_handler


class _TracedChatOllama(ChatOllama):
    """ChatOllama, but with the model name actually present in
    `invocation_params`.

    Upstream, `BaseChatModel._get_invocation_params()` builds the dict that
    gets handed to every callback (including PRISM's) as `invocation_params`
    from `self._identifying_params`, and `ChatOllama` never populates that
    with the model name. PRISM's trace handler looks for
    `invocation_params["model_name"]` / `invocation_params["model"]` to label
    a trace — with neither key present, every trace we send shows up as
    `model: unknown`. This is a PRISM SDK issue (tracked upstream; see
    llm_provider.py module docstring), but it's a one-property fix on our
    side, so we patch it here rather than wait on a PRISM release.
    """

    def _get_invocation_params(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        params = super()._get_invocation_params(*args, **kwargs)
        # Set both keys since PRISM's SDK checks either name; harmless if it
        # only reads one.
        params.setdefault("model", self.model)
        params.setdefault("model_name", self.model)
        return params


@contextmanager
def traced_generator_llm(*, agent_name: str, session_id: str, temperature: float = 0.2, **extra):
    handler = get_prism_callback_handler()
    # repeat_penalty guards against a real failure mode observed with these
    # small local models: degenerating into a repeated-phrase loop (e.g.
    # translation output looping the same 3-word phrase hundreds of times
    # instead of finishing the sentence), which both wastes the token budget
    # and silently drops whatever fact should have come after the loop
    # started. 1.3 is a mild default; callers can still override it.
    extra.setdefault("repeat_penalty", 1.3)
    llm = _TracedChatOllama(
        model=settings.generator_model,
        base_url=settings.ollama_host,
        temperature=temperature,
        callbacks=[handler] if handler else [],
        metadata={"agent_name": agent_name, "session_id": session_id},
        **extra,
    )
    yield llm


@contextmanager
def traced_verifier_llm(*, agent_name: str, session_id: str, temperature: float = 0.0, **extra):
    handler = get_prism_callback_handler()
    llm = _TracedChatOllama(
        model=settings.verifier_model,
        base_url=settings.ollama_host,
        temperature=temperature,
        callbacks=[handler] if handler else [],
        metadata={"agent_name": agent_name, "session_id": session_id},
        **extra,
    )
    yield llm