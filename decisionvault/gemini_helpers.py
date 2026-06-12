import json


class GeminiJSONError(Exception):
    def __init__(self, message, raw_response):
        super().__init__(message)
        self.raw_response = raw_response


class GeminiAPIError(Exception):
    def __init__(self, message, original_error=None):
        super().__init__(message)
        self.original_error = original_error


def extract_json_from_response(raw_text):
    raw_text = raw_text.strip()

    if raw_text.startswith("```json"):
        raw_text = raw_text.replace("```json", "", 1).strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.replace("```", "", 1).strip()

    if raw_text.endswith("```"):
        raw_text = raw_text[:-3].strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        json_start = raw_text.find("{")
        json_end = raw_text.rfind("}")

        if json_start == -1 or json_end == -1 or json_end <= json_start:
            raise

        return json.loads(raw_text[json_start:json_end + 1])
