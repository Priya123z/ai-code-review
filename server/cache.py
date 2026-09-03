"""Small in-memory response cache.

Two people pasting the same snippet is the common case for a demo linked from a
portfolio, and a cache hit costs no quota at all.
"""
from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict


class ResponseCache:
    def __init__(self, max_entries: int = 256):
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._entries: OrderedDict = OrderedDict()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(*parts: str) -> str:
        digest = hashlib.sha256("\x00".join(parts).encode()).hexdigest()
        return digest[:32]

    def get(self, key: str):
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
                self.hits += 1
                return self._entries[key]
            self.misses += 1
            return None

    def put(self, key: str, value) -> None:
        with self._lock:
            self._entries[key] = value
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def stats(self) -> dict:
        with self._lock:
            return {"entries": len(self._entries), "hits": self.hits, "misses": self.misses}
