"""
A small time-to-live cache.

Market data is asked for far more often than it changes: a dashboard prices
every held ticker, the watchlist prices every saved one, the quote feed
re-prices whatever is on screen every few seconds, and the limit order
poller re-prices every pending order's ticker on its own timer. Without
something in between, each of those is its own round trip to the upstream
feed, and the same ticker gets fetched several times a second on behalf of
one person looking at one page.

Deliberately not an LRU: entries expire on time, not on pressure. What is
being bounded here is staleness, and the working set - the tickers a live
user is looking at or holding - is small enough that size never becomes the
constraint. `sweep()` drops what has expired so an unbounded run of distinct
tickers can't accumulate.
"""
import threading
import time
from typing import Any, Callable, Hashable

# Returned by get() when there is nothing usable cached, so that a cached
# None - which asset_quote and analyst_ratings both return meaningfully -
# is not confused with a miss.
MISS = object()


class TTLCache:
    """Thread-safe key/value store whose entries expire after `ttl_seconds`."""

    def __init__(self, ttl_seconds: float):
        self.ttl_seconds = ttl_seconds
        self._entries: dict[Hashable, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        # Counted because "how much upstream traffic is this saving" is the
        # only number that says whether the cache is worth its window, and
        # it is not answerable from the outside.
        self.hits = 0
        self.misses = 0

    def get(self, key: Hashable) -> Any:
        """The cached value, or MISS if it is absent or has expired."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self.misses += 1
                return MISS
            expires_at, value = entry
            if expires_at <= time.monotonic():
                del self._entries[key]
                self.misses += 1
                return MISS
            self.hits += 1
            return value

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._entries[key] = (time.monotonic() + self.ttl_seconds, value)

    def get_or_call(self, key: Hashable, produce: Callable[[], Any]) -> Any:
        """
        The cached value for `key`, calling `produce` to fill it on a miss.

        The lock is not held across `produce`: it is an upstream network call,
        and holding it there would put every caller behind whichever one
        happened to miss first. Two concurrent misses on the same key can
        therefore both fetch - a duplicated request, which is what would have
        happened anyway without a cache at all.

        A `produce` that raises is not cached, so an outage is retried rather
        than remembered.
        """
        value = self.get(key)
        if value is not MISS:
            return value

        value = produce()
        self.set(key, value)
        return value

    def sweep(self) -> int:
        """Drop expired entries. Returns how many were removed."""
        now = time.monotonic()
        with self._lock:
            expired = [key for key, (expires_at, _) in self._entries.items() if expires_at <= now]
            for key in expired:
                del self._entries[key]
            return len(expired)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self.hits = 0
            self.misses = 0

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)
