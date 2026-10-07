import tempfile
import unittest
from pathlib import Path

from fb_state import SEEN_LIMIT, StateStore


class StateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(str(Path(self._tmp.name) / "data"))

    def tearDown(self):
        self._tmp.cleanup()

    def test_defaults(self):
        self.assertEqual(self.store.load(), {"seen": [], "failures": {}, "baselined": []})

    def test_roundtrip(self):
        state = self.store.load()
        state["seen"].append("a")
        state["failures"]["b"] = 2
        state["baselined"].append("feed")
        self.store.save(state)
        loaded = StateStore(str(self.store.dir)).load()
        self.assertEqual(loaded, {"seen": ["a"], "failures": {"b": 2}, "baselined": ["feed"]})
        self.assertFalse(list(self.store.dir.glob("*.tmp")))

    def test_trim_keeps_the_most_recent_in_order(self):
        state = self.store.load()
        state["seen"] = [f"link{i}" for i in range(SEEN_LIMIT + 20)]
        self.store.save(state)
        seen = self.store.load()["seen"]
        self.assertEqual(len(seen), SEEN_LIMIT)
        self.assertEqual(seen[0], "link20")
        self.assertEqual(seen[-1], f"link{SEEN_LIMIT + 19}")

    def test_corrupt_file_is_ignored(self):
        self.store.path.write_text("{oops", encoding="utf-8")
        self.assertEqual(self.store.load()["seen"], [])


if __name__ == "__main__":
    unittest.main()
