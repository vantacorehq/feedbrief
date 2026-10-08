"""Remembers which articles were already posted."""

import json
import os
from pathlib import Path

SEEN_LIMIT = 500  # how many posted links to remember (the most recent ones)


def _write_json_atomic(path: Path, data) -> None:
    """Writes to a temporary file first, so a crash cannot leave a half-written file."""
    temp = path.with_name(path.name + ".tmp")
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(temp, path)


class StateStore:
    def __init__(self, data_dir: str = "data"):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "state.json"

    def load(self) -> dict:
        state = {}
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    state = json.load(f)
            except (json.JSONDecodeError, OSError):
                state = {}
        if not isinstance(state, dict):
            state = {}
        state.setdefault("seen", [])
        state.setdefault("failures", {})
        state.setdefault("baselined", [])
        return state

    def save(self, state: dict) -> None:
        state = dict(state)
        # "seen" is an ordered list, so trimming drops the oldest links, not random ones
        state["seen"] = list(state.get("seen", []))[-SEEN_LIMIT:]
        _write_json_atomic(self.path, state)
