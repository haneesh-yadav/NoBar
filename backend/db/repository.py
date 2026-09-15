"""
Thin data-access layer sitting between the pipeline/FastAPI routes and
SQLAlchemy, so the rest of the app never writes raw session/query code.
"""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy.orm import Session

from chains.pipeline import PipelineResult
from db.models import (
    Document,
    EvaluationScore,
    FactLedgerRecord,
    ReviewQueueEntry,
    SavedScheme,
    SchemeApplication,
    SessionLocal,
    SimplifiedVersion,
    User,
    WcagAuditResult,
)


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_document(session: Session, *, source_pdf_path: str, category: str = "uncategorized") -> Document:
    doc = Document(source_pdf_path=source_pdf_path, category=category, status="processing")
    session.add(doc)
    session.flush()
    return doc


def save_pipeline_result(session: Session, document_id: str, result: PipelineResult) -> Document:
    doc = session.get(Document, document_id)
    if doc is None:
        raise ValueError(f"document {document_id} not found")

    doc.title = result.title or doc.title
    doc.source_text = result.source_text
    doc.status = result.status
    doc.prism_session_id = result.session_id
    if not doc.scheme_url:
        from app.scheme_links import build_scheme_url

        doc.scheme_url = build_scheme_url(doc.title, source_text=result.source_text)

    session.add(
        FactLedgerRecord(document_id=doc.id, ledger_json=result.ledger.model_dump())
    )

    wcag_score = None
    if result.wcag_audit is not None:
        if result.wcag_audit.ran_successfully:
            wcag_score = 100.0 if result.wcag_audit.serious_or_critical_count == 0 else 0.0
        session.add(
            WcagAuditResult(
                document_id=doc.id,
                raw_result_json={"violations": result.wcag_audit.violations},
                violations_count=result.wcag_audit.violations_count,
                serious_or_critical_count=result.wcag_audit.serious_or_critical_count,
            )
        )

    if result.language_versions:
        for lang, v in result.language_versions.items():
            session.add(
                SimplifiedVersion(
                    document_id=doc.id,
                    language=lang,
                    plain_text=v.text,
                    html_output=v.html,
                    audio_path=v.audio_path or "",
                    reading_grade=result.reading_grade if lang == "en" else (v.translation_fidelity_score or 0.0),
                )
            )
    else:
        # needs_review documents still get the raw simplified English text
        # recorded, even though translation/WCAG/audio were skipped — a
        # human reviewer needs to see exactly what was produced, not nothing.
        session.add(
            SimplifiedVersion(
                document_id=doc.id,
                language="en",
                plain_text=result.simplified_text,
                reading_grade=result.reading_grade,
            )
        )

    session.add(
        EvaluationScore(
            document_id=doc.id,
            fidelity_score=result.verification.fidelity_score,
            wcag_score=wcag_score,
            readability_grade=result.reading_grade,
            retries_used=result.retries_used,
            checks_json={
                "checks": [
                    {
                        "fact": c.fact_description,
                        "value": c.raw_value,
                        "tier": c.tier,
                        "preserved": c.preserved,
                        "reason": c.reason,
                    }
                    for c in result.verification.checks
                ],
                "missing_facts": result.verification.missing_facts,
                "language_versions": {
                    lang: {
                        "translation_fidelity_score": v.translation_fidelity_score,
                        "verified": v.verified,
                        "issues": v.translation_issues,
                    }
                    for lang, v in result.language_versions.items()
                },
            },
            prism_session_id=result.session_id,
        )
    )

    if result.status == "needs_review":
        session.add(
            ReviewQueueEntry(
                document_id=doc.id,
                reason=(
                    f"Fact fidelity {result.verification.fidelity_score:.1f}% below threshold "
                    f"after {result.retries_used} retries. Missing: "
                    + "; ".join(result.verification.missing_facts)
                ),
                status="open",
            )
        )

    session.flush()
    return doc


def get_document(session: Session, document_id: str) -> Document | None:
    return session.get(Document, document_id)


def list_library(session: Session, *, published_only: bool = True) -> list[Document]:
    q = session.query(Document)
    if published_only:
        q = q.filter(Document.status == "published")
    return q.order_by(Document.created_at.desc()).all()


def list_review_queue(session: Session) -> list[ReviewQueueEntry]:
    return (
        session.query(ReviewQueueEntry)
        .filter(ReviewQueueEntry.status == "open")
        .order_by(ReviewQueueEntry.created_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Users / saved schemes / applications
# ---------------------------------------------------------------------------


def create_user(
    session: Session,
    *,
    email: str,
    password_hash: str,
    full_name: str = "",
    aadhaar_hash: str | None = None,
    aadhaar_masked: str = "",
) -> User:
    user = User(
        email=email.lower().strip(),
        password_hash=password_hash,
        full_name=full_name,
        aadhaar_hash=aadhaar_hash,
        aadhaar_masked=aadhaar_masked,
    )
    session.add(user)
    session.flush()
    return user


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.query(User).filter(User.email == email.strip().lower()).first()


def get_user_by_aadhaar(session: Session, aadhaar_hash: str) -> User | None:
    return session.query(User).filter(User.aadhaar_hash == aadhaar_hash).first()


def get_user(session: Session, user_id: str) -> User | None:
    return session.get(User, user_id)


def update_user_profile(session: Session, user: User, updates: dict) -> User:
    for field, value in updates.items():
        if not hasattr(user, field):
            continue
        setattr(user, field, value)
    session.flush()
    return user


def save_scheme_for_user(session: Session, user_id: str, document_id: str) -> SavedScheme:
    existing = (
        session.query(SavedScheme)
        .filter(SavedScheme.user_id == user_id, SavedScheme.document_id == document_id)
        .first()
    )
    if existing:
        return existing
    entry = SavedScheme(user_id=user_id, document_id=document_id)
    session.add(entry)
    session.flush()
    return entry


def unsave_scheme_for_user(session: Session, user_id: str, document_id: str) -> None:
    session.query(SavedScheme).filter(
        SavedScheme.user_id == user_id, SavedScheme.document_id == document_id
    ).delete()


def is_scheme_saved(session: Session, user_id: str, document_id: str) -> bool:
    return (
        session.query(SavedScheme)
        .filter(SavedScheme.user_id == user_id, SavedScheme.document_id == document_id)
        .first()
        is not None
    )


def apply_to_scheme(session: Session, user_id: str, document_id: str) -> SchemeApplication:
    existing = (
        session.query(SchemeApplication)
        .filter(SchemeApplication.user_id == user_id, SchemeApplication.document_id == document_id)
        .first()
    )
    if existing:
        return existing
    entry = SchemeApplication(user_id=user_id, document_id=document_id, status="submitted")
    session.add(entry)
    session.flush()
    return entry


def list_saved_schemes(session: Session, user_id: str) -> list[SavedScheme]:
    return (
        session.query(SavedScheme)
        .filter(SavedScheme.user_id == user_id)
        .order_by(SavedScheme.created_at.desc())
        .all()
    )


def list_applications(session: Session, user_id: str) -> list[SchemeApplication]:
    return (
        session.query(SchemeApplication)
        .filter(SchemeApplication.user_id == user_id)
        .order_by(SchemeApplication.applied_at.desc())
        .all()
    )
