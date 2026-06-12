import tempfile
import unittest
from pathlib import Path

from decisionvault.storage import load_vault, save_decisions_to_vault


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


if __name__ == "__main__":
    unittest.main()
