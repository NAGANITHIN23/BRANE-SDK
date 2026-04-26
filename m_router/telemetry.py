from __future__ import annotations

import atexit
import threading
from typing import Iterable

from .schemas.events import TelemetryEvent


class TelemetryBuffer:
    def __init__(self, client: object | None = None, max_size: int = 20):
        self.client = client
        self.max_size = max_size
        self._events: list[TelemetryEvent] = []
        self._lock = threading.Lock()
        atexit.register(self.flush)

    @property
    def events(self) -> list[TelemetryEvent]:
        with self._lock:
            return list(self._events)

    def add(self, event: TelemetryEvent) -> None:
        should_flush = False
        with self._lock:
            self._events.append(event)
            should_flush = len(self._events) >= self.max_size
        if should_flush:
            self.flush()

    def extend(self, events: Iterable[TelemetryEvent]) -> None:
        for event in events:
            self.add(event)

    def flush(self) -> None:
        with self._lock:
            events = self._events
            self._events = []
        if not events or self.client is None:
            return
        try:
            self.client.send_events(events)
        except Exception:
            with self._lock:
                self._events = events + self._events

    async def aflush(self) -> None:
        import asyncio

        await asyncio.to_thread(self.flush)
