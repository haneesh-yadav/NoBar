from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.storage import audio_dir_for_document, save_upload
from chains.pipeline import run_pipeline
from db.repository import create_document, get_document, get_session, save_pipeline_result

logger = logging.getLogger("nobar.documents")
router = APIRouter()


def _process_document(document_id: str, pdf_path: str):
    try:
        result = run_pipeline(
            pdf_path,
            session_id=document_id,
            languages=("en", "hi", "ta"),
            audio_dir=audio_dir_for_document(),
        )
        with get_session() as session:
            save_pipeline_result(session, document_id, result)
    except Exception:
        logger.exception("pipeline failed for document %s", document_id)
        with get_session() as session:
            doc = get_document(session, document_id)
            if doc:
                doc.status = "failed"


@router.post("/upload")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "only PDF files are supported")

    contents = await file.read()
    pdf_path = save_upload(contents, file.filename)

    with get_session() as session:
        doc = create_document(session, source_pdf_path=pdf_path)
        document_id = doc.id

    background_tasks.add_task(_process_document, document_id, pdf_path)
    return {"document_id": document_id, "status": "processing"}


@router.get("/{document_id}/status")
def get_status(document_id: str):
    with get_session() as session:
        doc = get_document(session, document_id)
        if doc is None:
            raise HTTPException(404, "document not found")
        return {"document_id": doc.id, "status": doc.status, "title": doc.title}


@router.get("/{document_id}")
def get_document_detail(document_id: str):
    with get_session() as session:
        doc = get_document(session, document_id)
        if doc is None:
            raise HTTPException(404, "document not found")

        return {
            "document_id": doc.id,
            "title": doc.title,
            "status": doc.status,
            "category": doc.category,
            "prism_session_id": doc.prism_session_id,
            "fact_ledger": doc.fact_ledger.ledger_json if doc.fact_ledger else None,
            "versions": [
                {
                    "language": v.language,
                    "plain_text": v.plain_text,
                    "html_output": v.html_output,
                    "audio_path": v.audio_path,
                    "reading_grade": v.reading_grade,
                }
                for v in doc.versions
            ],
            "evaluation": (
                {
                    "fidelity_score": doc.evaluation.fidelity_score,
                    "wcag_score": doc.evaluation.wcag_score,
                    "readability_grade": doc.evaluation.readability_grade,
                    "retries_used": doc.evaluation.retries_used,
                    "checks": doc.evaluation.checks_json,
                }
                if doc.evaluation
                else None
            ),
            "wcag_audit": (
                {
                    "violations_count": doc.wcag_audit.violations_count,
                    "serious_or_critical_count": doc.wcag_audit.serious_or_critical_count,
                    "violations": doc.wcag_audit.raw_result_json.get("violations", []),
                }
                if doc.wcag_audit
                else None
            ),
            "review_reason": doc.review_entry.reason if doc.review_entry else None,
        }


@router.get("/{document_id}/audio/{language}")
def get_audio(document_id: str, language: str):
    from pathlib import Path

    path = Path(audio_dir_for_document()) / f"{document_id}_{language}.mp3"
    if not path.exists():
        raise HTTPException(404, "audio not available for this document/language")
    return FileResponse(str(path), media_type="audio/mpeg")
