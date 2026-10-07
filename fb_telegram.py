"""Posts messages to a Telegram chat or channel."""

import html
import time

import requests

from fb_config import redact

SEND_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_LEN = 4096        # Telegram's limit for one message
MAX_RETRY_WAIT = 60   # never wait longer than this because of one HTTP 429


def _esc(text: str) -> str:
    return html.escape(text, quote=False)


def format_message(title: str, summary: str, link: str) -> str:
    """Builds the HTML message. Title and summary are escaped, so characters like
    < and & cannot break Telegram's HTML parsing. Too long messages are shortened."""
    title = title if len(title) <= 300 else title[:299] + "…"
    while True:
        text = f"<b>{_esc(title)}</b>\n\n{_esc(summary)}\n\n{_esc(link)}"
        if len(text) <= MAX_LEN or not summary:
            return text
        summary = summary[: max(0, int(len(summary) * 0.9) - 1)].rstrip() + "…" if len(summary) > 1 else ""


class TelegramClient:
    def __init__(self, token: str, chat_id: str, timeout: float = 10, retries: int = 3, backoff: float = 2.0,
                 session=None, sleep=time.sleep):
        self.token = token
        self.chat_id = chat_id
        self.url = SEND_URL.format(token=token)
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.session = session or requests
        self.sleep = sleep

    def _clean(self, text: str) -> str:
        return redact(str(text), self.token)

    def send_message(self, text: str) -> tuple:
        """Sends one message. Returns (ok, error_text). Connection errors, HTTP 429 and HTTP 5xx
        are retried; other errors (wrong token, wrong chat, bad HTML) fail right away."""
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}
        error = "unknown error"

        for attempt in range(self.retries + 1):
            wait = self.backoff * 2 ** attempt
            try:
                response = self.session.post(self.url, json=payload, timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout) as e:
                error = f"could not reach Telegram: {type(e).__name__}"
            except requests.RequestException as e:
                return False, f"request failed: {self._clean(e)}"
            else:
                if response.status_code == 200:
                    return True, ""
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                description = body.get("description") or response.text[:200]
                error = self._clean(f"HTTP {response.status_code}: {description}")
                if response.status_code == 429:
                    wait = min(body.get("parameters", {}).get("retry_after", wait), MAX_RETRY_WAIT)
                elif response.status_code < 500:
                    return False, error  # retrying will not help

            if attempt < self.retries:
                self.sleep(wait)

        return False, error
