import unittest

from decisionvault.extraction import ask_decision_vault_with_client, extract_decisions_with_client
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


class TemporarilyUnavailableModels:
    def __init__(self, failures_before_success=1):
        self.failures_before_success = failures_before_success
        self.call_count = 0

    def generate_content(self, **kwargs):
        self.call_count += 1

        if self.call_count <= self.failures_before_success:
            raise RuntimeError(
                "503 UNAVAILABLE. {'error': {'code': 503, 'message': "
                "'This model is currently experiencing high demand.', "
                "'status': 'UNAVAILABLE'}}"
            )

        return FakeResponse(
            """
            {
              "executive_summary": "Launch readiness was discussed.",
              "decision_records": [],
              "items_needing_human_review": []
            }
            """
        )


class TemporarilyUnavailableClient:
    def __init__(self, failures_before_success=1):
        self.models = TemporarilyUnavailableModels(failures_before_success)


class CapturingModels:
    def __init__(self, text):
        self.text = text
        self.last_kwargs = None

    def generate_content(self, **kwargs):
        self.last_kwargs = kwargs
        return FakeResponse(self.text)


class CapturingClient:
    def __init__(self, text):
        self.models = CapturingModels(text)


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

    def test_extract_retries_temporary_gemini_503_errors(self):
        client = TemporarilyUnavailableClient(failures_before_success=1)

        result = extract_decisions_with_client(client, "Meeting notes", sleep_seconds=0)

        self.assertEqual(client.models.call_count, 2)
        self.assertEqual(result["executive_summary"], "Launch readiness was discussed.")

    def test_extract_raises_friendly_message_after_repeated_503_errors(self):
        client = TemporarilyUnavailableClient(failures_before_success=3)

        with self.assertRaises(GeminiAPIError) as context:
            extract_decisions_with_client(client, "Meeting notes", sleep_seconds=0)

        self.assertIn("Gemini is temporarily overloaded", str(context.exception))
        self.assertNotIn("{'error'", str(context.exception))

    def test_ask_prompt_includes_meeting_context_when_available(self):
        client = CapturingClient(
            """
            {
              "answer_status": "Answered",
              "direct_answer": "The meeting topic was launch readiness.",
              "key_points": [],
              "supporting_records": [],
              "information_gaps": [],
              "recommended_next_steps": []
            }
            """
        )

        ask_decision_vault_with_client(
            client,
            "What is the topic of this meeting?",
            [],
            context={
                "executive_summary": "The meeting covered launch readiness.",
                "source_text": "--- SOURCE FILE: meeting_notes.txt ---\nLaunch readiness notes",
            },
        )

        prompt = client.models.last_kwargs["contents"]

        self.assertIn("Meeting Context", prompt)
        self.assertIn("The meeting covered launch readiness.", prompt)
        self.assertIn("Launch readiness notes", prompt)

    def test_ask_prompt_prioritizes_reviewed_records_before_raw_source(self):
        client = CapturingClient(
            """
            {
              "answer_status": "Answered",
              "answer_source": "Reviewed Records",
              "confidence": "High",
              "direct_answer": "The launch was delayed.",
              "key_points": [],
              "supporting_records": [],
              "source_references": [],
              "information_gaps": [],
              "recommended_next_steps": []
            }
            """
        )

        ask_decision_vault_with_client(
            client,
            "What happened with launch?",
            [{"decision": "Delay launch", "source_evidence": ["Launch delayed"]}],
            context={"source_text": "Raw notes about the launch delay."},
        )

        prompt = client.models.last_kwargs["contents"]

        self.assertIn("Use reviewed decision records first", prompt)
        self.assertIn("Use raw source text as backup", prompt)
        self.assertIn('"answer_source": "Reviewed Records / Source Text / Both / Not Available"', prompt)
        self.assertIn("Raw notes about the launch delay.", prompt)

    def test_ask_normalizes_missing_optional_answer_fields(self):
        client = FakeClient(
            """
            {
              "answer_status": "Answered",
              "direct_answer": "Launch readiness was the topic."
            }
            """
        )

        answer = ask_decision_vault_with_client(client, "Topic?", [])

        self.assertEqual(answer["answer_source"], "Not Available")
        self.assertEqual(answer["confidence"], "Medium")
        self.assertEqual(answer["source_references"], [])
        self.assertEqual(answer["key_points"], [])


if __name__ == "__main__":
    unittest.main()
