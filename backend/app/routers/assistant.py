"""
GET/POST entry points for "Ask NoBar".

The heavy lifting lives in app/assistant.py (grounded prompt, PRISM-traced
LLM call, deterministic fallback). This router only wires it to HTTP and the
auth boundary. Authentication is optional: anonymous citizens can ask, and
when a citizen is signed in the assistant additionally reasons from their
profile and the deterministic eligibility check.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app import assistant as assistant_service
from app.routers.users import get_current_user
from db.repository import get_document, get_session

logger = logging.getLogger("nobar.assistant")
router = APIRouter()


class AskBody(BaseModel):
    document_id: str
    question: str = Field(..., min_length=2, max_length=600)
    language: Literal["en", "hi", "ta"] = "en"


def optional_user(authorization: str | None = Header(default=None)) -> Optional[dict]:
    """Resolve the citizen when a valid token is present; else None."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        return get_current_user(authorization)
    except HTTPException:
        return None


@router.post("/ask")
def ask(body: AskBody, user: Optional[dict] = Depends(optional_user)):
    with get_session() as session:
        doc = get_document(session, body.document_id)
        if doc is None or doc.status != "published":
            raise HTTPException(404, "scheme not found or not published")
        ledger = doc.fact_ledger.ledger_json if getattr(doc, "fact_ledger", None) else {}
        snapshot = SimpleNamespace(
            id=doc.id,
            title=doc.title,
            category=doc.category,
            scheme_url=doc.scheme_url,
            status=doc.status,
            fact_ledger=SimpleNamespace(ledger_json=ledger),
        )

    result = assistant_service.answer_question(snapshot, ledger, user, body.question, body.language)
    return {
        "document_id": snapshot.id,
        "title": snapshot.title,
        "scheme_url": snapshot.scheme_url,
        "question": body.question,
        "answer": result["answer"],
        "engine": result["engine"],
        "grounded": result["grounded"],
        "language": result["language"],
        "session_id": result["session_id"],
        "matched": result["matched"],
        "reasons": result["reasons"],
    }