#!/usr/bin/env python
"""
Seed the NoBar library with a small set of published scheme records so the
UI (library cards, document viewer, login → profile → entitlement PDF) works
immediately, without needing Ollama running.

These are demo records: the fact ledgers below are accurate summaries of
widely-known Government of India schemes and each links to its official
MyScheme page. For fully pipeline-processed, 3-tier-verified records run:

    python scripts/batch_preprocess.py --limit 20

Usage:
  python scripts/seed_demo_data.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from db.models import (  # noqa: E402
    Document,
    EvaluationScore,
    FactLedgerRecord,
    SimplifiedVersion,
    init_db,
)
from db.repository import get_session  # noqa: E402

DEMO_SCHEMES = [
    {
        "title": "Indira Gandhi National Old Age Pension Scheme (IGNOAPS)",
        "category": "pension",
        "scheme_url": "https://www.myscheme.gov.in/schemes/nsap-ignoaps",
        "summary": "Monthly pension for senior citizens aged 60 and above belonging to below-poverty-line households.",
        "eligibility": [
            {"condition_type": "age", "operator": ">=", "value": "60", "unit": "years", "source_span": "60 years of age or more"},
            {"condition_type": "income", "operator": "<=", "value": "BPL", "unit": "card", "source_span": "living below the poverty line"},
        ],
        "numeric_thresholds": [
            {"raw_text": "60 years", "normalized_value": 60, "unit": "years", "context": "minimum age"},
        ],
        "deadlines": [{"date_or_period": "within 60 days of application", "description": "processing time"}],
        "benefits": [{"amount_or_description": "Rs.1,000 per month", "frequency": "monthly"}],
        "required_documents": ["Aadhaar card", "Bank passbook", "Proof of age", "BPL or income certificate"],
        "application_steps": ["Apply at your local pension office or online via the official portal", "Attach age and income proof", "Receive pension into your bank account"],
    },
    {
        "title": "Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)",
        "category": "agriculture",
        "scheme_url": "https://www.myscheme.gov.in/search?keyword=PM-KISAN",
        "summary": "Income support of Rs.6,000 per year to farmer families with cultivable land.",
        "eligibility": [
            {"condition_type": "occupation", "operator": "==", "value": "farmer", "unit": "", "source_span": "landholding farmer families"},
        ],
        "numeric_thresholds": [
            {"raw_text": "Rs.6,000 per year", "normalized_value": 6000, "unit": "INR/year", "context": "total benefit amount"},
            {"raw_text": "Rs.2,000 per instalment", "normalized_value": 2000, "unit": "INR", "context": "each instalment"},
        ],
        "deadlines": [{"date_or_period": "thrice a year", "description": "instalment schedule"}],
        "benefits": [{"amount_or_description": "Rs.6,000 per year", "frequency": "3 instalments of Rs.2,000"}],
        "required_documents": ["Aadhaar card", "Land records", "Bank account"],
        "application_steps": ["Register on the PM-KISAN portal", "Verify land records with your state", "Receive instalments into your bank account"],
    },
    {
        "title": "Sukanya Samriddhi Yojana",
        "category": "women_child",
        "scheme_url": "https://www.myscheme.gov.in/search?keyword=Sukanya+Samriddhi+Yojana",
        "summary": "Savings scheme for the education and marriage of a girl child, opened in her name by a parent or guardian.",
        "eligibility": [
            {"condition_type": "age", "operator": "<=", "value": "10", "unit": "years", "source_span": "girl child below 10 years"},
            {"condition_type": "gender", "operator": "==", "value": "female", "unit": "", "source_span": "girl child"},
        ],
        "numeric_thresholds": [
            {"raw_text": "Rs.250 minimum deposit", "normalized_value": 250, "unit": "INR", "context": "minimum annual deposit"},
            {"raw_text": "Rs.1,50,000 maximum", "normalized_value": 150000, "unit": "INR", "context": "maximum annual deposit"},
        ],
        "deadlines": [{"date_or_period": "until the girl turns 21", "description": "maturity period"}],
        "benefits": [{"amount_or_description": "Tax-free savings with government-guaranteed interest", "frequency": "annual"}],
        "required_documents": ["Girl child birth certificate", "Guardian Aadhaar", "Bank/Post Office account"],
        "application_steps": ["Open the account at a bank or post office", "Deposit the minimum Rs.250 annually", "Withdraw at age 21 or for education"],
    },
    {
        "title": "Pradhan Mantri Ujjwala Yojana",
        "category": "general_welfare",
        "scheme_url": "https://www.myscheme.gov.in/search?keyword=Pradhan+Mantri+Ujjwala+Yojana",
        "summary": "Free LPG cooking-gas connection for women from below-poverty-line households.",
        "eligibility": [
            {"condition_type": "gender", "operator": "==", "value": "female", "unit": "", "source_span": "adult women of BPL households"},
            {"condition_type": "income", "operator": "<=", "value": "BPL", "unit": "card", "source_span": "below poverty line"},
        ],
        "numeric_thresholds": [],
        "deadlines": [{"date_or_period": "once per household", "description": "one connection per BPL family"}],
        "benefits": [{"amount_or_description": "Free LPG connection with first refill and stove", "frequency": "one-time"}],
        "required_documents": ["BPL certificate", "Aadhaar", "Bank account"],
        "application_steps": ["Apply at any authorised LPG distributor", "Verify BPL status", "Get the connection installed"],
    },
    {
        "title": "Atal Pension Yojana (APY)",
        "category": "pension",
        "scheme_url": "https://www.myscheme.gov.in/search?keyword=Atal+Pension+Yojana",
        "summary": "Guaranteed monthly pension of Rs.1,000 to Rs.5,000 for subscribers aged 18 to 40.",
        "eligibility": [
            {"condition_type": "age", "operator": ">=", "value": "18", "unit": "years", "source_span": "age 18"},
            {"condition_type": "age", "operator": "<=", "value": "40", "unit": "years", "source_span": "age 40"},
        ],
        "numeric_thresholds": [
            {"raw_text": "Rs.1,000", "normalized_value": 1000, "unit": "INR/month", "context": "minimum assured pension"},
            {"raw_text": "Rs.5,000", "normalized_value": 5000, "unit": "INR/month", "context": "maximum assured pension"},
        ],
        "deadlines": [{"date_or_period": "60 years of age", "description": "pension begins at age 60"}],
        "benefits": [{"amount_or_description": "Assured monthly pension after age 60", "frequency": "monthly"}],
        "required_documents": ["Aadhaar", "Bank account", "Mobile number"],
        "application_steps": ["Enrol through your bank or post office", "Choose your pension amount", "Start receiving pension at 60"],
    },
]


def main() -> None:
    init_db()
    with get_session() as session:
        existing = session.query(Document).filter(Document.status == "published").count()
        if existing:
            print(f"Library already has {existing} published record(s) — skipping demo seed.")
            return

        now = datetime.now(timezone.utc)
        for i, scheme in enumerate(DEMO_SCHEMES):
            doc = Document(
                title=scheme["title"],
                category=scheme["category"],
                scheme_url=scheme["scheme_url"],
                source_pdf_path="demo-seed",
                source_text=scheme["summary"],
                status="published",
                is_published_to_library=True,
                created_at=now,
            )
            session.add(doc)
            session.flush()

            ledger = {k: v for k, v in scheme.items() if k != "scheme_url"}
            session.add(FactLedgerRecord(document_id=doc.id, ledger_json=ledger))

            en_html = (
                f"<h1>{scheme['title']}</h1><p>{scheme['summary']}</p>"
                f"<h2>What you get</h2><ul>"
                + "".join(f"<li>{b.get('amount_or_description', '')}</li>" for b in scheme["benefits"])
                + f"</ul><p>See the official site for the full, current application process.</p>"
            )
            session.add(
                SimplifiedVersion(
                    document_id=doc.id,
                    language="en",
                    plain_text=scheme["summary"],
                    html_output=en_html,
                    reading_grade=6.0,
                )
            )
            session.add(
                EvaluationScore(
                    document_id=doc.id,
                    fidelity_score=100.0,
                    wcag_score=100.0,
                    readability_grade=6.0,
                    retries_used=0,
                    checks_json={"checks": [], "missing_facts": [], "language_versions": {"en": {"verified": True}}},
                )
            )
            print(f"  + seeded: {scheme['title']}")

    print(f"\nSeeded {len(DEMO_SCHEMES)} published schemes. Restart the backend and open the library.")


if __name__ == "__main__":
    main()