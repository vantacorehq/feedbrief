from unittest import mock

import requests


def fake_response(status=200, payload=None, headers=None, content=b"", text=""):
    response = mock.Mock()
    response.status_code = status
    response.headers = headers or {}
    response.content = content
    response.text = text
    response.json.return_value = payload if payload is not None else {}
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status}", response=response)
    else:
        response.raise_for_status.return_value = None
    return response


def gemini_payload(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def article(n, title=None):
    return {"title": title or f"Title {n}", "link": f"https://example.org/{n}", "summary": f"Description {n}"}


class FakeSummarizer:
    def __init__(self):
        self.calls = []

    def summarize(self, title, description):
        self.calls.append(title)
        return f"Summary of {title}", True


class FakeTelegram:
    def __init__(self, results=None):
        self.sent = []
        self.results = list(results or [])

    def send_message(self, text):
        self.sent.append(text)
        if self.results:
            return self.results.pop(0)
        return True, ""
