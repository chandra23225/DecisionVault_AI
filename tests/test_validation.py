import unittest

from decisionvault.validation import validate_uploaded_file


class FakeUpload:
    def __init__(self, name, data, content_type="text/plain"):
        self.name = name
        self._data = data
        self.type = content_type
        self.size = len(data)

    def getvalue(self):
        return self._data


class ValidationTests(unittest.TestCase):
    def test_accepts_utf8_text_file(self):
        upload = FakeUpload("meeting_notes.txt", b"Decision: delay launch")

        content, error = validate_uploaded_file(upload, 1024, 1)

        self.assertIsNone(error)
        self.assertEqual(content, "Decision: delay launch")

    def test_rejects_binary_file(self):
        upload = FakeUpload("meeting_notes.txt", b"hello\x00world")

        content, error = validate_uploaded_file(upload, 1024, 1)

        self.assertIsNone(content)
        self.assertIn("binary data", error)

    def test_rejects_plain_text_disguised_as_csv(self):
        upload = FakeUpload(
            "decisions.csv",
            b"this is just one text cell",
            "text/csv"
        )

        content, error = validate_uploaded_file(upload, 1024, 1)

        self.assertIsNone(content)
        self.assertIn("looks like plain text", error)


if __name__ == "__main__":
    unittest.main()
