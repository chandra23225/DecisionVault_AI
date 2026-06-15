import unittest

from decisionvault.view_models import (
    enrich_records_for_ui,
    filter_records_for_vault,
    format_bytes,
    format_missing_field_warning,
    generate_example_questions,
    get_record_quality,
    summarize_records,
)


class ViewModelTests(unittest.TestCase):
    def test_format_bytes_uses_human_readable_units(self):
        self.assertEqual(format_bytes(12), "12 B")
        self.assertEqual(format_bytes(2048), "2.0 KB")
        self.assertEqual(format_bytes(2 * 1024 * 1024), "2.0 MB")

    def test_record_quality_flags_missing_fields(self):
        quality = get_record_quality({
            "decision": "Delay launch",
            "reason": "Approval pending",
            "owner": "",
            "approver": "Product Lead",
            "affected_project_or_workflow": "Payments",
            "source_evidence": []
        })

        self.assertEqual(quality["level"], "Review")
        self.assertIn("owner", quality["missing_fields"])
        self.assertIn("source_evidence", quality["missing_fields"])

    def test_enrich_records_adds_quality_fields(self):
        records = enrich_records_for_ui([
            {
                "decision": "Choose Vendor B",
                "reason": "Lower support risk",
                "owner": "Ops Lead",
                "approver": "Finance Lead",
                "affected_project_or_workflow": "Procurement",
                "source_evidence": ["Finance approved Vendor B"]
            }
        ])

        self.assertEqual(records[0]["record_quality_level"], "Ready")
        self.assertEqual(records[0]["record_missing_fields"], [])

    def test_enrich_records_adds_friendly_missing_field_warning(self):
        records = enrich_records_for_ui([
            {
                "decision": "Migrate backend service to FastAPI",
                "reason": "Improve backend performance",
                "owner": "Meera",
                "approver": "None",
                "affected_project_or_workflow": "Backend migration",
                "source_evidence": ["Team agreed to migrate backend service"]
            }
        ])

        self.assertEqual(
            records[0]["record_missing_field_warning"],
            "Needs review: approver not found",
        )

    def test_format_missing_field_warning_uses_readable_labels(self):
        self.assertEqual(
            format_missing_field_warning(["source_evidence", "affected_project_or_workflow"]),
            "Needs review: source evidence and workflow not found",
        )

    def test_enrich_records_adds_friendly_input_values_and_placeholders(self):
        records = enrich_records_for_ui([
            {
                "decision": "Delay mobile launch",
                "reason": "None",
                "owner": "unknown",
                "approver": "None",
                "affected_project_or_workflow": "",
                "source_evidence": []
            }
        ])

        form_fields = records[0]["form_fields"]

        self.assertEqual(form_fields["owner"]["value"], "")
        self.assertEqual(form_fields["owner"]["placeholder"], "Owner not found")
        self.assertEqual(form_fields["approver"]["value"], "")
        self.assertEqual(form_fields["approver"]["placeholder"], "Approver not found")
        self.assertEqual(form_fields["workflow"]["placeholder"], "Workflow not found")

    def test_generate_example_questions_uses_current_records(self):
        questions = generate_example_questions([
            {
                "decision": "Delay mobile launch",
                "owner": "Priya",
                "approver": "",
                "affected_project_or_workflow": "Mobile App"
            }
        ])

        self.assertIn("What were the main decisions?", questions)
        self.assertIn("What follow-ups does Priya own?", questions)
        self.assertIn("What approvals are missing?", questions)
        self.assertIn("What decisions affect Mobile App?", questions)

    def test_filter_records_for_vault_matches_query_and_status(self):
        records = [
            {
                "decision": "Delay mobile launch",
                "owner": "Priya",
                "status": "Pending Approval",
                "affected_project_or_workflow": "Mobile App",
            },
            {
                "decision": "Migrate backend",
                "owner": "Meera",
                "status": "Completed",
                "affected_project_or_workflow": "Backend",
            },
        ]

        filtered = filter_records_for_vault(records, query="mobile", status="Pending Approval")

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["decision"], "Delay mobile launch")

    def test_summarize_records_counts_quality_levels(self):
        summary = summarize_records([
            {
                "decision": "Choose Vendor B",
                "reason": "Lower support risk",
                "owner": "Ops Lead",
                "approver": "Finance Lead",
                "affected_project_or_workflow": "Procurement",
                "source_evidence": ["Finance approved Vendor B"],
                "bayesian_confidence_score": 90
            },
            {
                "decision": "Delay launch",
                "reason": "",
                "owner": "",
                "approver": "",
                "affected_project_or_workflow": "Payments",
                "source_evidence": [],
                "bayesian_confidence_score": 40
            }
        ])

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["ready"], 1)
        self.assertEqual(summary["incomplete"], 1)
        self.assertEqual(summary["average_bayes_score"], 65)


if __name__ == "__main__":
    unittest.main()
