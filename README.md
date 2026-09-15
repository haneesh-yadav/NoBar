# NoBar — AI Accessibility Auditor for Government/NGO Welfare Scheme Documents

> **Financial Inclusion Theme Fit (Block Convey Hackathon "Money Talks: AI x Finance")**  
> Pensions, disability aid, agricultural subsidies, and maternal welfare are real cash transfers that fail to reach eligible citizens simply because official scheme documents are complex, unreadable, and inaccessible. **NoBar** bridges this gap: it extracts every criterion, numeric threshold, and benefit into a verified **Fact Ledger**, rewrites the document in plain language (WCAG 2.1 AA compliant + audio narration + multilingual translation), and enforces a strict **3-Tier Verification Gate** traced end-to-end via **PRISM** to ensure zero facts are altered or dropped.

---

## 📊 The Financial Inclusion Gap & Cited Research Statistics

- **40% Take-up Rate**: Only ~40% of Indian citizens apply for government benefits they self-report needing (*Demirguc-Kunt et al., cited via Harvard thesis on welfare take-up*).
- **Delhi Widow Pension Study**: Only ~34% of eligible women enrolled despite a life-long cash transfer opportunity (*World Bank 2014 survey + RCT*).
- **BoCW Construction Worker Fund**: Only 40% of ₹50,000 crore in available welfare funds was spent; fewer than 50% of eligible workers even registered (*IDinsight / Indus Action*).
- **Ayushman Bharat Healthcare Study**: 64% were aware of benefits, but only 37.5% ever utilized them. Top cited barriers were **complexity of enrolment (42.2%)** and **lack of procedural knowledge (53.1%)** (*2026 Ayushman Bharat PHC Study*).
- **Regulatory Deadline**: US DOJ Title II rule requires public entities serving 50,000+ residents to meet **WCAG 2.1 AA by April 24, 2026**.

---

## 🏗️ Architecture & Pipeline Workflow

```
               +------------------------------------------------------+
               |                   NoBar Pipeline                     |
               +------------------------------------------------------+
                                          |
                                    [PDF Ingest]
                           (pdfplumber + OCR Fallback)
                                          |
                                          v
                                [Fact Extraction]
                      (Decomposed JSON-mode Schema Calls)
                                          |
                                          v
                               [Plain-Language Rewrite]
                        (WCAG 2.1 AA Structure + Textstat)
                                          |
                                          v
                         +---------------------------------+
                         |  3-Tier Fact Fidelity Gate      |
                         |  1. Deterministic Numeric Diff  |
                         |  2. LLM-as-Judge (llama3.2:3b)  |
                         +---------------------------------+
                                     /         \
                             (Pass) /           \ (Fail & Max Retries)
                                   v             v
                     [WCAG HTML + Audio + Trans]  [Route to Review Queue]
                                   |             (Status: needs_review)
                                   v
                         [Published Library Record]
```

### 1. Fact Extraction Stage
Extracts every criterion, numeric threshold, date/period, and benefit into a structured Pydantic `FactLedger` schema. Every fact retains source quotes from the original document.

### 2. Simplification & Plain Language Stage
Rewrites the document in accessible plain language (reading grade level 5-8), structuring content with semantic headings, lists, and WCAG-compliant landmarks.

### 3. 3-Tier Verification Layer
- **Tier 1 (Deterministic Diff)**: Pure regex & Devanagari/Tamil numeric normalization (lakhs, crores, dates, percentages). Zero LLM calls; runs instantly.
- **Tier 2 (LLM-as-Judge)**: Escalate ambiguous paraphrase cases to `llama3.2:3b` (a different model family than the generator `qwen2.5:3b` to prevent self-grading bias).
- **Corrective Retry Loop**: If fidelity is below 90%, auto-retries simplification with explicit corrective feedback (max 2 retries). If still failing, flags the document as `needs_review` and blocks publishing.

### 4. Accessibility, Translation & Audio
- **WCAG 2.1 AA HTML Audit**: Validated via `axe-core` (JSDOM automated auditor) for zero critical violations.
- **Multilingual Translation**: Hindi (`hi`) and Tamil (`ta`) translations with numeric fidelity survival checks.
- **TTS Audio Narration**: HTML5 audio narration with synced transcript text view.

---

## 👤 Citizen Login, Scheme Links & Entitlement Report (PDF)

Every published scheme now carries a link straight to its **official site** on the Government of India's MyScheme portal (`https://www.myscheme.gov.in`). The link is picked automatically: an explicit URL in the source text wins, otherwise a MyScheme search for the scheme title is built.

Citizens can **Sign Up / Sign In** (JWT login, `pbkdf2` password hashing) — or simply **Sign In with Aadhaar**: enter a 12-digit Aadhaar number, receive an OTP (`123456` in the demo), and NoBar fetches the citizen's details (name, DOB, gender, state, district) and signs them in — creating a pre-filled profile on first use. Aadhaar authentication is a simulated UIDAI stand-in (no real citizen data; only a SHA-256 digest of the number plus the last-4 mask are ever stored). Then a deterministic, rule-free matcher (no LLM call) cross-references the profile against each published scheme's verified Fact Ledger to produce:

- **Schemes You Match** — with the *reason* for the match.
- **Saved Schemes** and **My Applications** (saved/applied per scheme).
- **Download My Report (PDF)** — a single entitlement report containing all profile details, matched schemes, saved items, and applications, generated server-side with `reportlab` and streamed to the browser.

Registration & report endpoints (all under `/api`, auth via `Authorization: Bearer <jwt>`):

| Endpoint | Purpose |
| --- | --- |
| `POST /api/auth/register`, `POST /api/auth/login` | Create account / obtain JWT |
| `POST /api/auth/aadhaar/request-otp` | Send (simulated) Aadhaar OTP; returns fetched details + demo OTP |
| `POST /api/auth/aadhaar/login` | Sign in via Aadhaar OTP — pre-fills + creates an account on first use |
| `GET /api/users/me`, `PUT /api/users/me` | Read / update profile |
| `GET /api/users/me/schemes` | `{ matched, saved, applications }` |
| `GET /api/users/me/schemes/pdf` | Download the entitlement report PDF |
| `POST\|DELETE /api/users/me/schemes/{id}/save`, `POST .../apply` | Save / apply to a scheme |

Try these demo Aadhaar numbers on the login page: `1111 2222 3333`, `2222 2222 2222`, `3333 3333 3333`, `4444 4444 4444` (OTP is always `123456`).

Set a `JWT_SECRET` in `backend/.env` (a random value is generated and persisted on first boot if absent).

To populate the library instantly **without Ollama** (demo records with real outcome data + official links + pre-translated **English / Hindi / Tamil** versions), run:

```bash
python backend/scripts/seed_demo_data.py        # first seed
python backend/scripts/seed_demo_data.py --force  # re-seed with translations
```

Every scheme page now has a **View Language: EN / हिं / தமிழ்** switch (only languages actually present are selectable) plus a **Listen — Read Aloud** button that reads the current language aloud using the browser's built-in screen-reader voice (no server audio needed); when a pipeline-generated studio recording exists, it is used instead.

---

## 🔍 PRISM Integration Checklist

NoBar uses **PRISM by Block Convey**  its observability, auditability, and verification backbone:

- [x] **LangChain Callback Tracing**: All LLM generation & verification calls pass through `PRISMtraceCallbackHandler`.
- [x] **Evaluation Summary Trace**: The completed fact-fidelity, readability, WCAG, and translation scores are sent through the `PRISMtrace` manual client without document text.
- [x] **Unified Session Audit Trail**: Every stage of a document run shares a single `session_id`, grouping the entire audit trajectory into one inspectable PRISM session.
- [x] **Custom Fact Fidelity Evaluator**: Configured in PRISM Evaluators Hub to mirror NoBar's 3-tier fidelity score.
- [x] **Guardrails**:
  - PII/PHI Detection (Flag mode for sample applicant data).
  - Prompt Injection Prevention (Block mode on untrusted uploaded PDFs).
  - Custom Numeric Regex Guardrail.
- [x] **Alerts**: Automated alerts on `compliance_score < 60` and `guardrail_blocks` spikes.
- [x] **Root Cause Analysis**: Surfaces systemic simplification failure patterns across batch document runs.
- [x] **Data Export**: Generates audit-ready evidence packs for regulatory compliance.

---

## 🚀 Quickstart & Local Run Instructions

### Prerequisites
- Python 3.12+
- Node.js 20+ and npm
- Ollama (`qwen2.5:3b` and `llama3.2:3b` pulled)

### 1. Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Set environment variables in `backend/.env` (optional, defaults to local SQLite + PRISM disabled mode):
```ini
PRISMTRACE_HOST=https://prism.blockconvey.com
PRISMTRACE_PROJECT_ID=your-project-uuid
PRISMTRACE_API_KEY=pt-sk-your-key

# Optional JWT signing key for the citizen login feature (auto-generated if absent)
JWT_SECRET=change-me-to-a-long-random-string
```

Run unit test suite:
```bash
PYTHONPATH=backend python -m pytest backend/tests -v
```

Start FastAPI Server:
```bash
python -m uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

### 3. CLI Single Document Test
```bash
python backend/scripts/run_pipeline_cli.py Dataset/data/gov_myscheme/text_data/oap(1).pdf
```

### 4. Batch Preprocess Dataset Subset
```bash
python backend/scripts/batch_preprocess.py --limit 20
```

---

## 📜 License
MIT License. Built for the Block Convey "Money Talks: AI x Finance" Hackathon.
