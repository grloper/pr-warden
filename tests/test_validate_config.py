"""Unit tests for PR-Warden config validation (no deps, runs with plain unittest)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from validate_config import validate  # noqa: E402


class ValidateConfigTest(unittest.TestCase):
    def test_valid_config_passes(self):
        problems = validate(
            app_id="4818633",
            private_key="-----BEGIN RSA PRIVATE KEY-----\nMII...\n-----END RSA PRIVATE KEY-----",
            webhook_secret="s3cr3t",
            model="ollama/qwen2.5-coder:14b",
        )
        self.assertEqual(problems, [])

    def test_int_app_id_is_rejected(self):
        problems = validate(app_id=4818633, private_key="-----BEGIN RSA PRIVATE KEY-----", webhook_secret="s", model="m")
        self.assertTrue(any("must be a string" in p for p in problems))

    def test_missing_app_id_is_rejected(self):
        problems = validate(app_id=None, private_key="-----BEGIN RSA PRIVATE KEY-----", webhook_secret="s", model="m")
        self.assertTrue(any("App ID is missing" in p for p in problems))

    def test_missing_key_is_rejected(self):
        problems = validate(app_id="1", private_key=None, webhook_secret="s", model="m")
        self.assertTrue(any("Private key is missing" in p for p in problems))

    def test_non_pem_key_is_rejected(self):
        problems = validate(app_id="1", private_key="not-a-pem", webhook_secret="s", model="m")
        self.assertTrue(any("does not look like a PEM" in p for p in problems))

    def test_empty_model_is_rejected(self):
        problems = validate(app_id="1", private_key="-----BEGIN RSA PRIVATE KEY-----", webhook_secret="s", model="")
        self.assertTrue(any("Model is empty" in p for p in problems))

    def test_cli_mode_does_not_require_webhook_secret(self):
        problems = validate(app_id="1", private_key="-----BEGIN RSA PRIVATE KEY-----", webhook_secret=None, model="m", require_webhook=False)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
