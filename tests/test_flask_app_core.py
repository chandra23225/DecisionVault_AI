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


if __name__ == "__main__":
    unittest.main()
