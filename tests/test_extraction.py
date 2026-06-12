import unittest

from decisionvault.extraction import ask_decision_vault_with_client
from decisionvault.gemini_helpers import GeminiAPIError


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, text):
        self.text = text

    def generate_content(self, **kwargs):
        return FakeResponse(self.text)


class FakeClient:
    def __init__(self, text):
        self.models = FakeModels(text)


class FailingModels:
    def generate_content(self, **kwargs):
        raise RuntimeError("quota exceeded")


class FailingClient:
    def __init__(self):
        self.models = FailingModels()


class ExtractionTests(unittest.TestCase):
    def test_ask_parses_structured_json_answer(self):
        client = FakeClient(
            """
            {
              "answer_status": "Answered",
              "direct_answer": "Launch was delayed for approval.",
              "key_points": ["Finance approval was pending"],
              "supporting_records": [],
              "information_gaps": [],
              "recommended_next_steps": []
            }
            """
        )

        answer = ask_decision_vault_with_client(client, "Why?", [])

        self.assertEqual(answer["answer_status"], "Answered")
        self.assertEqual(answer["direct_answer"], "Launch was delayed for approval.")
        self.assertEqual(answer["key_points"], ["Finance approval was pending"])

    def test_ask_falls_back_for_plain_text_answer(self):
        client = FakeClient("Plain answer")

        answer = ask_decision_vault_with_client(client, "Why?", [])

        self.assertEqual(answer["answer_status"], "Answered")
        self.assertEqual(answer["direct_answer"], "Plain answer")
        self.assertEqual(answer["supporting_records"], [])

    def test_ask_wraps_gemini_client_errors(self):
        client = FailingClient()

        with self.assertRaises(GeminiAPIError) as context:
            ask_decision_vault_with_client(client, "Why?", [])

        self.assertIn("quota exceeded", str(context.exception))


if __name__ == "__main__":
    unittest.main()
