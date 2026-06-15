import tempfile
import unittest
from pathlib import Path

from decisionvault.storage import load_vault, save_decisions_to_vault, update_saved_decision


class StorageTests(unittest.TestCase):
    def test_save_decisions_skips_duplicates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_file = str(Path(temp_dir) / "vault.json")
            records = [
                {
                    "decision": "Delay launch",
                    "affected_project_or_workflow": "Payments MVP",
                    "reason": "Approval pending"
                },
                {
                    "decision": " delay launch ",
                    "affected_project_or_workflow": " payments mvp ",
                    "reason": "Same decision"
                }
            ]

            saved_count, duplicate_count, duplicate_records = save_decisions_to_vault(
                records,
                vault_file
            )

            self.assertEqual(saved_count, 1)
            self.assertEqual(duplicate_count, 1)
            self.assertEqual(len(duplicate_records), 1)
            self.assertEqual(len(load_vault(vault_file)), 1)

    def test_update_saved_decision_edits_existing_record(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_file = str(Path(temp_dir) / "vault.json")
            save_decisions_to_vault(
                [
                    {
                        "decision": "Delay launch",
                        "affected_project_or_workflow": "Payments MVP",
                        "reason": "Approval pending",
                    }
                ],
                vault_file,
            )

            updated = update_saved_decision(
                "DV-001",
                {
                    "decision": "Delay launch by one week",
                    "owner": "Priya",
                    "status": "Pending Approval",
                },
                vault_file,
            )

            records = load_vault(vault_file)

            self.assertTrue(updated)
            self.assertEqual(records[0]["decision"], "Delay launch by one week")
            self.assertEqual(records[0]["owner"], "Priya")
            self.assertEqual(records[0]["status"], "Pending Approval")
            self.assertEqual(records[0]["decision_id"], "DV-001")

    def test_update_saved_decision_returns_false_for_missing_record(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_file = str(Path(temp_dir) / "vault.json")

            self.assertFalse(update_saved_decision("DV-404", {"status": "Archived"}, vault_file))


if __name__ == "__main__":
    unittest.main()
