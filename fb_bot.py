"""One check of the feeds: find new articles, summarize them, post them."""

import time
from datetime import datetime

import requests

from fb_feed import fetch_articles
from fb_telegram import format_message

MAX_FAILURES = 3  # after this many failed posts an article is skipped for good


def _stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def check_feed(feed_url, store, summarizer, telegram, max_per_check=3, from_now=False, dry_run=False,
               delay=5.0, fetch=None, sleep=time.sleep, log=print) -> tuple:
    """Checks one feed. Returns (posted, errors)."""
    fetch = fetch or fetch_articles
    try:
        articles = fetch(feed_url)
    except (requests.RequestException, ValueError) as e:
        log(f"Could not read {feed_url}: {type(e).__name__}: {e}")
        return 0, 1

    state = store.load()
    seen = state["seen"]
    new_articles = [a for a in articles if a["link"] and a["link"] not in seen]
    log(f"[{_stamp()}] {feed_url}: {len(articles)} articles in the feed, {len(new_articles)} new.")

    if from_now and feed_url not in state["baselined"]:
        if dry_run:
            log(f"[dry-run] --from-now: {len(new_articles)} existing articles would be skipped.")
            return 0, 0
        seen.extend(a["link"] for a in reversed(new_articles))
        state["baselined"].append(feed_url)
        store.save(state)
        log(f"Starting from now: {len(new_articles)} existing articles skipped.")
        return 0, 0

    batch = list(reversed(new_articles))[:max_per_check]  # oldest first
    posted = 0
    errors = 0

    for index, article in enumerate(batch):
        summary, _ = summarizer.summarize(article["title"], article["summary"])
        message = format_message(article["title"], summary, article["link"])

        if dry_run:
            log(f"[dry-run] would post:\n{message}\n")
            continue

        ok, error = telegram.send_message(message)
        if ok:
            seen.append(article["link"])
            state["failures"].pop(article["link"], None)
            posted += 1
            log(f"Posted to Telegram: {article['title']}")
        else:
            errors += 1
            failures = state["failures"].get(article["link"], 0) + 1
            state["failures"][article["link"]] = failures
            log(f"Telegram error for '{article['title']}': {error}")
            if failures >= MAX_FAILURES:
                seen.append(article["link"])
                state["failures"].pop(article["link"], None)
                log(f"Giving up on this article after {MAX_FAILURES} failed attempts.")
        store.save(state)  # saved after every article, so a crash cannot cause duplicates

        if index < len(batch) - 1:
            sleep(delay)

    return posted, errors


def run_cycle(feeds, store, summarizer, telegram, **options) -> tuple:
    posted = 0
    errors = 0
    for feed_url in feeds:
        p, e = check_feed(feed_url, store, summarizer, telegram, **options)
        posted += p
        errors += e
    return posted, errors


def run_loop(feeds, store, summarizer, telegram, interval=900, once=False, sleep=time.sleep, **options) -> int:
    """Runs cycles until stopped (Ctrl+C). With once=True runs a single cycle.
    Returns the number of errors of the last cycle."""
    while True:
        _, errors = run_cycle(feeds, store, summarizer, telegram, sleep=sleep, **options)
        if once:
            return errors
        sleep(interval)
