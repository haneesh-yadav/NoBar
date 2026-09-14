from __future__ import annotations

from fastapi import APIRouter

from db.repository import get_session, list_review_queue

router = APIRouter()


@router.get("/queue")
def get_review_queue():
    with get_session() as session:
        entries = list_review_queue(session)
        return [
            {
                "id": e.id,
                "document_id": e.document_id,
                "document_title": e.document.title if e.document else None,
                "reason": e.reason,
                "status": e.status,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ]


@router.post("/{entry_id}/resolve")
def resolve_review_entry(entry_id: str, action: str = "approve"):
    from fastapi import HTTPException
    from db.models import Document, ReviewQueueEntry

    with get_session() as session:
        entry = session.get(ReviewQueueEntry, entry_id)
        if not entry:
            raise HTTPException(404, "review entry not found")

        entry.status = "resolved"
        if entry.document:
            if action == "approve":
                entry.document.status = "published"
            elif action == "reject":
                entry.document.status = "rejected"

        return {"id": entry.id, "status": entry.status, "action": action}

