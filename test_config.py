import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fb_config import ConfigError, get_secret, load_env_file, redact


class ConfigTests(unittest.TestCase):
    def test_load_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text('# comment\nAAA_KEY=one\nBBB_KEY="two words"\n\nbad line\nCCC_KEY=\'three\'\n', encoding="utf-8")
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(load_env_file(str(path)), 3)
                self.assertEqual(os.environ["BBB_KEY"], "two words")
                self.assertEqual(os.environ["CCC_KEY"], "three")

    def test_env_file_does_not_override_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("AAA_KEY=from_file\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"AAA_KEY": "from_env"}, clear=True):
                self.assertEqual(load_env_file(str(path)), 0)
                self.assertEqual(os.environ["AAA_KEY"], "from_env")

    def test_missing_env_file(self):
        self.assertEqual(load_env_file("/nonexistent/.env"), 0)

    def test_get_secret(self):
        with mock.patch.dict(os.environ, {"K": " value "}, clear=True):
            self.assertEqual(get_secret("K"), "value")
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigError):
                get_secret("K")
        for placeholder in ("PASTE_YOUR_KEY_HERE", "your_key_here"):
            with mock.patch.dict(os.environ, {"K": placeholder}, clear=True):
                with self.assertRaises(ConfigError):
                    get_secret("K")

    def test_redact(self):
        self.assertEqual(redact("url/bot123:ABC/send and 123:ABC", "123:ABC"), "url/bot***/send and ***")
        self.assertEqual(redact("nothing", "", None), "nothing")


if __name__ == "__main__":
    unittest.main()
