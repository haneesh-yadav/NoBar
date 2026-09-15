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
        "translations": {
            "hi": {
                "title": "इंदिरा गांधी राष्ट्रीय वृद्धावस्था पेंशन योजना (IGNOAPS)",
                "summary": "60 वर्ष या उससे अधिक आयु के वरिष्ठ नागरिकों को मासिक पेंशन, जो गरीबी रेखा से नीचे (BPL) के परिवारों से आते हैं।",
                "benefits": ["हर महीने ₹1,000 पेंशन"],
                "note": "आवेदन के लिए आधिकारिक MyScheme वेबसाइट खोलें: myscheme.gov.in",
            },
            "ta": {
                "title": "இந்திரா காந்தி தேசிய முதியோர் ஓய்வூதியத் திட்டம் (IGNOAPS)",
                "summary": "60 வயது அல்லது அதற்கு மேலான, வறுமைக்கோட்டுக்குக் கீழ் (BPL) குடும்பங்களைச் சேர்ந்த மூத்த குடிமக்களுக்கு மாதாந்திர ஓய்வூதியம்.",
                "benefits": ["மாதம் ₹1,000 ஓய்வூதியம்"],
                "note": "விண்ணப்பிக்க அதிகாரப்பூர்வ MyScheme இணையதளத்தைத் திறக்கவும்: myscheme.gov.in",
            },
        },
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
        "translations": {
            "hi": {
                "title": "प्रधानमंत्री किसान सम्मान निधि (PM-KISAN)",
                "summary": "खेती योग्य भूमि वाले किसान परिवारों को हर साल ₹6,000 की आय सहायता।",
                "benefits": ["साल में ₹6,000 (₹2,000 की 3 किश्तों में)"],
                "note": "आवेदन के लिए आधिकारिक PM-KISAN पोर्टल देखें।",
            },
            "ta": {
                "title": "பிரதம மந்திரி கிசான் சம்மான் நிதி (PM-KISAN)",
                "summary": "விவசாய நிலம் வைத்திருக்கும் விவசாயக் குடும்பங்களுக்கு ஆண்டுக்கு ₹6,000 வருமான ஆதரவு.",
                "benefits": ["ஆண்டுக்கு ₹6,000 (₹2,000 × 3 தவணைகள்)"],
                "note": "விண்ணப்பிக்க அதிகாரப்பூர்வ PM-KISAN இணையதளத்தைப் பார்க்கவும்.",
            },
        },
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
        "translations": {
            "hi": {
                "title": "सुकन्या समृद्धि योजना",
                "summary": "बालिका की शिक्षा और विवाह के लिए बचत योजना; माता-पिता या अभिभावक उसके नाम पर खाता खोलते हैं।",
                "benefits": ["कर-मुक्त बचत और सरकार द्वारा गारंटीकृत ब्याज"],
                "note": "बैंक या डाकघर में खाता खोलें।",
            },
            "ta": {
                "title": "சுகன்யா சம்ரித்தி யோஜனா",
                "summary": "பெண் குழந்தையின் கல்வி மற்றும் திருமணத்திற்கான சேமிப்புத் திட்டம்; பெற்றோர் அல்லது பாதுகாவலர் அவள் பெயரில் கணக்கு திறப்பார்கள்.",
                "benefits": ["வரி இல்லாத சேமிப்பு மற்றும் அரசு உத்தரவாத வட்டி"],
                "note": "வங்கி அல்லது தபால் நிலையத்தில் கணக்கு திறக்கவும்.",
            },
        },
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
        "translations": {
            "hi": {
                "title": "प्रधानमंत्री उज्ज्वला योजना",
                "summary": "गरीबी रेखा से नीचे (BPL) के परिवारों की महिलाओं को मुफ्त एलपीजी गैस कनेक्शन।",
                "benefits": ["मुफ्त गैस कनेक्शन, पहला सिलेंडर और स्टोव"],
                "note": "अपने नजदीकी अधिकृत गैस वितरक से आवेदन करें।",
            },
            "ta": {
                "title": "பிரதம மந்திரி உஜ்வலா யோஜனா",
                "summary": "வறுமைக்கோட்டுக்குக் கீழ் (BPL) குடும்பங்களைச் சேர்ந்த பெண்களுக்கு இலவச எல்பிஜி சமையல் எரிவாயு இணைப்பு.",
                "benefits": ["இலவச கேஸ் இணைப்பு, முதல் உருளை மற்றும் அடுப்பு"],
                "note": "அருகிலுள்ள அங்கீகரிக்கப்பட்ட எரிவாயு விநியோகஸ்தரிடம் விண்ணப்பிக்கவும்.",
            },
        },
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
        "translations": {
            "hi": {
                "title": "अटल पेंशन योजना (APY)",
                "summary": "18 से 40 वर्ष की आयु के ग्राहकों को ₹1,000 से ₹5,000 तक की गारंटीकृत मासिक पेंशन।",
                "benefits": ["60 वर्ष की आयु के बाद हर महीने पक्की पेंशन"],
                "note": "बैंक या डाकघर में नामांकन करें।",
            },
            "ta": {
                "title": "அடல் ஓய்வூதியத் திட்டம் (APY)",
                "summary": "18–40 வயதுடைய சந்தாதாரர்களுக்கு ₹1,000 முதல் ₹5,000 வரை உத்தரவாத மாதாந்திர ஓய்வூதியம்.",
                "benefits": ["60 வயதிற்குப் பிறகு ஒவ்வொரு மாதமும் உறுதியான ஓய்வூதியம்"],
                "note": "வங்கி அல்லது தபால் நிலையத்தில் பதிவு செய்யவும்.",
            },
        },
    },
]


def main() -> None:
    init_db()
    with get_session() as session:
        force = "--force" in sys.argv
        existing = session.query(Document).filter(Document.status == "published").count()
        if existing and not force:
            print(f"Library already has {existing} published record(s) — skipping demo seed.")
            return
        if force:
            demo = session.query(Document).filter(Document.source_pdf_path == "demo-seed").all()
            for d in demo:
                session.query(SimplifiedVersion).filter(SimplifiedVersion.document_id == d.id).delete()
                session.query(FactLedgerRecord).filter(FactLedgerRecord.document_id == d.id).delete()
                session.query(EvaluationScore).filter(EvaluationScore.document_id == d.id).delete()
                session.delete(d)
            session.flush()
            print(f"  --force: removed {len(demo)} previous demo record(s).")

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

            ledger = {k: v for k, v in scheme.items() if k != "scheme_url" and k != "translations"}
            session.add(FactLedgerRecord(document_id=doc.id, ledger_json=ledger))

            languages_verified = {"en": {"verified": True}}
            translations = scheme.get("translations", {})
            for lang_code, tr in [("en", None), *translations.items()]:
                if lang_code == "en":
                    display_title = scheme["title"]
                    summary = scheme["summary"]
                    benefit_lines = [b.get("amount_or_description", "") for b in scheme["benefits"]]
                    note = "See the official site for the full, current application process."
                else:
                    display_title = tr["title"]
                    summary = tr["summary"]
                    benefit_lines = tr["benefits"]
                    note = tr["note"]
                    languages_verified[lang_code] = {"verified": True}
                html = (
                    f"<h1>{display_title}</h1><p>{summary}</p>"
                    f"<h2>{'What you get' if lang_code == 'en' else ('क्या मिलता है' if lang_code == 'hi' else 'உங்களுக்கு என்ன கிடைக்கும்')}</h2><ul>"
                    + "".join(f"<li>{line}</li>" for line in benefit_lines)
                    + f"</ul><p>{note}</p>"
                )
                session.add(
                    SimplifiedVersion(
                        document_id=doc.id,
                        language=lang_code,
                        plain_text=summary,
                        html_output=html,
                        reading_grade=6.0 if lang_code == "en" else 0.0,
                    )
                )

            session.add(
                EvaluationScore(
                    document_id=doc.id,
                    fidelity_score=100.0,
                    wcag_score=100.0,
                    readability_grade=6.0,
                    retries_used=0,
                    checks_json={
                        "checks": [],
                        "missing_facts": [],
                        "language_versions": languages_verified,
                    },
                )
            )
            print(f"  + seeded: {scheme['title']} (en/hi/ta)")

    print(f"\nSeeded {len(DEMO_SCHEMES)} published schemes with English, Hindi & Tamil versions. Restart the backend and open the library.")


if __name__ == "__main__":
    main()