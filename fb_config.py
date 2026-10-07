"""Settings: API keys come from environment variables or a local .env file."""

import os
from pathlib import Path

BOT_TOKEN_VAR = "TELEGRAM_BOT_TOKEN"
CHAT_ID_VAR = "TELEGRAM_CHAT_ID"
GEMINI_KEY_VAR = "GEMINI_API_KEY"


class ConfigError(Exception):
    pass


def load_env_file(path: str = ".env") -> int:
    """Reads KEY=VALUE lines from a .env file into os.environ.

    Variables that are already set in the environment are not overwritten.
    Returns how many variables were loaded.
    """
    env_path = Path(path)
    if not env_path.is_file():
        return 0

    loaded = 0
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded


def get_secret(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value or value.startswith("PASTE_") or value.startswith("your_"):
        raise ConfigError(f"{name} is not set. Put it in the environment or in a .env file (see .env.example).")
    return value


def redact(text: str, *secrets: str) -> str:
    """Replaces secret values in a text, so keys never end up in logs."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text
