import unittest

from decisionvault.view_models import (
    enrich_records_for_ui,
    format_bytes,
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
