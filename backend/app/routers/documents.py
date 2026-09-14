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
    except Exception as exc:
        logger.exception("pipeline failed for document %s", document_id)
        with get_session() as session:
            doc = get_document(session, document_id)
            if doc:
                doc.status = "failed"
                doc.failure_reason = _classify_pipeline_error(exc)


def _classify_pipeline_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "localhost:11434" in message or "ollama" in message:
        return "Ollama is unavailable. Start Ollama and ensure the configured models are installed."
    if "prism" in message:
        return "PRISM tracing failed. Check PRISMTRACE_HOST and credentials, then retry."
    # A bare ConnectError/ConnectTimeout with none of the above substrings
    # (e.g. a raw WinError/OSError message with no host info) is, in this
    # pipeline, overwhelmingly an Ollama connectivity issue: PRISM's own
    # connection failures are now caught non-fatally inside prism/client.py
    # (see prism_session), so they should never reach this handler at all.
    if type(exc).__name__ in ("ConnectError", "ConnectTimeout", "ConnectionError"):
        return (
            "Could not connect to Ollama at the configured host. "
            "Start Ollama and ensure the configured models are installed."
        )
    return f"Pipeline failed: {type(exc).__name__}. Check the backend logs for details."


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
        return {
            "document_id": doc.id,
            "status": doc.status,
            "title": doc.title,
            "failure_reason": doc.failure_reason or None,
        }


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