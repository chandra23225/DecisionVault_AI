import os
import json
import html
from io import BytesIO

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

from decisionvault.confidence import add_bayesian_confidence_to_records
from decisionvault.gemini_helpers import GeminiJSONError, extract_json_from_response
from decisionvault.storage import (
    delete_decision_from_vault as delete_decision_from_vault_file,
    load_vault as load_vault_file,
    save_decisions_to_vault as save_decisions_to_vault_file,
    save_vault as save_vault_file,
)
from decisionvault.validation import get_file_size, validate_uploaded_file
from decisionvault.view_models import (
    enrich_records_for_ui,
    format_bytes,
    summarize_records,
    summarize_uploaded_files,
)


# =========================
# App Setup
# =========================

load_dotenv()

st.set_page_config(
    page_title="DecisionVault AI",
    page_icon="🧠",
    layout="wide"
)

st.markdown(
    """
    <style>
    :root {
        --dv-bg: #f8fafc;
        --dv-ink: #0f172a;
        --dv-muted: #475569;
        --dv-line: #d8dee8;
        --dv-card: #ffffff;
        --dv-teal: #0f766e;
        --dv-teal-soft: #ccfbf1;
        --dv-green: #047857;
        --dv-amber: #b45309;
        --dv-red: #dc2626;
    }

    .stApp {
        background:
            radial-gradient(circle at top left, rgba(15, 118, 110, 0.08), transparent 32rem),
            linear-gradient(180deg, #ffffff 0%, var(--dv-bg) 42%, #ffffff 100%);
        color: var(--dv-ink);
    }

    .stApp,
    .stApp p,
    .stApp li,
    .stApp label,
    .stApp h1,
    .stApp h2,
    .stApp h3,
    .stApp h4,
    .stApp h5,
    .stApp h6,
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] * {
        color: var(--dv-ink);
    }

    .stCaptionContainer,
    .stCaptionContainer *,
    small {
        color: var(--dv-muted) !important;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1240px;
    }

    [data-testid="stSidebar"] {
        background: #f1f5f9;
        border-right: 1px solid var(--dv-line);
    }

    [data-testid="stSidebar"] * {
        color: var(--dv-ink) !important;
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] li,
    [data-testid="stSidebar"] .stCaptionContainer {
        color: var(--dv-muted) !important;
    }

    [data-testid="stSidebar"] div[data-testid="stAlert"] *,
    [data-testid="stAlert"] * {
        color: var(--dv-ink) !important;
    }

    .dv-hero {
        position: relative;
        overflow: hidden;
        border: 1px solid var(--dv-line);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        background: #ffffff;
        box-shadow: 0 18px 44px rgba(15, 23, 42, 0.08);
    }

    .dv-hero::after {
        content: "";
        position: absolute;
        inset: auto -6rem -8rem auto;
        width: 22rem;
        height: 22rem;
        border-radius: 999px;
        background: rgba(15, 118, 110, 0.08);
    }

    .dv-kicker {
        display: inline-flex;
        gap: 0.45rem;
        align-items: center;
        padding: 0.35rem 0.65rem;
        border: 1px solid #99f6e4;
        border-radius: 999px;
        color: #115e59 !important;
        background: #f0fdfa;
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        text-transform: uppercase;
    }

    .dv-hero h1 {
        margin: 0.7rem 0 0.55rem;
        color: var(--dv-ink) !important;
        font-size: 2.45rem;
        line-height: 1.08;
        letter-spacing: 0;
    }

    .dv-hero p {
        max-width: 760px;
        color: var(--dv-muted) !important;
        font-size: 1.08rem;
        line-height: 1.65;
        margin: 0;
    }

    .dv-appbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: 0.8rem;
    }

    .dv-brand {
        font-weight: 900;
        letter-spacing: -0.01em;
        color: var(--dv-ink) !important;
    }

    .dv-appbar-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        justify-content: flex-end;
    }

    .dv-mini-pill {
        border: 1px solid var(--dv-line);
        background: #ffffff;
        border-radius: 999px;
        padding: 0.32rem 0.62rem;
        color: var(--dv-muted) !important;
        font-size: 0.8rem;
        font-weight: 750;
    }

    .dv-hero-grid {
        position: relative;
        z-index: 1;
        display: grid;
        grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr);
        gap: 1.4rem;
        align-items: stretch;
    }

    .dv-hero-side {
        border: 1px solid var(--dv-line);
        border-radius: 14px;
        padding: 1rem;
        background: #f8fafc;
        display: grid;
        gap: 0.7rem;
        align-content: start;
    }

    .dv-pipeline-row {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.65rem;
        margin-top: 1.05rem;
    }

    .dv-pipeline-step {
        border: 1px solid var(--dv-line);
        border-radius: 12px;
        background: #f8fafc;
        padding: 0.8rem;
    }

    .dv-step-number {
        width: 1.55rem;
        height: 1.55rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 999px;
        background: #0f172a;
        color: #ffffff !important;
        font-size: 0.78rem;
        font-weight: 900;
        margin-bottom: 0.5rem;
    }

    .dv-step-title {
        color: var(--dv-ink) !important;
        font-weight: 850;
        margin-bottom: 0.15rem;
    }

    .dv-step-copy {
        color: var(--dv-muted) !important;
        font-size: 0.86rem;
        line-height: 1.45;
    }

    .dv-side-label {
        color: var(--dv-muted) !important;
        font-size: 0.76rem;
        font-weight: 850;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }

    .dv-side-value {
        color: var(--dv-ink) !important;
        font-weight: 850;
        font-size: 1.05rem;
    }

    .dv-workspace-title {
        display: flex;
        align-items: end;
        justify-content: space-between;
        gap: 1rem;
        margin: 1.25rem 0 0.7rem;
    }

    .dv-workspace-title h2 {
        margin: 0;
        font-size: 1.35rem;
        letter-spacing: -0.01em;
    }

    .dv-workspace-title p {
        margin: 0.1rem 0 0;
        color: var(--dv-muted) !important;
    }

    .dv-panel-note {
        border: 1px solid var(--dv-line);
        border-radius: 12px;
        background: #ffffff;
        padding: 0.95rem;
        margin-bottom: 0.75rem;
    }

    .dv-panel-note-title {
        color: var(--dv-ink) !important;
        font-weight: 850;
        margin-bottom: 0.25rem;
    }

    .dv-panel-note-copy {
        color: var(--dv-muted) !important;
        line-height: 1.5;
        font-size: 0.92rem;
    }

    .dv-file-list {
        border: 1px solid var(--dv-line);
        border-radius: 12px;
        padding: 0.7rem 0.85rem;
        background: #f8fafc;
        margin: 0.65rem 0;
    }

    .dv-file-row {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        padding: 0.35rem 0;
        border-bottom: 1px solid #e2e8f0;
    }

    .dv-file-row:last-child {
        border-bottom: 0;
    }

    .dv-file-name {
        color: var(--dv-ink) !important;
        font-weight: 750;
        overflow-wrap: anywhere;
    }

    .dv-file-size {
        color: var(--dv-muted) !important;
        white-space: nowrap;
        font-size: 0.86rem;
    }

    .dv-empty-state {
        border: 1px dashed #94a3b8;
        border-radius: 14px;
        background: #f8fafc;
        padding: 1.3rem;
        text-align: center;
        margin: 0.75rem 0;
    }

    .dv-empty-state strong {
        display: block;
        color: var(--dv-ink) !important;
        margin-bottom: 0.25rem;
    }

    .dv-empty-state span {
        color: var(--dv-muted) !important;
    }

    .dv-hero-grid {
        position: relative;
        z-index: 1;
    }

    .dv-status-pill {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 180px;
        padding: 0.8rem 1rem;
        border-radius: 14px;
        background: #f0fdfa;
        border: 1px solid #99f6e4;
        color: #115e59 !important;
        font-weight: 800;
    }

    .dv-card-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.9rem;
        margin: 1rem 0 1.25rem;
    }

    .dv-card {
        background: rgba(255, 255, 255, 0.88);
        border: 1px solid var(--dv-line);
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
    }

    .dv-card-label {
        color: var(--dv-muted) !important;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }

    .dv-card-title {
        color: var(--dv-ink) !important;
        font-size: 1.05rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
    }

    .dv-card-body {
        color: var(--dv-muted) !important;
        font-size: 0.92rem;
        line-height: 1.5;
    }

    .dv-alert-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.9rem;
        margin-bottom: 1.2rem;
    }

    .dv-alert {
        border-radius: 12px;
        padding: 0.9rem 1rem;
        border: 1px solid var(--dv-line);
        background: #ffffff;
        color: var(--dv-muted) !important;
        line-height: 1.45;
    }

    .dv-alert strong {
        display: block;
        color: var(--dv-ink) !important;
        margin-bottom: 0.15rem;
    }

    .dv-alert.quickstart {
        border-left: 4px solid var(--dv-teal);
    }

    .dv-alert.privacy {
        border-left: 4px solid var(--dv-amber);
    }

    .stButton > button,
    .stDownloadButton > button {
        border-radius: 10px;
        border: 1px solid #99f6e4;
        background: #ccfbf1;
        color: #134e4a !important;
        font-weight: 750;
        box-shadow: 0 10px 22px rgba(15, 118, 110, 0.12);
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover {
        border-color: #5eead4;
        background: #99f6e4;
        color: #0f172a !important;
        transform: translateY(-1px);
    }

    .stButton > button *,
    .stDownloadButton > button * {
        color: inherit !important;
    }

    .stButton > button:disabled,
    .stDownloadButton > button:disabled {
        background: #e2e8f0;
        border-color: #cbd5e1;
        color: #475569 !important;
        box-shadow: none;
    }

    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid var(--dv-line);
        border-radius: 12px;
        padding: 0.95rem 1rem;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
    }

    div[data-testid="stMetric"] * {
        color: var(--dv-ink) !important;
    }

    div[data-testid="stMetric"] label,
    div[data-testid="stMetric"] [data-testid="stMetricLabel"] * {
        color: var(--dv-muted) !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.35rem;
        background: #e2e8f0;
        padding: 0.35rem;
        border-radius: 12px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 9px;
        padding: 0.55rem 0.9rem;
        font-weight: 750;
        color: var(--dv-ink) !important;
    }

    .stTabs [aria-selected="true"] {
        background: #ffffff;
        box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
    }

    .stTabs [data-baseweb="tab"] *,
    .stTabs [aria-selected="true"] * {
        color: var(--dv-ink) !important;
    }

    input,
    textarea,
    [data-baseweb="input"] input,
    [data-baseweb="textarea"] textarea {
        color: var(--dv-ink) !important;
        background: #ffffff !important;
    }

    input::placeholder,
    textarea::placeholder {
        color: #64748b !important;
        opacity: 1 !important;
    }

    [data-testid="stFileUploader"] *,
    [data-testid="stDataFrame"] *,
    [data-testid="stDataEditor"] * {
        color: var(--dv-ink);
    }

    .dv-section-title {
        margin: 1.25rem 0 0.7rem;
        font-size: 1.2rem;
        font-weight: 850;
        color: var(--dv-ink);
    }

    .dv-decision-card {
        border: 1px solid var(--dv-line);
        border-radius: 14px;
        padding: 1.1rem;
        margin: 0.95rem 0;
        background: #ffffff;
        box-shadow: 0 14px 32px rgba(15, 23, 42, 0.06);
    }

    .dv-record-shell {
        border: 1px solid var(--dv-line);
        border-radius: 16px;
        padding: 1rem;
        background: #ffffff;
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.04);
        margin: 1rem 0;
    }

    .dv-actions-row {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.65rem;
        margin: 0.9rem 0;
    }

    .dv-decision-heading {
        display: flex;
        gap: 0.75rem;
        align-items: flex-start;
        margin-bottom: 0.75rem;
    }

    .dv-number {
        flex: 0 0 auto;
        width: 2rem;
        height: 2rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 999px;
        background: var(--dv-teal-soft);
        color: #115e59 !important;
        font-weight: 850;
    }

    .dv-decision-title {
        font-size: 1.12rem;
        font-weight: 850;
        color: var(--dv-ink) !important;
        line-height: 1.35;
    }

    .dv-chip-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin: 0.35rem 0 0.6rem;
    }

    .dv-chip {
        display: inline-flex;
        padding: 0.25rem 0.55rem;
        border-radius: 999px;
        background: #f1f5f9;
        color: #334155 !important;
        font-size: 0.78rem;
        font-weight: 750;
    }

    .dv-chip.high {
        background: #dcfce7;
        color: #166534 !important;
    }

    .dv-chip.ready {
        background: #d1fae5;
        color: #065f46 !important;
    }

    .dv-chip.medium {
        background: #fef3c7;
        color: #92400e !important;
    }

    .dv-chip.low {
        background: #fee2e2;
        color: #991b1b !important;
    }

    .dv-field-label {
        color: var(--dv-muted) !important;
        font-size: 0.77rem;
        font-weight: 800;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.2rem;
    }

    .dv-field-value {
        color: var(--dv-ink) !important;
        line-height: 1.45;
        margin-bottom: 0.6rem;
    }

    @media (max-width: 760px) {
        .dv-hero {
            padding: 1.35rem;
        }

        .dv-hero h1 {
            font-size: 2.1rem;
        }

        .dv-hero-grid,
        .dv-pipeline-row,
        .dv-card-grid,
        .dv-alert-row,
        .dv-actions-row {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="dv-appbar">
        <div class="dv-brand">DecisionVault AI</div>
        <div class="dv-appbar-meta">
            <span class="dv-mini-pill">Local vault storage</span>
            <span class="dv-mini-pill">Gemini extraction</span>
            <span class="dv-mini-pill">Review before save</span>
        </div>
    </div>
    <div class="dv-hero">
        <div class="dv-hero-grid">
            <div>
                <div class="dv-kicker">Decision Memory Layer</div>
                <h1>DecisionVault AI</h1>
                <p>
                    Convert scattered workplace communication into decision records with
                    rationale, ownership, approval context, evidence, and reusable memory.
                </p>
                <div class="dv-pipeline-row">
                    <div class="dv-pipeline-step">
                        <div class="dv-step-number">1</div>
                        <div class="dv-step-title">Add evidence</div>
                        <div class="dv-step-copy">Upload notes, threads, emails, markdown, or CSV exports.</div>
                    </div>
                    <div class="dv-pipeline-step">
                        <div class="dv-step-number">2</div>
                        <div class="dv-step-title">Extract decisions</div>
                        <div class="dv-step-copy">Generate structured records from messy source text.</div>
                    </div>
                    <div class="dv-pipeline-step">
                        <div class="dv-step-number">3</div>
                        <div class="dv-step-title">Review and reuse</div>
                        <div class="dv-step-copy">Edit records, save to the vault, export, and search later.</div>
                    </div>
                </div>
            </div>
            <div class="dv-hero-side">
                <div>
                    <div class="dv-side-label">Primary output</div>
                    <div class="dv-side-value">Reusable decision records</div>
                </div>
                <div>
                    <div class="dv-side-label">Evidence policy</div>
                    <div class="dv-side-value">Source-backed extraction</div>
                </div>
                <div>
                    <div class="dv-side-label">Human control</div>
                    <div class="dv-side-value">Editable before save</div>
                </div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

with st.sidebar:
    st.header("Workspace")
    st.caption("Decision extraction, review, and saved memory.")

    st.markdown("### Best-fit records")
    st.markdown(
        "- Launch or timeline choices\n"
        "- Vendor and tooling selections\n"
        "- Approval dependencies\n"
        "- Incident follow-ups\n"
        "- Project handoff decisions"
    )

    st.markdown("### Data note")
    st.info("Avoid sensitive or regulated data unless your Gemini/API setup is approved.")
    st.caption(
        "A production deployment should add authentication, database storage, "
        "access controls, and retention policy."
    )


# =========================
# API Setup
# =========================

def get_config_value(name, default=None):
    env_value = os.getenv(name)

    if env_value:
        return env_value

    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


API_KEY = get_config_value("GEMINI_API_KEY")

if not API_KEY:
    st.error("GEMINI_API_KEY not found. Please add it to your .env file.")
    st.stop()

try:
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    st.error(f"Failed to create Gemini client: {e}")
    st.stop()


# =========================
# Vault Storage Helpers
# =========================

VAULT_FILE = get_config_value("DECISION_VAULT_FILE", "decision_vault.json")
MAX_UPLOAD_FILE_SIZE_MB = int(
    get_config_value("MAX_UPLOAD_FILE_SIZE_MB", "2")
)
MAX_UPLOAD_FILE_SIZE_BYTES = MAX_UPLOAD_FILE_SIZE_MB * 1024 * 1024
MAX_TOTAL_UPLOAD_SIZE_MB = int(
    get_config_value("MAX_TOTAL_UPLOAD_SIZE_MB", "5")
)
MAX_TOTAL_UPLOAD_SIZE_BYTES = MAX_TOTAL_UPLOAD_SIZE_MB * 1024 * 1024


def convert_dataframe_to_excel(df):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="DecisionVault")

    return output.getvalue()


LIST_RECORD_FIELDS = [
    "dependencies_or_conditions",
    "follow_up_actions",
    "source_evidence"
]

EDITABLE_RECORD_FIELDS = [
    "decision",
    "decision_type",
    "reason",
    "owner",
    "approver",
    "affected_project_or_workflow",
    "dependencies_or_conditions",
    "follow_up_actions",
    "source_evidence",
    "confidence",
    "reusable_context"
]


def list_to_editor_text(value):
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if str(item).strip())

    return str(value or "")


def editor_text_to_list(value):
    return [
        line.strip()
        for line in str(value or "").splitlines()
        if line.strip()
    ]


def prepare_records_for_editor(records):
    editor_rows = []

    for record in records:
        editor_row = {}

        for field in EDITABLE_RECORD_FIELDS:
            value = record.get(field, "")
            if field in LIST_RECORD_FIELDS:
                value = list_to_editor_text(value)

            editor_row[field] = value

        editor_rows.append(editor_row)

    return pd.DataFrame(editor_rows, columns=EDITABLE_RECORD_FIELDS)


def records_from_editor(editor_df):
    edited_records = editor_df.to_dict(orient="records")

    for record in edited_records:
        for field in LIST_RECORD_FIELDS:
            record[field] = editor_text_to_list(record.get(field, ""))

    return enrich_records_for_ui(
        add_bayesian_confidence_to_records(edited_records)
    )


def confidence_chip_class(confidence):
    confidence = str(confidence or "").strip().lower()

    if confidence in {"high", "medium", "low"}:
        return confidence

    return ""


def quality_chip_class(level):
    level = str(level or "").strip().lower()

    if level == "ready":
        return "ready"

    if level == "review":
        return "medium"

    if level == "incomplete":
        return "low"

    return ""


def html_text(value):
    return html.escape(str(value if value is not None else "N/A"))


def save_decisions_to_vault(decision_records):
    return save_decisions_to_vault_file(decision_records, VAULT_FILE)


def delete_decision_from_vault(decision_id):
    return delete_decision_from_vault_file(decision_id, VAULT_FILE)


def load_vault():
    return load_vault_file(VAULT_FILE)


def save_vault(records):
    save_vault_file(records, VAULT_FILE)


def render_uploaded_file_list(files):
    file_summary = summarize_uploaded_files(files)
    rows = []

    for file in file_summary["files"]:
        rows.append(
            f"""
            <div class="dv-file-row">
                <span class="dv-file-name">{html_text(file["name"])}</span>
                <span class="dv-file-size">{html_text(file["size_label"])}</span>
            </div>
            """
        )

    st.markdown(
        f"""
        <div class="dv-file-list">
            {''.join(rows)}
        </div>
        """,
        unsafe_allow_html=True
    )


def get_vault_summary():
    saved_records = enrich_records_for_ui(
        add_bayesian_confidence_to_records(load_vault())
    )
    record_summary = summarize_records(saved_records)

    if not saved_records:
        return {
            "saved_count": 0,
            "active_count": 0,
            "needs_review_count": 0,
            "average_quality_score": 0
        }

    return {
        "saved_count": len(saved_records),
        "active_count": sum(
            1 for record in saved_records
            if record.get("status", "").lower() == "active"
        ),
        "needs_review_count": record_summary["review"] + record_summary["incomplete"],
        "average_quality_score": record_summary["average_quality_score"]
    }


def clear_current_session():
    st.session_state.pop("decision_result", None)
    st.session_state.pop("combined_text", None)


# =========================
# File Upload
# =========================

st.markdown(
    """
    <div class="dv-workspace-title">
        <div>
            <h2>Source Workspace</h2>
            <p>Add evidence on the left. Track saved decision memory on the right.</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

source_col, memory_col = st.columns([1.45, 1], gap="large")

with source_col:
    with st.container(border=True):
        st.markdown('<div class="dv-section-title">Source Evidence</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="dv-panel-note">
                <div class="dv-panel-note-title">Accepted files</div>
                <div class="dv-panel-note-copy">
                    Upload .txt, .md, or .csv files. Keep the total upload under the configured limit
                    and remove sensitive data before processing.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        uploaded_files = st.file_uploader(
            "Upload source files",
            type=["txt", "md", "csv"],
            accept_multiple_files=True,
            max_upload_size=MAX_UPLOAD_FILE_SIZE_MB,
            label_visibility="collapsed"
        )

        if uploaded_files:
            upload_summary = summarize_uploaded_files(uploaded_files)
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            metric_col1.metric("Files", upload_summary["count"])
            metric_col2.metric("Total Size", upload_summary["total_size_label"])
            metric_col3.metric("Limit", f"{MAX_TOTAL_UPLOAD_SIZE_MB} MB")
            render_uploaded_file_list(uploaded_files)
        else:
            st.markdown(
                """
                <div class="dv-empty-state">
                    <strong>No source files selected</strong>
                    <span>Use the uploader above to add meeting notes, threads, emails, or exports.</span>
                </div>
                """,
                unsafe_allow_html=True
            )

        action_col1, action_col2 = st.columns([1, 1])
        with action_col1:
            generate_clicked = st.button(
                "Generate Decision Memory",
                type="primary",
                use_container_width=True,
                disabled=not uploaded_files
            )
        with action_col2:
            clear_clicked = st.button(
                "Clear Current Session",
                use_container_width=True
            )

        if clear_clicked:
            clear_current_session()
            st.success("Current generated decision memory cleared.")

with memory_col:
    with st.container(border=True):
        st.markdown('<div class="dv-section-title">Vault Snapshot</div>', unsafe_allow_html=True)
        vault_summary = get_vault_summary()
        vault_col1, vault_col2 = st.columns(2)
        vault_col1.metric("Saved", vault_summary["saved_count"])
        vault_col2.metric("Active", vault_summary["active_count"])
        vault_col3, vault_col4 = st.columns(2)
        vault_col3.metric("Needs Review", vault_summary["needs_review_count"])
        vault_col4.metric("Quality", f'{vault_summary["average_quality_score"]}%')
        st.markdown(
            """
            <div class="dv-panel-note">
                <div class="dv-panel-note-title">How to use the vault</div>
                <div class="dv-panel-note-copy">
                    Generate records, review them, save the useful ones, then search across saved decisions
                    when the same workflow question comes back later.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


def read_uploaded_files(files):
    combined_text = ""
    validation_errors = []
    total_size = sum(get_file_size(file) for file in files)

    if total_size > MAX_TOTAL_UPLOAD_SIZE_BYTES:
        validation_errors.append(
            "Total upload size is too large. Max combined size is "
            f"{MAX_TOTAL_UPLOAD_SIZE_MB} MB."
        )

    for file in files:
        content, validation_error = validate_uploaded_file(
            file,
            MAX_UPLOAD_FILE_SIZE_BYTES,
            MAX_UPLOAD_FILE_SIZE_MB
        )

        if validation_error:
            validation_errors.append(validation_error)
            continue

        combined_text += f"\n\n--- SOURCE FILE: {file.name} ---\n"
        combined_text += content

    return combined_text, validation_errors


def extract_decisions(text):
    prompt = f"""
You are DecisionVault AI, a GenAI system that extracts structured business decisions
from messy workplace communication.

Your goal is NOT to list every sentence as a decision.

Your goal is to identify the main business decisions and organize supporting details
under each decision.

IMPORTANT RULES:

1. A "decision" is a final or agreed business choice.
   Examples:
   - Delay launch to next Friday
   - Choose Vendor B
   - Remove a feature from MVP
   - Pause deployment until approval

2. A "follow-up action" is NOT a separate decision unless it represents a new business choice.
   Example:
   - "Ramesh will update Jira" is a follow-up action, not a separate decision.

3. A "dependency" or "condition" is NOT a separate decision.
   Example:
   - "Finance approval is pending" is a dependency/reason, not a decision.

4. Group related details into one decision record when they belong to the same situation.

5. Prefer fewer, higher-quality decision records over many small records.

6. If something is only an update, blocker, or task, include it under the relevant decision as
   reason, dependency, follow-up, or evidence.

For each main decision, return:
- decision
- decision_type
- reason
- owner
- approver
- affected_project_or_workflow
- dependencies_or_conditions
- follow_up_actions
- source_evidence
- confidence
- reusable_context

Return ONLY valid JSON in this exact format:

{{
  "executive_summary": "short summary of the main decisions found",
  "decision_records": [
    {{
      "decision": "...",
      "decision_type": "Timeline Change / Approval / Scope Change / Vendor Choice / Process Exception / Deployment Condition / Other",
      "reason": "...",
      "owner": "...",
      "approver": "...",
      "affected_project_or_workflow": "...",
      "dependencies_or_conditions": ["..."],
      "follow_up_actions": ["..."],
      "source_evidence": ["..."],
      "confidence": "High/Medium/Low",
      "reusable_context": "..."
    }}
  ],
  "items_needing_human_review": [
    {{
      "item": "...",
      "why_review_needed": "..."
    }}
  ]
}}

Workplace text:
{text}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    raw_output = response.text or ""

    try:
        return extract_json_from_response(raw_output)
    except json.JSONDecodeError as e:
        raise GeminiJSONError(str(e), raw_output) from e


def ask_decision_vault(question, decision_records):
    prompt = f"""
You are DecisionVault AI.

You answer questions using ONLY the provided decision records.
Do not invent information that is not in the records.

If the answer is not available, say:
"That information is not available in the current decision memory."

Decision Records:
{json.dumps(decision_records, indent=2)}

User Question:
{question}

Give a clear, concise answer.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text


def display_saved_vault(key_prefix):
    saved_records = add_bayesian_confidence_to_records(load_vault())

    if saved_records:
        st.write(
            "These are decision records saved into the local DecisionVault memory file."
        )

        active_count = sum(
            1 for record in saved_records
            if record.get("status", "").lower() == "active"
        )
        high_confidence_count = sum(
            1 for record in saved_records
            if record.get("confidence", "").lower() == "high"
        )
        low_confidence_count = sum(
            1 for record in saved_records
            if record.get("confidence", "").lower() == "low"
        )
        average_bayes_score = round(
            sum(
                int(record.get("bayesian_confidence_score", 0))
                for record in saved_records
            ) / len(saved_records)
        )

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Saved Decisions", len(saved_records))
        col2.metric("Active", active_count)
        col3.metric("High Confidence", high_confidence_count)
        col4.metric("Needs Review", low_confidence_count)
        col5.metric("Avg Bayes Score", f"{average_bayes_score}%")

        st.markdown("### Search Saved Vault")
        saved_vault_question = st.text_input(
            "Ask a question about saved decisions",
            placeholder="Example: Have we handled finance approval delays before?",
            key=f"{key_prefix}_question"
        )

        if st.button("Search Saved Vault", key=f"{key_prefix}_search_button"):
            if not saved_vault_question.strip():
                st.warning("Please enter a question.")
            else:
                with st.spinner("Searching saved decision vault..."):
                    saved_answer = ask_decision_vault(
                        saved_vault_question,
                        saved_records
                    )

                st.markdown("### Saved Vault Answer")
                st.write(saved_answer)

        st.markdown("### Saved Records")
        saved_df = pd.DataFrame(saved_records)

        filter_col1, filter_col2, filter_col3 = st.columns(3)

        with filter_col1:
            keyword_filter = st.text_input(
                "Filter by keyword",
                placeholder="Search decision, reason, owner, project...",
                key=f"{key_prefix}_keyword_filter"
            )

        with filter_col2:
            confidence_options = ["All"]
            if "confidence" in saved_df.columns:
                confidence_options += sorted(
                    value for value in saved_df["confidence"].dropna().unique()
                    if value
                )

            selected_confidence = st.selectbox(
                "Filter by confidence",
                confidence_options,
                key=f"{key_prefix}_confidence_filter"
            )

        with filter_col3:
            project_options = ["All"]
            if "affected_project_or_workflow" in saved_df.columns:
                project_options += sorted(
                    value for value in saved_df["affected_project_or_workflow"].dropna().unique()
                    if value
                )

            selected_project = st.selectbox(
                "Filter by project/workflow",
                project_options,
                key=f"{key_prefix}_project_filter"
            )

        filtered_df = saved_df.copy()

        if keyword_filter.strip():
            keyword = keyword_filter.strip().lower()
            filtered_df = filtered_df[
                filtered_df.astype(str).apply(
                    lambda row: keyword in " ".join(row).lower(),
                    axis=1
                )
            ]

        if selected_confidence != "All" and "confidence" in filtered_df.columns:
            filtered_df = filtered_df[
                filtered_df["confidence"] == selected_confidence
            ]

        if selected_project != "All" and "affected_project_or_workflow" in filtered_df.columns:
            filtered_df = filtered_df[
                filtered_df["affected_project_or_workflow"] == selected_project
            ]

        st.dataframe(filtered_df, use_container_width=True)

        st.markdown("### Manage Saved Records")
        decision_options = [
            {
                "id": record.get("decision_id"),
                "label": (
                    f"{record.get('decision_id', 'No ID')} - "
                    f"{record.get('decision', 'Untitled decision')}"
                )
            }
            for record in saved_records
            if record.get("decision_id")
        ]

        if decision_options:
            selected_decision = st.selectbox(
                "Select a saved decision to delete",
                decision_options,
                format_func=lambda option: option["label"],
                key=f"{key_prefix}_delete_select"
            )

            if st.button(
                "Delete Selected Saved Decision",
                key=f"{key_prefix}_delete_button"
            ):
                deleted = delete_decision_from_vault(selected_decision["id"])

                if deleted:
                    st.success("Saved decision deleted.")
                    st.rerun()
                else:
                    st.warning("That saved decision could not be found.")

        saved_csv = saved_df.to_csv(index=False).encode("utf-8")
        saved_excel = convert_dataframe_to_excel(saved_df)
        filtered_csv = filtered_df.to_csv(index=False).encode("utf-8")
        filtered_excel = convert_dataframe_to_excel(filtered_df)

        st.download_button(
            label="Download Full Vault as CSV",
            data=saved_csv,
            file_name="saved_decision_vault.csv",
            mime="text/csv",
            key=f"{key_prefix}_download_button"
        )

        st.download_button(
            label="Download Full Vault as Excel",
            data=saved_excel,
            file_name="saved_decision_vault.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}_excel_download_button"
        )

        st.download_button(
            label="Download Filtered Vault as CSV",
            data=filtered_csv,
            file_name="filtered_decision_vault.csv",
            mime="text/csv",
            key=f"{key_prefix}_filtered_download_button"
        )

        st.download_button(
            label="Download Filtered Vault as Excel",
            data=filtered_excel,
            file_name="filtered_decision_vault.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}_filtered_excel_download_button"
        )

        if st.button("Clear Saved Vault", key=f"{key_prefix}_clear_button"):
            save_vault([])
            st.success("Saved vault cleared.")
            st.rerun()
    else:
        st.info(
            "No decisions saved yet. Generate decision records and click "
            "'Save Decision Records to Vault'."
        )


# =========================
# Generate Decision Memory
# =========================

if uploaded_files:
    combined_text, validation_errors = read_uploaded_files(uploaded_files)

    if validation_errors:
        st.error("Some uploaded files were rejected.")

        for validation_error in validation_errors:
            st.warning(validation_error)

        if not combined_text.strip():
            st.stop()

    if not combined_text.strip():
        st.warning("Uploaded files appear to be empty.")
        st.stop()

    if generate_clicked:
        with st.spinner("Extracting decision records using Gemini..."):
            try:
                result = extract_decisions(combined_text)
                result["decision_records"] = add_bayesian_confidence_to_records(
                    result.get("decision_records", [])
                )
                st.session_state["decision_result"] = result
                st.session_state["combined_text"] = combined_text
                st.success("Decision memory generated successfully!")

            except GeminiJSONError as e:
                st.error("Gemini returned text that was not valid JSON.")
                st.write("JSON error:", e)
                with st.expander("View raw Gemini response for debugging"):
                    st.text_area("Raw Gemini response", e.raw_response, height=300)
                st.write("Try clicking the button again.")

            except Exception as e:
                st.error(f"Something went wrong: {e}")

else:
    combined_text = ""
    if generate_clicked:
        st.warning("Upload one or more files before generating decision memory.")


# =========================
# Display Results
# =========================

if "decision_result" in st.session_state:
    result = st.session_state["decision_result"]
    combined_text = st.session_state.get("combined_text", "")

    decision_records = enrich_records_for_ui(
        add_bayesian_confidence_to_records(
            result.get("decision_records", [])
        )
    )
    result["decision_records"] = decision_records
    review_items = result.get("items_needing_human_review", [])
    record_summary = summarize_records(decision_records)
    total_followups = sum(
        len(record.get("follow_up_actions", []))
        for record in decision_records
    )
    human_review_count = len(review_items)

    st.markdown(
        """
        <div class="dv-workspace-title">
            <div>
                <h2>Decision Memory Review</h2>
                <p>Review generated records, edit fields, ask questions, and save durable context.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Records", record_summary["total"])
    col2.metric("Ready", record_summary["ready"])
    col3.metric("Needs Cleanup", record_summary["review"] + record_summary["incomplete"])
    col4.metric("Follow-ups", total_followups)
    col5.metric("Quality", f'{record_summary["average_quality_score"]}%')

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "Overview",
            "Review Records",
            "Ask",
            "Saved Vault",
            "Human Review",
            "Source Text"
        ]
    )

    # =========================
    # Tab 1: Summary
    # =========================

    with tab1:
        with st.container(border=True):
            st.markdown('<div class="dv-section-title">Executive Summary</div>', unsafe_allow_html=True)
            st.write(result.get("executive_summary", "No summary available."))

        overview_col1, overview_col2 = st.columns(2)
        with overview_col1:
            with st.container(border=True):
                st.markdown('<div class="dv-section-title">What Was Captured</div>', unsafe_allow_html=True)
                st.markdown(
                    "- Business choice\n"
                    "- Decision rationale\n"
                    "- Owner and approver context\n"
                    "- Workflow impact\n"
                    "- Dependencies and evidence"
                )
        with overview_col2:
            with st.container(border=True):
                st.markdown('<div class="dv-section-title">Next Step</div>', unsafe_allow_html=True)
                st.write(
                    "Open Review Records, clean up any extracted fields, then save the records "
                    "you want to keep in the local vault."
                )

    # =========================
    # Tab 2: Decision Records
    # =========================

    with tab2:
        st.markdown('<div class="dv-section-title">Decision Records</div>', unsafe_allow_html=True)

        if decision_records:
            st.markdown(
                '<div class="dv-section-title">Review and Edit Before Saving</div>',
                unsafe_allow_html=True
            )
            st.caption(
                "Edit any extracted fields before exporting or saving. For list fields, "
                "use one item per line."
            )
            edited_df = st.data_editor(
                prepare_records_for_editor(decision_records),
                use_container_width=True,
                num_rows="fixed",
                hide_index=True,
                key="decision_records_editor"
            )
            decision_records = records_from_editor(edited_df)

            for idx, record in enumerate(decision_records, 1):
                with st.container(border=True):
                    confidence = record.get("confidence", "N/A")
                    bayes_level = record.get("bayesian_confidence_level", "N/A")
                    chip_class = confidence_chip_class(confidence)
                    quality_level = record.get("record_quality_level", "Review")
                    quality_class = quality_chip_class(quality_level)
                    missing_fields = record.get("record_missing_fields", [])
                    st.markdown(
                        f"""
                        <div class="dv-decision-heading">
                            <div class="dv-number">{idx}</div>
                            <div>
                                <div class="dv-decision-title">{html_text(record.get('decision', 'N/A'))}</div>
                                <div class="dv-chip-row">
                                    <span class="dv-chip">{html_text(record.get('decision_type', 'Other'))}</span>
                                    <span class="dv-chip {chip_class}">Confidence: {html_text(confidence)}</span>
                                    <span class="dv-chip">Bayes: {html_text(record.get('bayesian_confidence_score', 'N/A'))}% ({html_text(bayes_level)})</span>
                                    <span class="dv-chip {quality_class}">Record: {html_text(quality_level)} · {html_text(record.get('record_quality_score', 0))}%</span>
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    if missing_fields:
                        st.warning(
                            "Missing review fields: "
                            + ", ".join(field.replace("_", " ") for field in missing_fields)
                        )

                    col_a, col_b = st.columns(2)

                    with col_a:
                        st.markdown(
                            f"""
                            <div class="dv-field-label">Reason</div>
                            <div class="dv-field-value">{html_text(record.get('reason', 'N/A'))}</div>
                            <div class="dv-field-label">Owner</div>
                            <div class="dv-field-value">{html_text(record.get('owner', 'N/A'))}</div>
                            <div class="dv-field-label">Approver</div>
                            <div class="dv-field-value">{html_text(record.get('approver', 'N/A'))}</div>
                            """,
                            unsafe_allow_html=True
                        )

                    with col_b:
                        st.markdown(
                            f"""
                            <div class="dv-field-label">Affected Project / Workflow</div>
                            <div class="dv-field-value">{html_text(record.get('affected_project_or_workflow', 'N/A'))}</div>
                            <div class="dv-field-label">Reusable Context</div>
                            <div class="dv-field-value">{html_text(record.get('reusable_context', 'N/A'))}</div>
                            """,
                            unsafe_allow_html=True
                        )

                        bayes_factors = record.get("bayesian_confidence_factors", [])
                        if bayes_factors:
                            with st.expander("Why this Bayesian score?"):
                                for factor in bayes_factors:
                                    st.markdown(f"- {factor}")

                    dependencies = record.get("dependencies_or_conditions", [])
                    followups = record.get("follow_up_actions", [])
                    evidence = record.get("source_evidence", [])

                    detail_col1, detail_col2, detail_col3 = st.columns(3)
                    with detail_col1:
                        st.markdown("**Dependencies / Conditions**")
                        if dependencies:
                            for dep in dependencies:
                                st.markdown(f"- {dep}")
                        else:
                            st.markdown("- N/A")

                    with detail_col2:
                        st.markdown("**Follow-up Actions**")
                        if followups:
                            for action in followups:
                                st.markdown(f"- {action}")
                        else:
                            st.markdown("- N/A")

                    with detail_col3:
                        st.markdown("**Source Evidence**")
                        if evidence:
                            for src in evidence:
                                st.markdown(f"- {src}")
                        else:
                            st.markdown("- N/A")

            df = pd.DataFrame(decision_records)
            csv = df.to_csv(index=False).encode("utf-8")
            excel = convert_dataframe_to_excel(df)

            save_col, csv_col, excel_col = st.columns(3)

            with save_col:
                save_clicked = st.button(
                    "Save Reviewed Records",
                    type="primary",
                    use_container_width=True
                )
            with csv_col:
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="decision_records.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with excel_col:
                st.download_button(
                    label="Download Excel",
                    data=excel,
                    file_name="decision_records.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

            if save_clicked:
                saved_count, duplicate_count, duplicate_records = save_decisions_to_vault(
                    decision_records
                )

                if saved_count:
                    st.success(f"Saved {saved_count} decision record(s) to DecisionVault.")

                if duplicate_count:
                    st.warning(
                        f"Skipped {duplicate_count} duplicate decision record(s). "
                        "Duplicates are checked using decision text and affected project/workflow."
                    )

                    with st.expander("View skipped duplicate decisions"):
                        for duplicate in duplicate_records:
                            st.markdown(f"- {duplicate.get('decision', 'N/A')}")

        else:
            st.warning("No clear decisions were found.")

    # =========================
    # Tab 3: Ask DecisionVault
    # =========================

    with tab3:
        st.subheader("Ask DecisionVault")

        st.write(
            "Ask questions about the extracted decision memory. "
            "DecisionVault will answer using only the decision records generated from your uploaded files."
        )

        user_question = st.text_input(
            "Ask a question",
            placeholder="Example: Why was the launch delayed?"
        )

        if st.button("Ask DecisionVault"):
            if not user_question.strip():
                st.warning("Please enter a question.")
            elif not decision_records:
                st.warning("No decision records available yet.")
            else:
                with st.spinner("Searching decision memory..."):
                    answer = ask_decision_vault(user_question, decision_records)

                st.markdown("### Answer")
                st.write(answer)

    # =========================
    # Tab 4: Saved Vault
    # =========================

    with tab4:
        st.subheader("Saved Decision Vault")
        display_saved_vault("tab_saved_vault")

    # =========================
    # Tab 5: Human Review
    # =========================

    with tab5:
        st.subheader("Items Needing Human Review")

        if review_items:
            for item in review_items:
                st.markdown(f"**Item:** {item.get('item', 'N/A')}")
                st.markdown(f"**Why Review Needed:** {item.get('why_review_needed', 'N/A')}")
                st.divider()
        else:
            st.success("No human review items detected.")

    # =========================
    # Tab 6: Raw Input
    # =========================

    with tab6:
        st.subheader("Uploaded Source Content")

        with st.expander("View combined uploaded content", expanded=False):
            st.text_area("Combined input", combined_text, height=400)

else:
    st.markdown("---")
    st.subheader("Saved Decision Vault")
    display_saved_vault("standalone_saved_vault")


# =========================
# Footer
# =========================

st.markdown("---")
st.markdown("""
### What DecisionVault AI does

DecisionVault AI does not just summarize conversations.

It extracts:

- what was decided
- why it was decided
- who owns the follow-up
- what workflow it affects
- whether the decision can be reused later
""")
