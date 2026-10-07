import unittest
from unittest import mock

import requests

from fb_telegram import MAX_LEN, TelegramClient, format_message
from helpers_fakes import fake_response


class FormatTests(unittest.TestCase):
    def test_basic_format(self):
        self.assertEqual(format_message("Title", "Summary.", "https://example.org/1"),
                         "<b>Title</b>\n\nSummary.\n\nhttps://example.org/1")

    def test_html_characters_are_escaped(self):
        text = format_message("A <b> & C", "1 < 2 && 3 > 2", "https://example.org/?a=1&b=2")
        self.assertIn("<b>A &lt;b&gt; &amp; C</b>", text)
        self.assertIn("1 &lt; 2 &amp;&amp; 3 &gt; 2", text)
        self.assertIn("https://example.org/?a=1&amp;b=2", text)

    def test_long_message_is_shortened(self):
        text = format_message("Title", "word & " * 3000, "https://example.org/1")
        self.assertLessEqual(len(text), MAX_LEN)
        self.assertTrue(text.endswith("https://example.org/1"))
        self.assertNotIn("&am\n", text)

    def test_very_long_title_is_shortened(self):
        text = format_message("T" * 5000, "s", "https://example.org/1")
        self.assertLessEqual(len(text), MAX_LEN)


class ClientTests(unittest.TestCase):
    def make(self, *responses, retries=3):
        session = mock.Mock()
        session.post.side_effect = list(responses)
        waits = []
        return TelegramClient("123:SECRET", "-100", session=session, retries=retries, backoff=1.0, sleep=waits.append), session, waits

    def test_success_and_payload(self):
        client, session, _ = self.make(fake_response(200))
        self.assertEqual(client.send_message("hi"), (True, ""))
        payload = session.post.call_args.kwargs["json"]
        self.assertEqual((payload["chat_id"], payload["text"], payload["parse_mode"]), ("-100", "hi", "HTML"))
        self.assertIn("123:SECRET", session.post.call_args.args[0])

    def test_rate_limit_waits_for_retry_after(self):
        limited = fake_response(429, payload={"ok": False, "parameters": {"retry_after": 7}})
        client, _, waits = self.make(limited, fake_response(200))
        self.assertEqual(client.send_message("hi"), (True, ""))
        self.assertEqual(waits, [7])

    def test_retry_after_is_capped(self):
        limited = fake_response(429, payload={"parameters": {"retry_after": 9999}})
        client, _, waits = self.make(limited, fake_response(200))
        client.send_message("hi")
        self.assertEqual(waits, [60])

    def test_server_error_is_retried_with_backoff(self):
        client, _, waits = self.make(fake_response(502), fake_response(500), fake_response(200))
        self.assertTrue(client.send_message("hi")[0])
        self.assertEqual(waits, [1.0, 2.0])

    def test_connection_error_is_retried(self):
        client, session, waits = self.make(requests.ConnectionError("down"), fake_response(200))
        self.assertTrue(client.send_message("hi")[0])
        self.assertEqual(waits, [1.0])

    def test_gives_up_after_retries(self):
        client, session, _ = self.make(*[requests.Timeout("slow")] * 4)
        ok, error = client.send_message("hi")
        self.assertFalse(ok)
        self.assertIn("could not reach Telegram", error)
        self.assertEqual(session.post.call_count, 4)

    def test_client_error_is_not_retried_and_shows_description(self):
        bad = fake_response(400, payload={"ok": False, "description": "Bad Request: can't parse entities"})
        client, session, _ = self.make(bad)
        ok, error = client.send_message("hi")
        self.assertFalse(ok)
        self.assertIn("can't parse entities", error)
        self.assertEqual(session.post.call_count, 1)

    def test_token_is_redacted_in_errors(self):
        bad = fake_response(401, payload={"description": "Unauthorized 123:SECRET"})
        client, _, _ = self.make(bad)
        _, error = client.send_message("hi")
        self.assertNotIn("SECRET", error)

    def test_unexpected_request_exception_is_redacted(self):
        client, _, _ = self.make(requests.RequestException("bad url https://api.telegram.org/bot123:SECRET/sendMessage"))
        ok, error = client.send_message("hi")
        self.assertFalse(ok)
        self.assertNotIn("SECRET", error)


if __name__ == "__main__":
    unittest.main()
