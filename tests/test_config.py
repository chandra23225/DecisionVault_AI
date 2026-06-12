import os
import unittest

from decisionvault.config import get_config_value, is_placeholder_config_value


class ConfigTests(unittest.TestCase):
    def test_placeholder_values_are_detected(self):
        self.assertTrue(is_placeholder_config_value("your_gemini_api_key_here"))
        self.assertTrue(is_placeholder_config_value("replace_me"))
        self.assertFalse(is_placeholder_config_value("real-key-value"))

    def test_placeholder_environment_values_fall_back_to_default(self):
        os.environ["GEMINI_API_KEY"] = "your_gemini_api_key_here"

        try:
            self.assertIsNone(get_config_value("GEMINI_API_KEY", None))
        finally:
            os.environ.pop("GEMINI_API_KEY", None)


if __name__ == "__main__":
    unittest.main()
