"""
Small local models occasionally wrap JSON in markdown fences, add a trailing
comma, or emit a stray comment even in "json" format mode. This is a
defensive parser used by every JSON-mode LLM call in the pipeline so one
malformed response doesn't crash a whole document run.
"""

from __future__ import annotations

import json
import re


class JSONParseError(ValueError):
    pass


def parse_llm_json(raw: str) -> dict:
    text = raw.strip()

    # Strip markdown code fences if the model added them despite format=json.
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Trailing commas are the most common small-model JSON mistake.
    no_trailing_commas = re.sub(r",(\s*[\]}])", r"\1", text)
    try:
        return json.loads(no_trailing_commas)
    except json.JSONDecodeError:
        pass

    # Last resort: grab the outermost {...} span and retry.
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        candidate = re.sub(r",(\s*[\]}])", r"\1", brace_match.group(0))
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise JSONParseError(f"could not parse JSON from model output: {raw[:300]!r}")
