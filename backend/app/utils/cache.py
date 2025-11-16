from dataclasses import dataclass
from threading import Lock
from time import time
from typing import Callable, Dict, Generic, Hashable, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: Dict[Hashable, CacheEntry[T]] = {}
        self._lock = Lock()

    def get(self, key: Hashable) -> T | None:
        with self._lock:
            entry = self._store.get(key)
            if entry and entry.expires_at > time():
                return entry.value
            if entry:
                self._store.pop(key, None)
            return None

    def set(self, key: Hashable, value: T) -> None:
        with self._lock:
            self._store[key] = CacheEntry(value=value, expires_at=time() + self.ttl_seconds)

    def get_or_set(self, key: Hashable, creator: Callable[[], T]) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = creator()
        self.set(key, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
