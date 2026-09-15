"""
Tests for the login-era additions: password hashing, JWT tokens, scheme link
generation, deterministic eligibility matching, and the citizen PDF report.
All pure Python — no Ollama, no network — so they run in milliseconds.
"""

from types import SimpleNamespace

from app.eligibility import age_from_dob, match_scheme, matched_schemes
from app.pdf_report import build_user_report_pdf
from app.scheme_links import build_scheme_url, myscheme_search_url
from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
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