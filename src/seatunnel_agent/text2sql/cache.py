"""TTL-based in-memory cache for SQL query results."""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from .executor import QueryResult


@dataclass
class _CacheEntry:
    result: QueryResult
    created_at: float
    sql: str


class SqlResultCache:
    """Thread-safe, TTL-bounded, size-limited query result cache.

    Keys are derived from whitespace-normalized, lowercased SQL combined
    with the datasource type so that ``SELECT a FROM t`` and
    ``select  a  from  t`` share one cache slot.
    """

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 50) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._store: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _normalize(sql: str) -> str:
        return " ".join(sql.strip().lower().split())

    def _key(self, sql: str, ds_type: str) -> str:
        normalized = self._normalize(sql)
        digest = hashlib.md5(normalized.encode("utf-8")).hexdigest()
        return f"{ds_type}:{digest}"

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._store.items() if now - v.created_at > self._ttl]
        for k in expired:
            del self._store[k]

    def get(self, sql: str, ds_type: str) -> QueryResult | None:
        with self._lock:
            self._evict_expired()
            entry = self._store.get(self._key(sql, ds_type))
            if entry is None:
                self._misses += 1
                return None
            self._hits += 1
            return entry.result

    def put(self, sql: str, ds_type: str, result: QueryResult) -> None:
        with self._lock:
            self._evict_expired()
            if len(self._store) >= self._max:
                oldest_key = min(self._store, key=lambda k: self._store[k].created_at)
                del self._store[oldest_key]
            key = self._key(sql, ds_type)
            self._store[key] = _CacheEntry(
                result=result, created_at=time.monotonic(), sql=sql,
            )

    def invalidate(self) -> None:
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "size": len(self._store),
                "hits": self._hits,
                "misses": self._misses,
            }
