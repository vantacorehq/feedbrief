# Changelog

All notable changes to this project are documented in this file.

## [0.1.0] - 2026-10-10

### Added
- Bot that reads RSS 2.0 and Atom feeds (default: CoinDesk crypto news), summarizes each new article in 2-3 sentences with Google Gemini and posts it with a link to a Telegram chat or channel.
- Commands: `run` (with `--feed`, `--interval`, `--max-per-check`, `--delay`, `--once`, `--from-now`, `--dry-run`, `--no-ai`, `--topic`, `--model`, `--data-dir`) and `test-telegram`.
- State in `data/state.json` (last 500 posted links), so nothing is posted twice.
- Retries for Telegram (connection errors, HTTP 429, HTTP 5xx); fallback to the feed description if Gemini fails.
- Configuration from environment variables or `.env` (`.env.example` included).
- Unit tests with mocked network calls.
- README with banner, workflow diagram and example output.
