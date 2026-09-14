from __future__ import annotations

from fastapi import APIRouter

from db.repository import get_session, list_library

router = APIRouter()


@router.get("")
def get_library():
    with get_session() as session:
        docs = list_library(session, published_only=True)
        return [
            {
                "document_id": d.id,
                "title": d.title,
                "category": d.category,
                "fidelity_score": d.evaluation.fidelity_score if d.evaluation else None,
                "wcag_score": d.evaluation.wcag_score if d.evaluation else None,
                "languages_available": [v.language for v in d.versions],
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ]
