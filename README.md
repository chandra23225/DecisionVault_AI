# DecisionVault AI

DecisionVault AI is a GenAI-powered decision memory workspace that turns messy workplace communication into structured, reusable decision records.

It is built for teams and AI agents that need more than meeting summaries. DecisionVault AI extracts what was decided, why it was decided, who owns the next step, who approved it, what workflow it affects, and what evidence supports it.

![DecisionVault AI extract workspace](assets/decisionvault-flask-extract.jpg)

## Product Focus

```text
messy workplace communication -> reviewed decision records -> searchable decision vault
```

DecisionVault AI focuses on durable business context. It helps convert scattered meetings, Slack-style threads, email discussions, incident notes, project updates, and CSV/text exports into decision memory that can be reviewed, saved, searched, and reused.

## Current App Experience

The primary app is now a custom Flask + HTML/CSS interface rather than a Streamlit-only UI. This gives the project more control over layout, navigation, review workflows, and desktop packaging.

Current views:

- **Extract**: upload source files and generate structured decision memory
- **Review**: edit extracted records before saving them
- **Ask**: ask professional, structured questions over the current decision memory
- **Vault**: manage saved decision records in local storage

## Workflow

```mermaid
flowchart TD
    A[User opens DecisionVault AI] --> B[Extract page]
    B --> C[Upload source files<br/>TXT, Markdown, CSV]
    C --> D{Upload validation}

    D -->|Valid files| E[Combine source text<br/>with source-file markers]
    D -->|Rejected files| D1[Show validation errors<br/>unsupported type, too large, empty,<br/>binary-looking, invalid UTF-8, bad CSV]
    D1 --> C

    E --> F[Gemini 2.5 Flash extraction]
    F --> G[Structured decision memory JSON]

    G --> H[Backend enrichment]
    H --> H1[Bayesian confidence scoring]
    H --> H2[Record quality scoring]
    H --> H3[Missing-field detection]

    H1 --> I[Review page]
    H2 --> I
    H3 --> I

    I --> J[User reviews and edits records]
    J --> K{Save reviewed records?}

    K -->|Yes| L[Duplicate check<br/>decision + workflow]
    K -->|No| M[Export current records<br/>CSV or Excel]

    L -->|New record| N[Assign decision ID<br/>and saved timestamp]
    L -->|Duplicate| O[Skip duplicate<br/>and report count]
    N --> P[Local JSON decision vault]
    O --> P

    P --> Q[Vault page]
    Q --> R[Inspect saved decisions]
    Q --> S[Delete outdated records]
    Q --> T[Export saved vault<br/>CSV or Excel]

    J --> U[Ask page]
    P --> U
    U --> V[User asks a question]
    V --> W[Gemini answers using only<br/>provided decision records]
    W --> X[Structured answer result]
    X --> X1[Direct answer]
    X --> X2[Key points]
    X --> X3[Supporting records]
    X --> X4[Information gaps]
    X --> X5[Recommended next steps]
```

### Workflow Summary

1. **Upload evidence**: users add `.txt`, `.md`, or `.csv` files from meetings, threads, emails, notes, or exports.
2. **Validate inputs**: the backend blocks unsupported, oversized, empty, binary-looking, invalid UTF-8, or unusable CSV files before anything is sent to Gemini.
3. **Extract decisions**: Gemini turns the combined source text into structured decision records with rationale, owner, approver, workflow, dependencies, evidence, confidence, and reusable context.
4. **Enrich records**: backend helpers add Bayesian confidence, record quality scores, and missing-field warnings.
5. **Review before saving**: users edit records first, so AI output does not automatically become saved memory.
6. **Save to vault**: reviewed records are deduplicated, assigned decision IDs, timestamped, and stored in a local JSON vault.
7. **Ask and reuse**: users can ask questions over the current decision memory and receive structured answers with supporting records, gaps, and next steps.
8. **Export when needed**: current records and saved vault records can be exported as CSV or Excel.

## Screenshots

### Extract Workspace

![DecisionVault AI extract workspace](assets/decisionvault-flask-extract.jpg)

### Review Records

![DecisionVault AI review workspace](assets/decisionvault-flask-review.jpg)

### Ask Decision Memory

![DecisionVault AI ask workspace](assets/decisionvault-flask-ask.jpg)

### Saved Vault

![DecisionVault AI saved vault](assets/decisionvault-flask-vault.jpg)

## What It Does

- Extracts structured business decisions from meeting notes, Slack-style threads, emails, project notes, and CSV/text exports
- Captures decision rationale, owner, approver, affected workflow, dependencies, source evidence, confidence, and reusable context
- Scores each record for completeness using review-ready quality signals
- Lets users review and edit extracted decision records before saving them
- Saves reviewed records into a local decision vault
- Provides structured Ask results with direct answers, key points, supporting records, information gaps, and next steps
- Prevents simple duplicate saves
- Exports current and saved records as CSV or Excel
- Flags ambiguous or incomplete records for human review

## Structured Ask Results

The Ask page is designed to feel more like a decision-intelligence result than a chatbot response. Answers include:

- answer status: answered, partially answered, or not available
- direct executive-style answer
- key points
- supporting decision records
- information gaps
- recommended next steps

This keeps answers grounded in saved or current decision records and makes missing context explicit.

## Saved Decision Vault

The saved vault turns one-off extraction into reusable organizational memory. Users can save reviewed records, inspect saved decisions, delete outdated records, and export the vault.

![DecisionVault AI saved vault](assets/decisionvault-flask-vault.jpg)

## Tech Stack

- Python
- Flask
- Custom HTML/CSS frontend
- Gemini 2.5 Flash through `google-genai`
- `pywebview` desktop wrapper
- `python-dotenv`
- pandas
- openpyxl
- Local JSON storage
- Streamlit legacy UI kept in `app.py`

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create a `.env` file in the project folder:

```text
GEMINI_API_KEY=your_api_key_here
```

The local vault file can be changed with:

```text
DECISION_VAULT_FILE=data/decision_vault.json
```

## Run The Custom App

Run the non-Streamlit app:

```powershell
python flask_app.py
```

Then open:

```text
http://127.0.0.1:5050
```

## Run As Desktop App

Run the custom app in a desktop window:

```powershell
python desktop_flask_app.py
```

On Windows, you can also double-click:

```text
launch_decisionvault_custom.bat
```

## Optional Streamlit Legacy App

The earlier Streamlit version is still available:

```powershell
python -m streamlit run app.py
```

Desktop wrapper for the Streamlit version:

```powershell
python desktop_app.py
```

## Example Files

For a quick example workflow, upload these files together:

- `meeting_notes.txt`
- `slack_thread.txt`
- `email_thread.txt`

For a more realistic workplace-style example, upload files from `sample_data/`:

- `sample_data/real_meeting_notes_anonymized.txt`
- `sample_data/real_slack_thread_anonymized.txt`
- `sample_data/real_email_thread_anonymized.txt`
- `sample_data/incident_decisions_anonymized.csv`

These files are anonymized examples that mimic decision-heavy workplace communication.

## Upload Safety

DecisionVault AI validates uploads before sending text to Gemini:

- accepts only `.txt`, `.md`, and `.csv`
- enforces per-file and combined upload size limits
- rejects empty files
- rejects binary-looking files
- requires UTF-8 readable text
- validates that `.csv` files contain usable CSV rows

This version does not include antivirus or malware scanning. A public or enterprise deployment should add an antivirus service such as ClamAV or a cloud file scanning service before processing uploaded files.

## Local Storage

Saved decisions are stored in:

```text
decision_vault.json
```

You can override this path with `DECISION_VAULT_FILE` in `.env`.

This keeps the project simple and easy to inspect. A production or team version should move storage to SQLite, Postgres, or another managed database.

## Project Structure

```text
flask_app.py                      Custom Flask app entrypoint
decisionvault/flask_app_core.py   Main Flask routes and app workflow
templates/index.html              Custom app UI
static/styles.css                 Custom app styling
desktop_flask_app.py              Desktop wrapper for the custom app
launch_decisionvault_custom.bat   Windows launcher for the custom app
app.py                            Legacy Streamlit entrypoint
decisionvault/streamlit_app.py    Legacy Streamlit implementation
desktop_app.py                    Desktop wrapper for the Streamlit app
decisionvault/                    Reusable validation, storage, confidence, extraction, and UI view-model helpers
tests/                            Unit tests for core non-UI behavior
sample_data/                      Anonymized example inputs
assets/                           README screenshots
```

## Run Tests

```powershell
python -m unittest discover -s tests
```

## Current Scope

Current capabilities:

- upload `.txt`, `.md`, and `.csv` files
- extract decision records with Gemini
- review and edit extracted records before export or save
- score record completeness with backend quality signals
- save records locally in `decision_vault.json`
- ask structured questions over current decision memory
- manage saved vault records
- prevent simple duplicate saves
- export CSV and Excel files

Not production-ready yet:

- no authentication or team workspaces
- no production database
- no enterprise access controls
- no live Slack, Jira, Gmail, or document integrations
- no formal compliance or data retention controls

## Privacy Note

Avoid uploading confidential, regulated, or sensitive workplace data unless your Gemini/API setup is approved for that use. See [PRIVACY.md](PRIVACY.md) for an anonymization checklist and data safety notes.
