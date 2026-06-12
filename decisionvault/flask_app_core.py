import csv
import io
import json
from pathlib import Path

import pandas as pd
from flask import Flask, redirect, render_template, request, send_file, url_for

from decisionvault.confidence import add_bayesian_confidence_to_records
from decisionvault.config import get_config_value, get_int_config_value, is_placeholder_config_value
from decisionvault.extraction import (
    ask_decision_vault_with_client,
    create_gemini_client,
    extract_decisions_with_client,
)
from decisionvault.gemini_helpers import GeminiAPIError, GeminiJSONError
from decisionvault.storage import (
    delete_decision_from_vault,
    load_vault,
    save_decisions_to_vault,
    save_vault,
)
from decisionvault.validation import validate_uploaded_file
from decisionvault.view_models import enrich_records_for_ui, summarize_records


APP_DIR = Path(__file__).resolve().parent
VAULT_FILE = get_config_value("DECISION_VAULT_FILE", str(APP_DIR / "decision_vault.json"))
MAX_UPLOAD_FILE_SIZE_MB = get_int_config_value("MAX_UPLOAD_FILE_SIZE_MB", 2)
MAX_UPLOAD_FILE_SIZE_BYTES = MAX_UPLOAD_FILE_SIZE_MB * 1024 * 1024
MAX_TOTAL_UPLOAD_SIZE_MB = get_int_config_value("MAX_TOTAL_UPLOAD_SIZE_MB", 5)
MAX_TOTAL_UPLOAD_SIZE_BYTES = MAX_TOTAL_UPLOAD_SIZE_MB * 1024 * 1024

app = Flask(__name__)
app.secret_key = get_config_value("FLASK_SECRET_KEY", "decisionvault-local-dev")

current_state = {
    "result": None,
    "combined_text": "",
    "answer": None,
    "last_question": "",
    "message": "",
    "error": "",
}


class UploadedFileAdapter:
    def __init__(self, storage):
        self.name = storage.filename
        self.type = storage.mimetype
        self._data = storage.read()
        self.size = len(self._data)

    def getvalue(self):
        return self._data


def get_client():
    api_key = get_config_value("GEMINI_API_KEY")

    if not api_key or is_placeholder_config_value(api_key):
        raise RuntimeError("GEMINI_API_KEY is missing or still a placeholder. Add a real key to .env first.")

    return create_gemini_client(api_key)


def get_current_records():
    result = current_state.get("result") or {}
    return enrich_records_for_ui(
        add_bayesian_confidence_to_records(result.get("decision_records", []))
    )


def parse_list_field(value):
    if not value:
        return []

    return [
        item.strip()
        for item in str(value).splitlines()
        if item.strip()
    ]


def parse_records_from_form(form):
    total_records = int(form.get("record_count", "0") or 0)
    records = []

    for index in range(total_records):
        records.append({
            "decision": form.get(f"decision_{index}", ""),
            "decision_type": form.get(f"decision_type_{index}", ""),
            "reason": form.get(f"reason_{index}", ""),
            "owner": form.get(f"owner_{index}", ""),
            "approver": form.get(f"approver_{index}", ""),
            "affected_project_or_workflow": form.get(f"workflow_{index}", ""),
            "dependencies_or_conditions": parse_list_field(form.get(f"dependencies_{index}", "")),
            "follow_up_actions": parse_list_field(form.get(f"followups_{index}", "")),
            "source_evidence": parse_list_field(form.get(f"evidence_{index}", "")),
            "confidence": form.get(f"confidence_{index}", ""),
            "reusable_context": form.get(f"reusable_context_{index}", ""),
        })

    return enrich_records_for_ui(add_bayesian_confidence_to_records(records))


def update_current_records(records):
    result = current_state.get("result") or {}
    result["decision_records"] = records
    current_state["result"] = result


def read_uploaded_files(files):
    validation_errors = []
    combined_text = ""
    adapters = [
        UploadedFileAdapter(file)
        for file in files
        if file and file.filename
    ]
    total_size = sum(file.size for file in adapters)

    if total_size > MAX_TOTAL_UPLOAD_SIZE_BYTES:
        validation_errors.append(
            "Total upload size is too large. Max combined size is "
            f"{MAX_TOTAL_UPLOAD_SIZE_MB} MB."
        )

    for file in adapters:
        content, validation_error = validate_uploaded_file(
            file,
            MAX_UPLOAD_FILE_SIZE_BYTES,
            MAX_UPLOAD_FILE_SIZE_MB,
        )

        if validation_error:
            validation_errors.append(validation_error)
            continue

        combined_text += f"\n\n--- SOURCE FILE: {file.name} ---\n"
        combined_text += content

    return combined_text, validation_errors


def build_page_context(active_view="extract"):
    records = get_current_records()
    saved_records = enrich_records_for_ui(add_bayesian_confidence_to_records(load_vault(VAULT_FILE)))
    result = current_state.get("result") or {}

    return {
        "result": result,
        "records": records,
        "record_summary": summarize_records(records),
        "review_items": result.get("items_needing_human_review", []),
        "combined_text": current_state.get("combined_text", ""),
        "saved_records": saved_records,
        "saved_summary": summarize_records(saved_records),
        "answer": current_state.get("answer", ""),
        "last_question": current_state.get("last_question", ""),
        "message": current_state.get("message", ""),
        "error": current_state.get("error", ""),
        "max_upload_mb": MAX_UPLOAD_FILE_SIZE_MB,
        "max_total_upload_mb": MAX_TOTAL_UPLOAD_SIZE_MB,
        "active_view": active_view,
    }


@app.route("/", methods=["GET"])
@app.route("/extract", methods=["GET"])
def index():
    return render_template("index.html", **build_page_context("extract"))


@app.route("/review", methods=["GET"])
def review_page():
    return render_template("index.html", **build_page_context("review"))


@app.route("/ask", methods=["GET"])
def ask_page():
    return render_template("index.html", **build_page_context("ask"))


@app.route("/vault", methods=["GET"])
def vault_page():
    return render_template("index.html", **build_page_context("vault"))


@app.route("/extract", methods=["POST"])
def extract():
    current_state["message"] = ""
    current_state["error"] = ""
    current_state["answer"] = ""
    current_state["last_question"] = ""

    combined_text, validation_errors = read_uploaded_files(request.files.getlist("source_files"))

    if validation_errors and not combined_text.strip():
        current_state["error"] = " ".join(validation_errors)
        return redirect(url_for("index"))

    if not combined_text.strip():
        current_state["error"] = "Upload at least one readable source file."
        return redirect(url_for("index"))

    try:
        result = extract_decisions_with_client(get_client(), combined_text)
        result["decision_records"] = enrich_records_for_ui(
            add_bayesian_confidence_to_records(result.get("decision_records", []))
        )
        current_state["result"] = result
        current_state["combined_text"] = combined_text
        current_state["message"] = "Decision memory generated."

        if validation_errors:
            current_state["error"] = "Some files were skipped: " + " ".join(validation_errors)
    except GeminiAPIError as e:
        current_state["error"] = f"Gemini request failed: {e}"
    except GeminiJSONError as e:
        current_state["error"] = f"Gemini returned invalid JSON: {e}"
    except Exception as e:
        current_state["error"] = str(e)

    if current_state.get("result"):
        return redirect(url_for("review_page"))

    return redirect(url_for("index"))


@app.route("/save-current", methods=["POST"])
def save_current():
    records = parse_records_from_form(request.form)
    update_current_records(records)
    saved_count, duplicate_count, _ = save_decisions_to_vault(records, VAULT_FILE)
    current_state["message"] = f"Saved {saved_count} record(s). Skipped {duplicate_count} duplicate(s)."
    current_state["error"] = ""
    return redirect(url_for("vault_page"))


@app.route("/update-current", methods=["POST"])
def update_current():
    records = parse_records_from_form(request.form)
    update_current_records(records)
    current_state["message"] = "Current records updated."
    current_state["error"] = ""
    return redirect(url_for("review_page"))


@app.route("/ask", methods=["POST"])
def ask_question():
    records = parse_records_from_form(request.form) if request.form.get("record_count") else get_current_records()
    update_current_records(records)
    question = request.form.get("question", "").strip()

    if not question:
        current_state["error"] = "Enter a question before asking DecisionVault."
        return redirect(url_for("ask_page"))

    try:
        current_state["answer"] = ask_decision_vault_with_client(get_client(), question, records)
        current_state["last_question"] = question
        current_state["message"] = ""
        current_state["error"] = ""
    except GeminiAPIError as e:
        current_state["error"] = f"Gemini request failed: {e}"
    except Exception as e:
        current_state["error"] = str(e)

    return redirect(url_for("ask_page"))


@app.route("/delete/<decision_id>", methods=["POST"])
def delete_saved(decision_id):
    deleted = delete_decision_from_vault(decision_id, VAULT_FILE)
    current_state["message"] = "Saved decision deleted." if deleted else "Saved decision was not found."
    current_state["error"] = ""
    return redirect(url_for("vault_page"))


@app.route("/clear-current", methods=["POST"])
def clear_current():
    current_state["result"] = None
    current_state["combined_text"] = ""
    current_state["answer"] = None
    current_state["last_question"] = ""
    current_state["message"] = "Current workspace cleared."
    current_state["error"] = ""
    return redirect(url_for("index"))


@app.route("/clear-vault", methods=["POST"])
def clear_vault():
    save_vault([], VAULT_FILE)
    current_state["message"] = "Saved vault cleared."
    current_state["error"] = ""
    return redirect(url_for("vault_page"))


def records_to_csv_bytes(records):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=sorted({key for record in records for key in record.keys()}))
    writer.writeheader()
    writer.writerows(records)
    return io.BytesIO(output.getvalue().encode("utf-8"))


def records_to_excel_bytes(records):
    output = io.BytesIO()
    pd.DataFrame(records).to_excel(output, index=False, sheet_name="DecisionVault")
    output.seek(0)
    return output


@app.route("/export/<scope>/<file_type>")
def export_records(scope, file_type):
    records = get_current_records() if scope == "current" else load_vault(VAULT_FILE)

    if file_type == "csv":
        return send_file(
            records_to_csv_bytes(records),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"{scope}_decision_records.csv",
        )

    return send_file(
        records_to_excel_bytes(records),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"{scope}_decision_records.xlsx",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=True)
