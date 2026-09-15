"""
SQLAlchemy models. SQLite by default (zero setup for local dev), pointed at
a real Supabase Postgres instance in production by setting DATABASE_URL to
the Supabase connection string — same models, same code, no branching,
because Supabase Postgres is just Postgres and SQLAlchemy talks to both
through the same engine interface. Supabase Storage/Auth are layered in
separately (see app/storage.py) and are optional: local disk storage is the
fallback when SUPABASE_URL isn't set.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String, default="")
    category: Mapped[str] = mapped_column(String, default="uncategorized")
    source_pdf_path: Mapped[str] = mapped_column(String)
    source_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="processing")  # processing|published|needs_review|failed
    failure_reason: Mapped[str] = mapped_column(String, default="")
    scheme_url: Mapped[str] = mapped_column(String, default="")
    prism_session_id: Mapped[str] = mapped_column(String, default="")
    is_published_to_library: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    fact_ledger: Mapped["FactLedgerRecord"] = relationship(back_populates="document", uselist=False)
    versions: Mapped[list["SimplifiedVersion"]] = relationship(back_populates="document")
    evaluation: Mapped["EvaluationScore"] = relationship(back_populates="document", uselist=False)
    wcag_audit: Mapped["WcagAuditResult"] = relationship(back_populates="document", uselist=False)
    review_entry: Mapped["ReviewQueueEntry"] = relationship(back_populates="document", uselist=False)


class FactLedgerRecord(Base):
    __tablename__ = "fact_ledgers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    ledger_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    document: Mapped[Document] = relationship(back_populates="fact_ledger")


class SimplifiedVersion(Base):
    __tablename__ = "simplified_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    language: Mapped[str] = mapped_column(String, default="en")  # en | hi | ta
    plain_text: Mapped[str] = mapped_column(Text, default="")
    html_output: Mapped[str] = mapped_column(Text, default="")
    audio_path: Mapped[str] = mapped_column(String, default="")
    reading_grade: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    document: Mapped[Document] = relationship(back_populates="versions")


class EvaluationScore(Base):
    __tablename__ = "evaluation_scores"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    fidelity_score: Mapped[float] = mapped_column(Float, default=0.0)
    wcag_score: Mapped[float] = mapped_column(Float, default=0.0)
    readability_grade: Mapped[float] = mapped_column(Float, default=0.0)
    retries_used: Mapped[int] = mapped_column(Integer, default=0)
    checks_json: Mapped[dict] = mapped_column(JSON, default=dict)
    prism_session_id: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    document: Mapped[Document] = relationship(back_populates="evaluation")


class WcagAuditResult(Base):
    __tablename__ = "wcag_audit_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    raw_result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    violations_count: Mapped[int] = mapped_column(Integer, default=0)
    serious_or_critical_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    document: Mapped[Document] = relationship(back_populates="wcag_audit")


class ReviewQueueEntry(Base):
    __tablename__ = "review_queue"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="open")  # open|resolved
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    document: Mapped[Document] = relationship(back_populates="review_entry")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    full_name: Mapped[str] = mapped_column(String, default="")
    dob: Mapped[str] = mapped_column(String, default="")  # YYYY-MM-DD
    gender: Mapped[str] = mapped_column(String, default="")
    marital_status: Mapped[str] = mapped_column(String, default="")
    disability_status: Mapped[str] = mapped_column(String, default="no")  # no | yes
    disability_type: Mapped[str] = mapped_column(String, default="")
    caste_category: Mapped[str] = mapped_column(String, default="")
    bpl_status: Mapped[str] = mapped_column(String, default="")
    annual_income: Mapped[float | None] = mapped_column(Float, default=None)
    employment_type: Mapped[str] = mapped_column(String, default="")
    state: Mapped[str] = mapped_column(String, default="")
    district: Mapped[str] = mapped_column(String, default="")
    pincode: Mapped[str] = mapped_column(String, default="")
    aadhaar_masked: Mapped[str] = mapped_column(String, default="")
    aadhaar_hash: Mapped[str | None] = mapped_column(String, unique=True, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    saved_schemes: Mapped[list["SavedScheme"]] = relationship(back_populates="user")
    applications: Mapped[list["SchemeApplication"]] = relationship(back_populates="user")


class SavedScheme(Base):
    __tablename__ = "saved_schemes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped[User] = relationship(back_populates="saved_schemes")
    document: Mapped[Document] = relationship()


class SchemeApplication(Base):
    __tablename__ = "scheme_applications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    status: Mapped[str] = mapped_column(String, default="submitted")  # submitted|in_progress|approved|rejected
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped[User] = relationship(back_populates="applications")
    document: Mapped[Document] = relationship()


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
    if engine.dialect.name == "sqlite":
        columns = {column["name"] for column in inspect(engine).get_columns("documents")}
        if "failure_reason" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE documents ADD COLUMN failure_reason VARCHAR DEFAULT ''"))
        if "scheme_url" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE documents ADD COLUMN scheme_url VARCHAR DEFAULT ''"))
        user_columns = {c["name"] for c in inspect(engine).get_columns("users")} if inspect(engine).has_table("users") else set()
        if user_columns and "aadhaar_hash" not in user_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE users ADD COLUMN aadhaar_hash VARCHAR"))
