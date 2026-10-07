import unittest
from unittest import mock

import requests

from fb_feed import clean_text, fetch_articles, parse_feed
from helpers_fakes import fake_response

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Example news</title>
    <item>
      <title>First &amp; best</title>
      <link>https://example.org/1</link>
      <description><![CDATA[<p>Hello <b>world</b> &amp; friends</p>]]></description>
    </item>
    <item>
      <title><![CDATA[Second]]></title>
      <link> https://example.org/2 </link>
      <content:encoded><![CDATA[<div>Long body</div>]]></content:encoded>
    </item>
    <item>
      <title>No link</title>
      <description>skipped later</description>
    </item>
  </channel>
</rss>"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example</title>
  <entry>
    <title>Atom one</title>
    <link rel="self" href="https://example.org/self"/>
    <link rel="alternate" href="https://example.org/a1"/>
    <summary>Atom summary</summary>
  </entry>
  <entry>
    <title>Atom two</title>
    <link href="https://example.org/a2"/>
    <content type="html">&lt;p&gt;Body&lt;/p&gt;</content>
  </entry>
</feed>"""


class FeedTests(unittest.TestCase):
    def test_clean_text(self):
        self.assertEqual(clean_text("<p>Hello <b>world</b> &amp; friends</p>\n\n  ok"), "Hello world & friends ok")
        self.assertEqual(clean_text(None), "")

    def test_parse_rss(self):
        articles = parse_feed(RSS)
        self.assertEqual(len(articles), 3)
        self.assertEqual(articles[0], {"title": "First & best", "link": "https://example.org/1", "summary": "Hello world & friends"})
        self.assertEqual(articles[1]["link"], "https://example.org/2")
        self.assertEqual(articles[1]["summary"], "Long body")
        self.assertEqual(articles[2]["link"], "")

    def test_parse_atom(self):
        articles = parse_feed(ATOM)
        self.assertEqual([a["link"] for a in articles], ["https://example.org/a1", "https://example.org/a2"])
        self.assertEqual(articles[0]["summary"], "Atom summary")
        self.assertEqual(articles[1]["summary"], "Body")

    def test_invalid_xml(self):
        with self.assertRaisesRegex(ValueError, "XML"):
            parse_feed(b"<html><body>not a feed")

    def test_unsupported_format(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            parse_feed(b"<root><item/></root>")

    def test_fetch_articles_uses_timeout(self):
        session = mock.Mock()
        session.get.return_value = fake_response(content=RSS)
        articles = fetch_articles("https://example.org/feed", timeout=7, session=session)
        self.assertEqual(len(articles), 3)
        self.assertEqual(session.get.call_args.kwargs["timeout"], 7)

    def test_fetch_http_error(self):
        session = mock.Mock()
        session.get.return_value = fake_response(503)
        with self.assertRaises(requests.HTTPError):
            fetch_articles("https://example.org/feed", session=session)


if __name__ == "__main__":
    unittest.main()
