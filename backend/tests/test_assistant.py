"""
Hermetic tests for the "Ask NoBar" assistant. Mixed approach to stay off
the network exactly like the rest of the suite:

  * pure-Python tests of the deterministic grounded fallback (no model, no DB)
  * HTTP tests against a scratch SQLite DB with the LLM call monkeypatched,
    so the router/auth/ledger wiring is exercised without Ollama.
  * optional live-LLM check, skipped unless NOBAR_LLM_TESTS=1.

All DB-backed tests share one temp SQLite file created below (set before any
app import, mirroring test_auth_eligibility_pdf.py).
"""

import os
import tempfile
import uuid

_TEST_DB = os.path.join(tempfile.gettempdir(), "nobar_test_assistant.db")
if os.path.exists(_TEST_DB):
    os.remove(_TEST_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"

from fastapi.testclient import TestClient  # noqa: E402
import pytest  # noqa: E402

from app import assistant as assistant_service  # noqa: E402
from app.assistant import build_grounded_answer  # noqa: E402
from app.main import app  # noqa: E402
from app.security import create_access_token  # noqa: E402
from db.models import Document, FactLedgerRecord, SimplifiedVersion, User  # noqa: E402
from db.repository import get_session  # noqa: E402

SAMPLE_LEDGER = {
    "summary": "Monthly pension for senior citizens aged 60 and above from below-poverty-line households.",
    "eligibility": [
        {"condition_type": "age", "operator": ">=", "value": "60", "unit": "years", "source_span": "60 years or more"},
        {"condition_type": "income", "operator": "<=", "value": "BPL", "unit": "card", "source_span": "below poverty line"},
    ],
    "numeric_thresholds": [{"raw_text": "Rs.1,000 per month", "normalized_value": 1000, "unit": "INR/month", "context": "monthly pension"}],
    "benefits": [{"amount_or_description": "Rs.1,000 per month", "frequency": "monthly"}],
    "required_documents": ["Aadhaar card", "Bank passbook", "Proof of age"],
    "application_steps": ["Apply at your local pension office", "Attach age and income proof"],
    "deadlines": [{"date_or_period": "within 60 days of application", "description": "processing time"}],
}

_TITLE = "Test Old Age Pension Scheme"


def _fake_doc():
    from types import SimpleNamespace

    return SimpleNamespace(
        id="d1",
        title=_TITLE,
        category="pension",
        scheme_url="https://myscheme.gov.in/test",
        status="published",
        fact_ledger=SimpleNamespace(ledger_json=SAMPLE_LEDGER),
    )


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def seeded_document(client):
    """A published Document with fact ledger + en version in the scratch DB."""
    with get_session() as session:
        doc = Document(
            title=_TITLE,
            category="pension",
            scheme_url="https://myscheme.gov.in/test",
            source_pdf_path="test-seed",
            source_text=SAMPLE_LEDGER["summary"],
            status="published",
            is_published_to_library=True,
        )
        session.add(doc)
        session.flush()
        session.add(FactLedgerRecord(document_id=doc.id, ledger_json=SAMPLE_LEDGER))
        session.add(
            SimplifiedVersion(
                document_id=doc.id,
                language="en",
                plain_text=SAMPLE_LEDGER["summary"],
                html_output=f"<h1>{_TITLE}</h1>",
                reading_grade=6.0,
            )
        )
        session.commit()
        return doc.id


@pytest.fixture()
def logged_in_user(client) -> tuple[str, dict]:
    """Create a real User row + return (token, user_dict)."""
    with get_session() as session:
        user = User(
            email=f"ask-{uuid.uuid4().hex[:8]}@test.local",
            password_hash="x",
            full_name="Asha Devi",
            dob="1955-01-01",
            gender="female",
            bpl_status="yes",
            employment_type="Pensioner",
            state="Rajasthan",
        )
        session.add(user)
        session.commit()
        uid = user.id
    token = create_access_token(uid)
    return token, {
        "id": uid,
        "dob": "1955-01-01",
        "gender": "female",
        "bpl_status": "yes",
        "annual_income": None,
        "employment_type": "Pensioner",
        "state": "Rajasthan",
    }


# --------------------------------------------------------------------------
# Pure deterministic fallback (no model, no DB)
# --------------------------------------------------------------------------

def test_fallback_eligibility_personalized():
    user = {"dob": "1955-01-01", "gender": "female", "bpl_status": "yes", "annual_income": None, "employment_type": "Pensioner", "state": "Rajasthan"}
    ans = build_grounded_answer(_fake_doc(), SAMPLE_LEDGER, user, "Am I eligible?")
    assert "eligibility criteria" in ans.lower()
    assert "you appear eligible" in ans.lower()


def test_fallback_eligibility_negative():
    user = {"dob": "2010-01-01", "gender": "male", "bpl_status": "no", "annual_income": 500000, "employment_type": "Engineer", "state": "Karnataka"}
    ans = build_grounded_answer(_fake_doc(), SAMPLE_LEDGER, user, "Am I eligible for this?")
    assert "not appear eligible" in ans.lower()


def test_fallback_documents():
    ans = build_grounded_answer(_fake_doc(), SAMPLE_LEDGER, None, "What documents do I need?")
    assert "Aadhaar card" in ans


def test_fallback_benefits():
    ans = build_grounded_answer(_fake_doc(), SAMPLE_LEDGER, None, "How much money will I get?")
    assert "Rs.1,000" in ans


def test_fallback_apply_includes_official_url():
    ans = build_grounded_answer(_fake_doc(), SAMPLE_LEDGER, None, "How do I apply?")
    assert "Apply at your local pension office" in ans
    assert "myscheme.gov.in/test" in ans


def test_fallback_generic():
    ans = build_grounded_answer(_fake_doc(), SAMPLE_LEDGER, None, "Tell me about this scheme")
    assert SAMPLE_LEDGER["summary"] in ans


# --------------------------------------------------------------------------
# HTTP endpoint with the LLM call monkeypatched
# --------------------------------------------------------------------------

def test_ask_returns_answer(seeded_document, monkeypatch):
    calls = {}

    def fake_answer(doc, ledger, user, question, language="en"):
        calls["ledger"] = ledger
        calls["user"] = user
        return {
            "answer": "Yes — at 71 you meet the 60+ age rule for the Test Old Age Pension Scheme.",
            "engine": "llm",
            "grounded": True,
            "language": language,
            "session_id": "sess-x",
            "matched": True,
            "reasons": ["Age 71 meets the senior-citizen threshold."],
        }

    monkeypatch.setattr(assistant_service, "answer_question", fake_answer)
    with TestClient(app) as c:
        body = {"document_id": seeded_document, "question": "Am I eligible?", "language": "hi"}
        r = c.post("/api/assistant/ask", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["engine"] == "llm"
    assert "60+" in data["answer"]
    assert data["matched"] is True
    assert data["language"] == "hi"
    assert calls["ledger"] == SAMPLE_LEDGER
    assert calls["user"] is None


def test_ask_logged_in_injects_user(seeded_document, logged_in_user, monkeypatch):
    token, user_dict = logged_in_user
    captured = {}

    def fake_answer(doc, ledger, user, question, language="en"):
        captured["user"] = user
        return {
            "answer": "Based on your profile, you qualify.",
            "engine": "fallback",
            "grounded": True,
            "language": language,
            "session_id": "sess-y",
            "matched": True,
            "reasons": [],
        }

    monkeypatch.setattr(assistant_service, "answer_question", fake_answer)
    with TestClient(app) as c:
        r = c.post(
            "/api/assistant/ask",
            json={"document_id": seeded_document, "question": "will they give it to me?"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    assert captured["user"] is not None
    assert captured["user"]["dob"] == user_dict["dob"]
    assert captured["user"]["bpl_status"] == "yes"


def test_ask_unknown_doc_404(monkeypatch):
    def fake_answer(*a, **k):
        raise AssertionError("should not call the model for an unknown doc")

    monkeypatch.setattr(assistant_service, "answer_question", fake_answer)
    with TestClient(app) as c:
        r = c.post("/api/assistant/ask", json={"document_id": "nope", "question": "hi there"})
    assert r.status_code == 404


def test_ask_empty_question_422(seeded_document):
    with TestClient(app) as c:
        r = c.post("/api/assistant/ask", json={"document_id": seeded_document, "question": ""})
    assert r.status_code == 422


# --------------------------------------------------------------------------
# Optional live-LLM integration (skipped unless NOBAR_LLM_TESTS=1)
# --------------------------------------------------------------------------

@pytest.mark.skipif(not os.environ.get("NOBAR_LLM_TESTS"), reason="set NOBAR_LLM_TESTS=1 to hit Ollama")
def test_live_llm_end_to_end(seeded_document):
    with TestClient(app) as c:
        r = c.post("/api/assistant/ask", json={"document_id": seeded_document, "question": "Am I eligible?"})
    assert r.status_code == 200
    data = r.json()
    assert data["answer"]
    assert data["engine"] in ("llm", "fallback")