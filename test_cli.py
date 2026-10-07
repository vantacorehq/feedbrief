import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from feedbrief import main
from helpers_fakes import FakeTelegram, article


def run(*argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, env or {}, clear=True):
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


KEYS = {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c", "GEMINI_API_KEY": "g"}


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data = str(Path(self._tmp.name) / "data")
        self._cwd = os.getcwd()
        os.chdir(self._tmp.name)  # so no real .env is picked up

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def test_run_needs_telegram_token(self):
        code, _, err = run("run", "--once", env={"TELEGRAM_CHAT_ID": "c", "GEMINI_API_KEY": "g"})
        self.assertEqual(code, 1)
        self.assertIn("TELEGRAM_BOT_TOKEN is not set", err)

    def test_run_needs_gemini_key_unless_no_ai(self):
        env = {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}
        code, _, err = run("run", "--once", env=env)
        self.assertEqual(code, 1)
        self.assertIn("GEMINI_API_KEY is not set", err)

        telegram = FakeTelegram()
        with mock.patch("feedbrief.TelegramClient", return_value=telegram), \
                mock.patch("fb_bot.fetch_articles", return_value=[article(1)]):
            code, out, _ = run("run", "--once", "--no-ai", "--data-dir", self.data, "--delay", "0", env=env)
        self.assertEqual(code, 0)
        self.assertEqual(len(telegram.sent), 1)

    def test_dry_run_needs_no_telegram_keys(self):
        with mock.patch("fb_bot.fetch_articles", return_value=[article(1)]):
            code, out, _ = run("run", "--once", "--dry-run", "--no-ai", "--data-dir", self.data)
        self.assertEqual(code, 0)
        self.assertIn("dry run: nothing is posted", out)
        self.assertIn("would post", out)

    def test_run_once_with_gemini_posts_summary(self):
        telegram = FakeTelegram()
        summarizer = mock.Mock()
        summarizer.summarize.return_value = ("Short summary.", True)
        with mock.patch("feedbrief.TelegramClient", return_value=telegram), \
                mock.patch("feedbrief.GeminiSummarizer", return_value=summarizer) as gemini, \
                mock.patch("fb_bot.fetch_articles", return_value=[article(1)]):
            code, _, _ = run("run", "--once", "--topic", "space news", "--data-dir", self.data, env=KEYS)
        self.assertEqual(code, 0)
        self.assertIn("Short summary.", telegram.sent[0])
        self.assertEqual(gemini.call_args.kwargs["topic"], "space news")

    def test_exit_code_is_1_when_something_failed(self):
        telegram = FakeTelegram(results=[(False, "HTTP 400")])
        with mock.patch("feedbrief.TelegramClient", return_value=telegram), \
                mock.patch("fb_bot.fetch_articles", return_value=[article(1)]):
            code, _, _ = run("run", "--once", "--no-ai", "--data-dir", self.data, env=KEYS)
        self.assertEqual(code, 1)

    def test_feed_option_is_repeatable(self):
        seen = []

        def fetch(url):
            seen.append(url)
            return []

        with mock.patch("fb_bot.fetch_articles", side_effect=fetch):
            run("run", "--once", "--dry-run", "--no-ai", "--feed", "https://a/feed", "--feed", "https://b/feed", "--data-dir", self.data)
        self.assertEqual(seen, ["https://a/feed", "https://b/feed"])

    def test_default_feed_is_used(self):
        seen = []
        with mock.patch("fb_bot.fetch_articles", side_effect=lambda url: seen.append(url) or []):
            run("run", "--once", "--dry-run", "--no-ai", "--data-dir", self.data)
        self.assertEqual(seen, ["https://www.coindesk.com/arc/outboundfeeds/rss/"])

    def test_test_telegram(self):
        telegram = FakeTelegram()
        with mock.patch("feedbrief.TelegramClient", return_value=telegram):
            code, out, _ = run("test-telegram", env=KEYS)
        self.assertEqual(code, 0)
        self.assertIn("Test message sent", out)

        telegram = FakeTelegram(results=[(False, "HTTP 401: Unauthorized")])
        with mock.patch("feedbrief.TelegramClient", return_value=telegram):
            code, _, err = run("test-telegram", env=KEYS)
        self.assertEqual(code, 1)
        self.assertIn("Unauthorized", err)

    def test_env_file_is_loaded(self):
        Path(".env").write_text("TELEGRAM_BOT_TOKEN=t\nTELEGRAM_CHAT_ID=c\n", encoding="utf-8")
        telegram = FakeTelegram()
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch("feedbrief.TelegramClient", return_value=telegram) as client:
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["test-telegram"])
        self.assertEqual(code, 0)
        self.assertEqual(client.call_args.args, ("t", "c"))


if __name__ == "__main__":
    unittest.main()
