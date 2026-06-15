import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from decisionvault import flask_app_core
from decisionvault.gemini_helpers import GeminiAPIError
from decisionvault.storage import load_vault


def make_form_record(index, **overrides):
    record = {
        f"decision_{index}": "Delay launch",
        f"decision_type_{index}": "Timeline Change",
        f"reason_{index}": "Approval pending",
        f"owner_{index}": "Priya",
        f"approver_{index}": "Rohan",
        f"workflow_{index}": "Mobile App",
        f"dependencies_{index}": "",
        f"followups_{index}": "",
        f"evidence_{index}": "Rohan approved delay",
        f"confidence_{index}": "High",
        f"reusable_context_{index}": "",
    }
    record.update(overrides)
    return record


class FlaskAppCoreTests(unittest.TestCase):
    def setUp(self):
        flask_app_core.app.config["TESTING"] = True
        self.client = flask_app_core.app.test_client()
        flask_app_core.current_state.update({
            "result": None,
            "combined_text": "",
            "answer": None,
            "last_question": "",
            "message": "",
            "error": "",
        })

    def test_save_ready_saves_only_ready_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_file = str(Path(temp_dir) / "vault.json")
            form_data = {"record_count": "2"}
            form_data.update(make_form_record(0, decision_0="Ready decision"))
            form_data.update(make_form_record(
                1,
                decision_1="Incomplete decision",
                approver_1="",
                evidence_1="",
            ))

            with patch.object(flask_app_core, "VAULT_FILE", vault_file):
                response = self.client.post("/save-ready", data=form_data)

            saved_records = load_vault(vault_file)

            self.assertEqual(response.status_code, 302)
            self.assertEqual(len(saved_records), 1)
            self.assertEqual(saved_records[0]["decision"], "Ready decision")

    def test_extract_no_decisions_returns_to_extract_with_clear_message(self):
        with patch.object(
            flask_app_core,
            "read_uploaded_files",
            return_value=("meeting notes without a final decision", []),
        ), patch.object(
            flask_app_core,
            "get_client",
            return_value=object(),
        ), patch.object(
            flask_app_core,
            "extract_decisions_with_client",
            return_value={
                "executive_summary": "The team discussed launch readiness.",
                "decision_records": [],
                "items_needing_human_review": [],
            },
        ):
            response = self.client.post("/extract", data={})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/extract")
        self.assertIn("No clear business decisions found", flask_app_core.current_state["error"])

    def test_extract_displays_friendly_gemini_error_without_duplicate_prefix(self):
        friendly_message = "Gemini is temporarily overloaded. Please wait a minute and try again."

        with patch.object(
            flask_app_core,
            "read_uploaded_files",
            return_value=("meeting notes", []),
        ), patch.object(
            flask_app_core,
            "get_client",
            return_value=object(),
        ), patch.object(
            flask_app_core,
            "extract_decisions_with_client",
            side_effect=GeminiAPIError(friendly_message),
        ):
            response = self.client.post("/extract", data={})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(flask_app_core.current_state["error"], friendly_message)

    def test_export_empty_current_records_redirects_with_message(self):
        response = self.client.get("/export/current/csv")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/extract")
        self.assertIn("No current records to export", flask_app_core.current_state["error"])

    def test_export_empty_saved_records_redirects_with_message(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_file = str(Path(temp_dir) / "vault.json")

            with patch.object(flask_app_core, "VAULT_FILE", vault_file):
                response = self.client.get("/export/saved/csv")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/vault")
        self.assertIn("No saved records to export", flask_app_core.current_state["error"])

    def test_extract_page_renders_user_clarity_labels(self):
        response = self.client.get("/extract")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Upload", html)
        self.assertIn("Review", html)
        self.assertIn("Ask", html)
        self.assertIn("Save", html)
        self.assertIn("Current workspace is temporary", html)
        self.assertIn("Saved vault is long-term memory", html)

    def test_review_page_renders_ai_confidence_and_completeness_labels(self):
        flask_app_core.current_state["result"] = {
            "executive_summary": "Launch readiness was discussed.",
            "decision_records": [
                {
                    "decision": "Delay launch",
                    "decision_type": "Timeline Change",
                    "reason": "Approval pending",
                    "owner": "Priya",
                    "approver": "Rohan",
                    "affected_project_or_workflow": "Mobile App",
                    "source_evidence": ["Rohan approved delay"],
                    "confidence": "High",
                }
            ],
        }

        response = self.client.get("/review")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI confidence", html)
        self.assertIn("Completeness", html)
        self.assertIn("View original uploaded text used by AI", html)


if __name__ == "__main__":
    unittest.main()
