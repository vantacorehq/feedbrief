"""Downloads and parses an RSS 2.0 or Atom feed (standard library only)."""

import html
import re
import xml.etree.ElementTree as ET

import requests

DEFAULT_FEED = "https://www.coindesk.com/arc/outboundfeeds/rss/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; feedbrief/1.0)"}

_TAGS = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"\s+")


def clean_text(raw: str) -> str:
    """Removes HTML tags and entities and collapses whitespace."""
    return _SPACES.sub(" ", html.unescape(_TAGS.sub(" ", raw or ""))).strip()


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _text(element) -> str:
    return "".join(element.itertext()).strip()


def _entry_to_article(entry) -> dict:
    title = link = ""
    summary_candidates = {}
    for child in entry:
        name = _local(child.tag)
        if name == "title":
            title = _text(child)
        elif name == "link":
            if child.get("href"):  # Atom
                if not link and child.get("rel", "alternate") == "alternate":
                    link = child.get("href").strip()
            elif not link:  # RSS
                link = _text(child)
        elif name in ("description", "summary", "content", "encoded"):
            summary_candidates.setdefault(name, _text(child))

    summary = ""
    for name in ("description", "summary", "content", "encoded"):
        if summary_candidates.get(name):
            summary = summary_candidates[name]
            break
    return {"title": clean_text(title), "link": link.strip(), "summary": clean_text(summary)}


def parse_feed(content) -> list:
    """Returns a list of {title, link, summary}, in the order of the feed."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise ValueError(f"Could not parse the feed as XML: {e}")

    kind = _local(root.tag)
    if kind == "rss":
        entries = [el for el in root.iter() if _local(el.tag) == "item"]
    elif kind == "feed":
        entries = [el for el in root if _local(el.tag) == "entry"]
    else:
        raise ValueError("Unsupported feed format (expected RSS 2.0 or Atom)")

    return [_entry_to_article(entry) for entry in entries]


def fetch_articles(url: str, timeout: float = 15, session=None) -> list:
    """Downloads the feed (with a timeout) and parses it."""
    response = (session or requests).get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return parse_feed(response.content)
