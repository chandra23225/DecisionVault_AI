import unittest

from decisionvault.confidence import (
    calculate_bayesian_confidence,
    get_duplicate_key,
)


class ConfidenceTests(unittest.TestCase):
    def test_duplicate_key_normalizes_decision_and_workflow(self):
        record = {
            "decision": " Delay Launch ",
            "affected_project_or_workflow": " Payments MVP "
        }

        self.assertEqual(get_duplicate_key(record), ("delay launch", "payments mvp"))

    def test_stronger_record_gets_high_confidence(self):
        record = {
            "decision": "Delay launch to Friday",
            "reason": "Finance approval is required before release",
            "owner": "Engineering Manager",
            "approver": "Product Lead approved the change",
            "reusable_context": "Final launch timing decision",
            "source_evidence": [
                "Product Lead approved delay (meeting_notes.txt)",
                "Engineering confirmed timeline (slack_thread.txt)"
            ]
        }

        result = calculate_bayesian_confidence(record)

        self.assertEqual(result["level"], "High")
        self.assertGreaterEqual(result["score"], 80)


if __name__ == "__main__":
    unittest.main()
