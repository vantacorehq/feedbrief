"""feedbrief: summarizes new articles of RSS/Atom feeds with Gemini and posts them to Telegram.

Usage: python feedbrief.py <run|test-telegram> ...
"""

import argparse
import sys

from fb_bot import run_loop
from fb_config import BOT_TOKEN_VAR, CHAT_ID_VAR, GEMINI_KEY_VAR, ConfigError, get_secret, load_env_file
from fb_feed import DEFAULT_FEED
from fb_gemini import DEFAULT_MODEL, DEFAULT_TOPIC, GeminiSummarizer, PlainSummarizer
from fb_state import StateStore
from fb_telegram import TelegramClient

__version__ = "1.0.0"


def cmd_run(args) -> int:
    try:
        telegram = None
        if not args.dry_run:
            telegram = TelegramClient(get_secret(BOT_TOKEN_VAR), get_secret(CHAT_ID_VAR))
        if args.no_ai:
            summarizer = PlainSummarizer()
        else:
            summarizer = GeminiSummarizer(get_secret(GEMINI_KEY_VAR), model=args.model, topic=args.topic)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1

    feeds = args.feed or [DEFAULT_FEED]
    store = StateStore(args.data_dir)
    mode = "one check" if args.once else f"every {args.interval} sec, Ctrl+C to stop"
    extra = " (dry run: nothing is posted)" if args.dry_run else ""
    print(f"Watching {len(feeds)} feed(s), {mode}{extra}. Data folder: {store.dir}")

    try:
        errors = run_loop(feeds, store, summarizer, telegram, interval=args.interval, once=args.once,
                          max_per_check=args.max_per_check, from_now=args.from_now, dry_run=args.dry_run,
                          delay=args.delay)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    return 1 if errors else 0


def cmd_test_telegram(args) -> int:
    try:
        telegram = TelegramClient(get_secret(BOT_TOKEN_VAR), get_secret(CHAT_ID_VAR))
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    ok, error = telegram.send_message("feedbrief test message: the bot can post here.")
    if ok:
        print("Test message sent.")
        return 0
    print(f"Telegram error: {error}", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="feedbrief", description="Summarize new RSS/Atom articles with Gemini and post them to Telegram.")
    parser.add_argument("--version", action="version", version=f"feedbrief {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="Watch the feeds and post summaries")
    p.add_argument("--feed", action="append", help="RSS or Atom feed URL (repeat for several, default: CoinDesk crypto news)")
    p.add_argument("--interval", type=int, default=900, help="Seconds between checks (default 900)")
    p.add_argument("--max-per-check", type=int, default=3, help="Most articles to post per feed per check (default 3)")
    p.add_argument("--delay", type=float, default=5.0, help="Seconds between Telegram messages (default 5)")
    p.add_argument("--once", action="store_true", help="Run a single check and exit")
    p.add_argument("--from-now", action="store_true", help="On the first check of a feed, skip the articles already in it")
    p.add_argument("--dry-run", action="store_true", help="Print the messages instead of posting them (needs no Telegram keys)")
    p.add_argument("--no-ai", action="store_true", help="Skip Gemini and post the feed description (needs no Gemini key)")
    p.add_argument("--topic", default=DEFAULT_TOPIC, help=f"Audience topic for the summary prompt (default: {DEFAULT_TOPIC})")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model (default {DEFAULT_MODEL})")
    p.add_argument("--data-dir", default="data", help="Folder for the state file (default data)")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("test-telegram", help="Send a test message to check the bot token and chat ID")
    p.set_defaults(func=cmd_test_telegram)

    return parser


def main(argv=None) -> int:
    load_env_file(".env")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
