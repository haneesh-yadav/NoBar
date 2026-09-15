"""
Tests for the login-era additions: password hashing, JWT tokens, scheme link
generation, deterministic eligibility matching, and the citizen PDF report.
All pure Python — no Ollama, no network — so they run in milliseconds.
"""

import os
import tempfile
from types import SimpleNamespace

# Hermetic database: isolate every DB-backed test from the dev storage db.
_TEST_DB = os.path.join(tempfile.gettempdir(), "nobar_test_auth.db")
if os.path.exists(_TEST_DB):
    os.remove(_TEST_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"

from app.aadhaar_demo import DEMO_CITIZENS, DEMO_OTP, fetch_aadhaar_details, otp_matches  # noqa: E402
from app.eligibility import age_from_dob, match_scheme, matched_schemes  # noqa: E402
from app.pdf_report import build_user_report_pdf  # noqa: E402
from app.scheme_links import build_scheme_url, myscheme_search_url  # noqa: E402
from app.security import (  # noqa: E402
    aadhaar_digest,
    aadhaar_placeholder_email,
    create_access_token,
    decode_access_token,
    hash_password,
    mask_aadhaar,
    normalize_aadhaar,
    verify_password,
)


# ---------------------------------------------------------------- security
def test_password_hash_roundtrip():
    stored = hash_password("s3cret-pw")
    assert stored != "s3cret-pw"
    assert verify_password("s3cret-pw", stored)
    assert not verify_password("wrong", stored)


def test_jwt_roundtrip():
    token = create_access_token("user-abc")
    assert decode_access_token(token) == "user-abc"
    assert decode_access_token("not.a.token") is None


# ------------------------------------------------------------------- links
def test_myscheme_search_url_encodes_title():
    url = myscheme_search_url("Old Age Pension")
    assert url == "https://www.myscheme.gov.in/search?keyword=Old+Age+Pension"


def test_build_scheme_url_priority():
    # explicit requested URL wins
    assert build_scheme_url("X", requested="https://www.myscheme.gov.in/schemes/foo") == (
        "https://www.myscheme.gov.in/schemes/foo"
    )
    # myscheme URL found in source text beats the search fallback
    src = "Apply at https://www.myscheme.gov.in/schemes/nsap-ignoaps today."
    assert build_scheme_url("Old Age Pension", source_text=src) == (
        "https://www.myscheme.gov.in/schemes/nsap-ignoaps"
    )
    # fallback to title search
    assert build_scheme_url("PM Kisan") == myscheme_search_url("PM Kisan")
    # empty title -> empty url
    assert build_scheme_url("") == ""


# ------------------------------------------------------------- eligibility
def _user(**kw):
    defaults = dict(
        id="u1",
        dob="1958-08-15",
        gender="",
        marital_status="",
        disability_status="no",
        disability_type="",
        bpl_status="",
        annual_income=None,
        employment_type="",
        state="",
        district="",
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _doc(category: str, title: str, ledger: dict | None = None):
    return SimpleNamespace(
        id="d1",
        title=title,
        category=category,
        scheme_url="",
        status="published",
        fact_ledger=(
            SimpleNamespace(ledger_json=ledger)
            if ledger
            else SimpleNamespace(
                ledger_json={
                    "eligibility": [],
                    "numeric_thresholds": [],
                    "summary": "test",
                }
            )
        ),
    )


def test_age_from_dob():
    assert age_from_dob("1960-01-01") is not None and age_from_dob("1960-01-01") >= 60
    assert age_from_dob("not-a-date") is None
    assert age_from_dob("") is None


def test_pension_match_by_age():
    user = _user(dob="1950-01-01")
    doc = _doc("pension", "Old Age Pension")
    eligible, reasons = match_scheme(user, doc)
    assert eligible
    assert reasons


def test_disability_scheme_requires_disability_status():
    not_disabled = _user(disability_status="no")
    doc = _doc("disability", "Disability Pension")
    eligible, _ = match_scheme(not_disabled, doc)
    assert not eligible

    disabled = _user(disability_status="yes", disability_type="Locomotor")
    eligible, _ = match_scheme(disabled, doc)
    assert eligible


def test_women_scheme_matches_female():
    doc = _doc("women_child", "Matru Vandana")
    assert match_scheme(_user(gender="Female"), doc)[0]
    assert not match_scheme(_user(gender="Male"), doc)[0]


def test_income_gated_scheme():
    ledger = {
        "eligibility": [],
        "numeric_thresholds": [
            {
                "raw_text": "2,00,000",
                "normalized_value": 200000,
                "unit": "INR/annum",
                "context": "maximum annual family income",
            }
        ],
        "summary": "test",
    }
    doc = _doc("general_welfare", "Income Test Scheme", ledger)
    assert match_scheme(_user(annual_income=150000), doc)[0]
    assert not match_scheme(_user(annual_income=400000), doc)[0]


def test_age_window_schemes_respect_ceiling():
    # Sukanya Samriddhi: girl child under 10 -> a 74-year-old must NOT match.
    led = {
        "eligibility": [
            {"condition_type": "age", "operator": "<=", "value": "10", "unit": "years", "source_span": "girl child below 10 years"},
        ],
        "numeric_thresholds": [],
        "summary": "test",
    }
    assert not match_scheme(_user(dob="1952-03-05", gender="Female"), _doc("women_child", "Sukanya", led))[0]
    # A 7-year-old girl matches.
    assert match_scheme(_user(dob="2019-06-01", gender="Female"), _doc("women_child", "Sukanya", led))[0]


def test_pension_age_window_both_bounds():
    # APY: 18 to 40 -> a 74-year-old must NOT match; a 30-year-old matches.
    led = {
        "eligibility": [
            {"condition_type": "age", "operator": ">=", "value": "18", "unit": "years", "source_span": "age 18"},
            {"condition_type": "age", "operator": "<=", "value": "40", "unit": "years", "source_span": "age 40"},
        ],
        "numeric_thresholds": [],
        "summary": "test",
    }
    assert not match_scheme(_user(dob="1952-03-05"), _doc("pension", "APY", led))[0]
    assert match_scheme(_user(dob="1996-01-01"), _doc("pension", "APY", led))[0]


def test_gender_restriction_from_ledger():
    led = {
        "eligibility": [
            {"condition_type": "gender", "operator": "==", "value": "female", "unit": "", "source_span": "women"},
        ],
        "numeric_thresholds": [],
        "summary": "test",
    }
    assert match_scheme(_user(gender="Female"), _doc("general_welfare", "Women Only", led))[0]
    assert not match_scheme(_user(gender="Male"), _doc("general_welfare", "Women Only", led))[0]


def test_bpl_gate_blocked_without_bpl_status():
    led = {
        "eligibility": [
            {"condition_type": "income", "operator": "<=", "value": "BPL", "unit": "card", "source_span": "below poverty line"},
        ],
        "numeric_thresholds": [],
        "summary": "test",
    }
    doc = _doc("general_welfare", "LPG Connection", led)
    assert match_scheme(_user(gender="Female", bpl_status="yes"), doc)[0]
    assert not match_scheme(_user(gender="Female", bpl_status="no"), doc)[0]


def test_occupation_gated_agriculture_scheme():
    # PM-KISAN: agriculture category, farmer occupation required.
    doc = _doc("agriculture", "PM-KISAN")
    assert match_scheme(_user(employment_type="Farmer", bpl_status="no"), doc)[0]
    assert not match_scheme(_user(employment_type="Teacher", bpl_status="yes"), doc)[0]


def test_matched_schemes_snapshot():
    user = _user(dob="1950-06-06")
    docs = [
        _doc("pension", "Pension A"),
        _doc("agriculture", "Farm Scheme"),
    ]
    out = matched_schemes(user, docs)
    assert [d["title"] for d in out] == ["Pension A"]


# --------------------------------------------------------------------- pdf
def test_build_user_report_pdf_returns_valid_pdf():
    user = {
        "full_name": "Asha Singh",
        "email": "asha@example.com",
        "dob": "1955-04-02",
        "gender": "Female",
        "marital_status": "Widowed",
        "disability_status": "no",
        "disability_type": "",
        "caste_category": "",
        "bpl_status": "yes",
        "annual_income": 72000.0,
        "employment_type": "",
        "state": "Uttar Pradesh",
        "district": "Varanasi",
        "pincode": "221001",
        "aadhaar_masked": "XXXX-1234",
    }
    pdf = build_user_report_pdf(
        user,
        matched=[
            {
                "title": "Old Age Pension",
                "category": "pension",
                "scheme_url": "https://www.myscheme.gov.in/schemes/nsap-ignoaps",
                "summary": "Monthly pension for seniors.",
                "reasons": ["Age matches."],
            }
        ],
        saved=[{"title": "PM Kisan", "category": "agriculture"}],
        applications=[
            {"title": "Old Age Pension", "category": "pension", "status": "submitted", "applied_at": "2025-01-10"}
        ],
    )
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1000


# ------------------------------------------------------------ aadhaar (pure)
def test_aadhaar_normalize_mask_digest():
    assert normalize_aadhaar("1111 2222 3333") == "111122223333"
    assert normalize_aadhaar("1111-2222-3333") == "111122223333"
    assert mask_aadhaar("111122223333") == "XXXX-XXXX-3333"
    digest = aadhaar_digest("1111 2222 3333")
    assert digest == aadhaar_digest("111122223333")  # stable, format-independent
    assert len(digest) == 64  # sha256 hex
    assert "111122223333" not in digest  # number is never recoverable
    for bad in ("1234", "1234567890123", "abcd22223333", ""):
        try:
            normalize_aadhaar(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad!r} should have been rejected")


def test_aadhaar_placeholder_email_unique():
    a = aadhaar_placeholder_email("ab" * 32)
    b = aadhaar_placeholder_email("cd" * 32)
    assert a != b and "@nobar.local" in a


def test_aadhaar_demo_details_stable_and_otp():
    d1 = fetch_aadhaar_details("555566667777")
    d2 = fetch_aadhaar_details("5555 6666 7777")  # same digits, different formatting
    assert d1 == d2
    assert d1["pincode"] and d1["state"] and len(d1["dob"]) == 10
    assert DEMO_CITIZENS["111122223333"]["full_name"] == "Asha Kumari Singh"
    assert otp_matches("111122223333", DEMO_OTP)
    assert not otp_matches("111122223333", "000000")


# ------------------------------------------------------ aadhaar api (http)
def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def test_aadhaar_request_otp_endpoint():
    with _client() as c:
        r = c.post("/api/auth/aadhaar/request-otp", json={"aadhaar": "111122223333"})
        assert r.status_code == 200
        body = r.json()
        assert body["otp"] == DEMO_OTP and body["demo"] is True
        assert body["masked_aadhaar"] == "XXXX-XXXX-3333"
        assert body["details"]["full_name"] == "Asha Kumari Singh"
        assert c.post("/api/auth/aadhaar/request-otp", json={"aadhaar": "1234"}).status_code == 422


def test_aadhaar_login_creates_prefilled_profile():
    with _client() as c:
        r = c.post("/api/auth/aadhaar/login", json={"aadhaar": "222222222222", "otp": DEMO_OTP})
        assert r.status_code == 200
        body = r.json()
        assert body["created"] is True
        assert body["user"]["full_name"] == "Rahul Verma"
        assert body["user"]["gender"] == "Male"
        assert body["user"]["state"] == "Madhya Pradesh"
        assert body["user"]["aadhaar_masked"] == "XXXX-XXXX-2222"
        # token works
        me = c.get("/api/users/me", headers={"Authorization": f"Bearer {body['token']}"})
        assert me.status_code == 200 and me.json()["id"] == body["user"]["id"]


def test_aadhaar_login_existing_account_and_otp_guard():
    email = "aadhaar-link@example.com"
    with _client() as c:
        reg = c.post(
            "/api/auth/register",
            json={"email": email, "password": "secret123", "full_name": "Linked User", "aadhaar": "333333333333"},
        )
        assert reg.status_code == 200
        # wrong OTP rejected
        bad = c.post("/api/auth/aadhaar/login", json={"aadhaar": "333333333333", "otp": "000000"})
        assert bad.status_code == 401
        # correct OTP signs into the SAME account (no new row)
        ok = c.post("/api/auth/aadhaar/login", json={"aadhaar": "333333333333", "otp": DEMO_OTP})
        assert ok.status_code == 200
        assert ok.json()["created"] is False
        assert ok.json()["user"]["id"] == reg.json()["user"]["id"]
        # request-otp reports registered
        otp_resp = c.post("/api/auth/aadhaar/request-otp", json={"aadhaar": "333333333333"})
        assert otp_resp.json()["registered"] is True