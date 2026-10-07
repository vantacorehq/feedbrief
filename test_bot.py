import tempfile
import unittest
from pathlib import Path

import requests

from fb_bot import MAX_FAILURES, check_feed, run_cycle, run_loop
from fb_state import StateStore
from helpers_fakes import FakeSummarizer, FakeTelegram, article

FEED = "https://example.org/feed"


class BotTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(str(Path(self._tmp.name) / "data"))
        self.summarizer = FakeSummarizer()
        self.telegram = FakeTelegram()
        self.logs = []
        self.sleeps = []

    def tearDown(self):
        self._tmp.cleanup()

    def check(self, articles, **options):
        options.setdefault("delay", 5.0)
        return check_feed(FEED, self.store, self.summarizer, self.telegram, fetch=lambda url: articles,
                          sleep=self.sleeps.append, log=self.logs.append, **options)

    def test_posts_new_articles_oldest_first(self):
        feed = [article(3), article(2), article(1)]  # feeds list the newest first
        posted, errors = self.check(feed)
        self.assertEqual((posted, errors), (3, 0))
        self.assertEqual(self.summarizer.calls, ["Title 1", "Title 2", "Title 3"])
        self.assertIn("<b>Title 1</b>\n\nSummary of Title 1\n\nhttps://example.org/1", self.telegram.sent[0])
        self.assertEqual(self.sleeps, [5.0, 5.0])  # a pause between messages, not after the last

    def test_max_per_check_and_the_rest_comes_next_time(self):
        feed = [article(n) for n in range(5, 0, -1)]
        self.assertEqual(self.check(feed, max_per_check=2), (2, 0))
        self.assertEqual(self.summarizer.calls, ["Title 1", "Title 2"])
        self.assertEqual(self.check(feed, max_per_check=2), (2, 0))
        self.assertEqual(self.summarizer.calls[2:], ["Title 3", "Title 4"])

    def test_nothing_is_posted_twice_even_after_restart(self):
        feed = [article(2), article(1)]
        self.check(feed)
        self.store = StateStore(str(self.store.dir))
        self.assertEqual(self.check(feed), (0, 0))
        self.assertEqual(len(self.telegram.sent), 2)

    def test_failed_post_is_not_marked_as_seen(self):
        self.telegram.results = [(False, "HTTP 502")]
        feed = [article(1)]
        self.assertEqual(self.check(feed), (0, 1))
        self.assertEqual(self.store.load()["seen"], [])
        self.assertEqual(self.store.load()["failures"], {"https://example.org/1": 1})
        self.assertEqual(self.check(feed), (1, 0))  # retried next cycle
        state = self.store.load()
        self.assertEqual(state["seen"], ["https://example.org/1"])
        self.assertEqual(state["failures"], {})

    def test_gives_up_after_repeated_failures_so_it_does_not_block_the_rest(self):
        self.telegram.results = [(False, "HTTP 400: bad")] * MAX_FAILURES
        feed = [article(2), article(1)]
        for _ in range(MAX_FAILURES):
            self.check(feed, max_per_check=1)
        self.assertIn("https://example.org/1", self.store.load()["seen"])
        posted, _ = self.check(feed, max_per_check=1)
        self.assertEqual(posted, 1)
        self.assertIn("<b>Title 2</b>", self.telegram.sent[-1])

    def test_articles_without_link_are_ignored(self):
        broken = {"title": "No link", "link": "", "summary": "x"}
        self.assertEqual(self.check([broken, article(1)]), (1, 0))

    def test_from_now_skips_existing_then_posts_new_ones(self):
        feed = [article(2), article(1)]
        self.assertEqual(self.check(feed, from_now=True), (0, 0))
        self.assertEqual(self.telegram.sent, [])
        feed = [article(3)] + feed
        self.assertEqual(self.check(feed, from_now=True), (1, 0))
        self.assertIn("Title 3", self.telegram.sent[0])

    def test_dry_run_posts_nothing_and_saves_nothing(self):
        self.assertEqual(self.check([article(1)], dry_run=True), (0, 0))
        self.assertEqual(self.telegram.sent, [])
        self.assertEqual(self.store.load()["seen"], [])
        self.assertTrue(any("would post" in line for line in self.logs))

    def test_dry_run_with_from_now_does_not_change_state(self):
        self.check([article(1)], dry_run=True, from_now=True)
        self.assertEqual(self.store.load()["baselined"], [])

    def test_feed_error_is_counted(self):
        def broken(url):
            raise requests.ConnectionError("down")

        posted, errors = check_feed(FEED, self.store, self.summarizer, self.telegram, fetch=broken, log=self.logs.append)
        self.assertEqual((posted, errors), (0, 1))

    def test_invalid_feed_is_counted(self):
        def invalid(url):
            raise ValueError("not xml")

        self.assertEqual(check_feed(FEED, self.store, self.summarizer, self.telegram, fetch=invalid, log=self.logs.append), (0, 1))

    def test_run_cycle_goes_through_all_feeds(self):
        feeds = {"https://a.example/feed": [article(1)], "https://b.example/feed": [article(2)]}
        posted, errors = run_cycle(list(feeds), self.store, self.summarizer, self.telegram, fetch=lambda url: feeds[url],
                                   sleep=self.sleeps.append, log=self.logs.append, delay=0)
        self.assertEqual((posted, errors), (2, 0))

    def test_one_broken_feed_does_not_stop_the_others(self):
        def fetch(url):
            if "bad" in url:
                raise requests.ConnectionError("down")
            return [article(1)]

        posted, errors = run_cycle(["https://bad.example/feed", "https://good.example/feed"], self.store, self.summarizer,
                                   self.telegram, fetch=fetch, sleep=self.sleeps.append, log=self.logs.append, delay=0)
        self.assertEqual((posted, errors), (1, 1))

    def test_run_loop_once_and_interval(self):
        errors = run_loop([FEED], self.store, self.summarizer, self.telegram, once=True, fetch=lambda url: [article(1)],
                          sleep=self.sleeps.append, log=self.logs.append, delay=0)
        self.assertEqual(errors, 0)

        waits = []

        def stop_after_two(seconds):
            waits.append(seconds)
            if len(waits) == 2:
                raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            run_loop([FEED], self.store, self.summarizer, self.telegram, interval=123, fetch=lambda url: [],
                     sleep=stop_after_two, log=self.logs.append, delay=0)
        self.assertEqual(waits, [123, 123])


if __name__ == "__main__":
    unittest.main()
