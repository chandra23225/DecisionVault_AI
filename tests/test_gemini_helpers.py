import unittest

from decisionvault.gemini_helpers import extract_json_from_response


class GeminiHelperTests(unittest.TestCase):
    def test_extracts_json_from_markdown_fence(self):
        raw_response = """```json
{"executive_summary": "Done", "decision_records": []}
```"""

        parsed = extract_json_from_response(raw_response)

        self.assertEqual(parsed["executive_summary"], "Done")
        self.assertEqual(parsed["decision_records"], [])

    def test_extracts_json_from_surrounding_text(self):
        raw_response = 'Here is the result: {"decision_records": [{"decision": "Go"}]}'

        parsed = extract_json_from_response(raw_response)

        self.assertEqual(parsed["decision_records"][0]["decision"], "Go")


if __name__ == "__main__":
    unittest.main()
