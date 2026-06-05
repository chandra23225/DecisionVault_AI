import os
import json
import re
from io import BytesIO
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google import genai


# =========================
# App Setup
# =========================

load_dotenv()

st.set_page_config(
    page_title="DecisionVault AI",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 DecisionVault AI")
st.subheader("GenAI-powered Decision Memory Layer for Teams and AI Agents")

st.write(
    "Upload workplace conversations, meeting notes, emails, or project notes. "
    "DecisionVault AI will extract structured decision records."
)

st.info(
    "Demo tip: try uploading meeting_notes.txt, slack_thread.txt, and "
    "email_thread.txt together. For more realistic demos, use the anonymized "
    "files in the sample_data folder."
)

st.warning(
    "Privacy note: avoid uploading confidential or regulated data unless your "
    "Gemini/API setup is approved for that use."
)


# =========================
# API Setup
# =========================

API_KEY = os.getenv("GEMINI_API_KEY")

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

VAULT_FILE = "decision_vault.json"


class GeminiJSONError(Exception):
    def __init__(self, message, raw_response):
        super().__init__(message)
        self.raw_response = raw_response


def load_vault():
    if not os.path.exists(VAULT_FILE):
        return []

    try:
        with open(VAULT_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return []


def save_vault(records):
    with open(VAULT_FILE, "w", encoding="utf-8") as file:
        json.dump(records, file, indent=2)


def generate_decision_id(existing_records):
    highest_number = 0

    for record in existing_records:
        decision_id = str(record.get("decision_id", ""))
        match = re.match(r"DV-(\d+)$", decision_id)

        if match:
            highest_number = max(highest_number, int(match.group(1)))

    next_number = highest_number + 1
    return f"DV-{next_number:03d}"


def convert_dataframe_to_excel(df):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="DecisionVault")

    return output.getvalue()


def normalize_for_duplicate_check(value):
    return str(value or "").strip().lower()


def get_duplicate_key(record):
    decision_text = normalize_for_duplicate_check(record.get("decision"))
    affected_area = normalize_for_duplicate_check(
        record.get("affected_project_or_workflow")
    )
    return (decision_text, affected_area)


def save_decisions_to_vault(decision_records):
    existing_records = load_vault()
    existing_keys = {
        get_duplicate_key(record)
        for record in existing_records
    }

    saved_count = 0
    duplicate_count = 0
    duplicate_records = []

    for record in decision_records:
        duplicate_key = get_duplicate_key(record)

        if duplicate_key in existing_keys:
            duplicate_count += 1
            duplicate_records.append(record)
            continue

        new_record = record.copy()

        new_record["decision_id"] = generate_decision_id(existing_records)
        new_record["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_record["status"] = "Active"

        existing_records.append(new_record)
        existing_keys.add(duplicate_key)
        saved_count += 1

    save_vault(existing_records)

    return saved_count, duplicate_count, duplicate_records


def clear_current_session():
    st.session_state.pop("decision_result", None)
    st.session_state.pop("combined_text", None)


# =========================
# File Upload
# =========================

uploaded_files = st.file_uploader(
    "Upload text files",
    type=["txt", "md", "csv"],
    accept_multiple_files=True
)

if st.button("Clear current session"):
    clear_current_session()
    st.success("Current generated decision memory cleared.")


def read_uploaded_files(files):
    combined_text = ""

    for file in files:
        try:
            content = file.read().decode("utf-8", errors="ignore")
            combined_text += f"\n\n--- SOURCE FILE: {file.name} ---\n"
            combined_text += content
        except Exception as e:
            st.error(f"Could not read {file.name}: {e}")

    return combined_text


# =========================
# Gemini Helpers
# =========================

def extract_json_from_response(raw_text):
    raw_text = raw_text.strip()

    if raw_text.startswith("```json"):
        raw_text = raw_text.replace("```json", "", 1).strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.replace("```", "", 1).strip()

    if raw_text.endswith("```"):
        raw_text = raw_text[:-3].strip()

    return json.loads(raw_text)


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
        contents=prompt
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
    saved_records = load_vault()

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

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Saved Decisions", len(saved_records))
        col2.metric("Active", active_count)
        col3.metric("High Confidence", high_confidence_count)
        col4.metric("Needs Review", low_confidence_count)

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
            st.success("Saved vault cleared. Refresh the page to update.")
    else:
        st.info(
            "No decisions saved yet. Generate decision records and click "
            "'Save Decision Records to Vault'."
        )


# =========================
# Generate Decision Memory
# =========================

if uploaded_files:
    combined_text = read_uploaded_files(uploaded_files)

    if not combined_text.strip():
        st.warning("Uploaded files appear to be empty.")
        st.stop()

    if st.button("Generate Decision Memory"):
        with st.spinner("Extracting decision records using Gemini..."):
            try:
                result = extract_decisions(combined_text)
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
    st.info("Upload one or more files to begin.")


# =========================
# Display Results
# =========================

if "decision_result" in st.session_state:
    result = st.session_state["decision_result"]
    combined_text = st.session_state.get("combined_text", "")

    decision_records = result.get("decision_records", [])
    review_items = result.get("items_needing_human_review", [])

    total_decisions = len(decision_records)
    high_confidence = sum(
        1 for record in decision_records
        if record.get("confidence", "").lower() == "high"
    )
    total_followups = sum(
        len(record.get("follow_up_actions", []))
        for record in decision_records
    )
    human_review_count = len(review_items)

    st.markdown("---")
    st.subheader("Decision Memory Overview")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Decisions", total_decisions)
    col2.metric("High Confidence", high_confidence)
    col3.metric("Follow-up Actions", total_followups)
    col4.metric("Human Review Items", human_review_count)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "Summary",
            "Decision Records",
            "Ask DecisionVault",
            "Saved Vault",
            "Human Review",
            "Raw Input"
        ]
    )

    # =========================
    # Tab 1: Summary
    # =========================

    with tab1:
        st.subheader("Executive Summary")
        st.write(result.get("executive_summary", "No summary available."))

        st.markdown("### What this means")
        st.write(
            "DecisionVault AI has extracted structured decision memory from messy workplace communication. "
            "These records can later be reused by teams or AI agents to understand what was decided, why it was decided, "
            "who owns the next step, and what context should be remembered."
        )

    # =========================
    # Tab 2: Decision Records
    # =========================

    with tab2:
        st.subheader("Decision Records")

        if decision_records:
            for idx, record in enumerate(decision_records, 1):
                st.markdown(f"### Decision {idx}: {record.get('decision', 'N/A')}")

                col_a, col_b = st.columns(2)

                with col_a:
                    st.markdown(f"**Type:** {record.get('decision_type', 'N/A')}")
                    st.markdown(f"**Reason:** {record.get('reason', 'N/A')}")
                    st.markdown(f"**Owner:** {record.get('owner', 'N/A')}")
                    st.markdown(f"**Approver:** {record.get('approver', 'N/A')}")
                    st.markdown(
                        f"**Affected Project/Workflow:** "
                        f"{record.get('affected_project_or_workflow', 'N/A')}"
                    )

                with col_b:
                    st.markdown(f"**Confidence:** {record.get('confidence', 'N/A')}")
                    st.markdown(f"**Reusable Context:** {record.get('reusable_context', 'N/A')}")

                dependencies = record.get("dependencies_or_conditions", [])
                followups = record.get("follow_up_actions", [])
                evidence = record.get("source_evidence", [])

                st.markdown("**Dependencies / Conditions:**")
                if dependencies:
                    for dep in dependencies:
                        st.markdown(f"- {dep}")
                else:
                    st.markdown("- N/A")

                st.markdown("**Follow-up Actions:**")
                if followups:
                    for action in followups:
                        st.markdown(f"- {action}")
                else:
                    st.markdown("- N/A")

                st.markdown("**Source Evidence:**")
                if evidence:
                    for src in evidence:
                        st.markdown(f"- {src}")
                else:
                    st.markdown("- N/A")

                st.divider()

            df = pd.DataFrame(decision_records)
            csv = df.to_csv(index=False).encode("utf-8")
            excel = convert_dataframe_to_excel(df)

            st.download_button(
                label="Download Current Decision Records as CSV",
                data=csv,
                file_name="decision_records.csv",
                mime="text/csv"
            )

            st.download_button(
                label="Download Current Decision Records as Excel",
                data=excel,
                file_name="decision_records.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.markdown("---")

            if st.button("Save Decision Records to Vault"):
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
