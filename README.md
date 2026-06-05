# DecisionVault AI

DecisionVault AI is a GenAI-powered decision memory layer for teams and AI agents. It turns messy workplace communication into structured, reusable decision records.

Instead of only summarizing meetings, DecisionVault AI extracts what was decided, why it was decided, who owns the next step, who approved it, what workflow it affects, and what evidence supports it.

![DecisionVault AI overview](assets/decisionvault-overview.jpg)

## What It Does

- Extracts structured business decisions from meeting notes, Slack-style threads, emails, project notes, and CSV/text exports
- Captures decision rationale, owner, approver, affected workflow, dependencies, source evidence, confidence, and reusable context
- Saves extracted records into a local decision vault
- Lets users ask questions across current extraction results or saved decision history
- Prevents simple duplicate saves
- Exports current and saved records as CSV or Excel
- Flags ambiguous items for human review

## Saved Decision Vault

The saved vault turns one-off extraction into reusable organizational memory. Users can search previous decisions, filter records by keyword, confidence, or project/workflow, and download filtered or full vault exports.

![DecisionVault AI saved vault](assets/decisionvault-saved-vault.jpg)

## Tech Stack

- Python
- Streamlit
- Gemini 2.5 Flash through `google-genai`
- `python-dotenv`
- pandas
- openpyxl
- Local JSON storage

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

## Run Locally

```powershell
python -m streamlit run app.py
```

## Demo Files

For a quick demo, upload these files together:

- `meeting_notes.txt`
- `slack_thread.txt`
- `email_thread.txt`

Then click **Generate Decision Memory**.

## Local Storage

Saved decisions are stored in:

```text
decision_vault.json
```

This keeps the MVP simple and easy to inspect. A production or team version should move this storage to SQLite, Postgres, or another managed database.

## Deployment

The fastest deployment path is Streamlit Community Cloud:

1. Connect this GitHub repository.
2. Set `GEMINI_API_KEY` as a Streamlit secret.
3. Deploy `app.py`.

Render, Railway, Azure, or other Python-friendly hosts can also run the app with:

```powershell
python -m streamlit run app.py
```

## MVP Scope

This version intentionally avoids real Slack, Jira, Gmail, or document management integrations. The goal is to validate the decision-memory workflow first:

```text
messy workplace text -> structured decision records -> saved searchable vault
```

## Privacy Note

Avoid uploading confidential, regulated, or sensitive workplace data unless your Gemini/API setup is approved for that use.
