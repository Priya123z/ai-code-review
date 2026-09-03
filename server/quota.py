"""Request budgeting for the public demo.

The demo runs on a free Groq key: 30 requests/min, 1000/day, 8000 tokens/min,
200k tokens/day. Tokens per minute is what actually binds — a couple of thousand
token reviews will hit 8000 TPM long before they hit 30 RPM — so this counts
tokens as well as requests.

Everything is in memory. The Space restarts and the counters reset, which is fine
for a demo and avoids dragging in a database.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

# Groq free tier, with headroom so the demo degrades before the provider does.
TOKENS_PER_MINUTE = 7000
TOKENS_PER_DAY = 180_000
REQUESTS_PER_DAY = 900

# What one visitor gets per day, so nobody drains the budget on their own.
PER_VISITOR_PER_DAY = 12

MINUTE = 60
DAY = 24 * 60 * 60


@dataclass
class Decision:
    allowed: bool
    reason: str = ""
    retry_after: int = 0


@dataclass
class Quota:
    tokens_per_minute: int = TOKENS_PER_MINUTE
    tokens_per_day: int = TOKENS_PER_DAY
    requests_per_day: int = REQUESTS_PER_DAY
    per_visitor_per_day: int = PER_VISITOR_PER_DAY

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _minute: deque = field(default_factory=deque, init=False)
    _day: deque = field(default_factory=deque, init=False)
    _visitors: dict = field(default_factory=dict, init=False)

    def check(self, visitor: str, estimated_tokens: int) -> Decision:
        now = time.time()

        with self._lock:
            self._evict(now)

            used_this_minute = sum(t for _, t in self._minute)
            if used_this_minute + estimated_tokens > self.tokens_per_minute:
                oldest = self._minute[0][0] if self._minute else now
                return Decision(False, "busy", max(1, int(MINUTE - (now - oldest)) + 1))

            if sum(t for _, t in self._day) + estimated_tokens > self.tokens_per_day:
                return Decision(False, "daily_tokens")

            if len(self._day) >= self.requests_per_day:
                return Decision(False, "daily_requests")

            seen = [t for t in self._visitors.get(visitor, []) if now - t < DAY]
            self._visitors[visitor] = seen
            if len(seen) >= self.per_visitor_per_day:
                return Decision(False, "visitor_daily")

            return Decision(True)

    def record(self, visitor: str, tokens: int) -> None:
        now = time.time()
        with self._lock:
            self._minute.append((now, tokens))
            self._day.append((now, tokens))
            self._visitors.setdefault(visitor, []).append(now)
            self._evict(now)

    def snapshot(self, visitor: str) -> dict:
        now = time.time()
        with self._lock:
            self._evict(now)
            used_minute = sum(t for _, t in self._minute)
            used_day = sum(t for _, t in self._day)
            seen = len([t for t in self._visitors.get(visitor, []) if now - t < DAY])

            return {
                "tokens_remaining_this_minute": max(0, self.tokens_per_minute - used_minute),
                "tokens_remaining_today": max(0, self.tokens_per_day - used_day),
                "requests_remaining_today": max(0, self.requests_per_day - len(self._day)),
                "your_runs_remaining_today": max(0, self.per_visitor_per_day - seen),
                "runs_served_today": len(self._day),
            }

    def _evict(self, now: float) -> None:
        while self._minute and now - self._minute[0][0] > MINUTE:
            self._minute.popleft()
        while self._day and now - self._day[0][0] > DAY:
            self._day.popleft()


def estimate_tokens(text: str) -> int:
    """Roughly four characters per token, plus room for the reply."""
    return len(text) // 4 + 800
