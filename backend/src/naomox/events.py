"""Diffusion d'événements vers les clients SSE."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any


class EventBroker:
    def __init__(self, queue_size: int = 256) -> None:
        self._subscribers: set[asyncio.Queue[tuple[str, dict[str, Any]]]] = set()
        self._queue_size = queue_size

    @property
    def subscribers(self) -> int:
        return len(self._subscribers)

    def publish(self, event: str, data: dict[str, Any]) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait((event, data))
            except asyncio.QueueFull:
                # Client trop lent : on lui retire le plus ancien événement.
                with contextlib.suppress(asyncio.QueueEmpty):
                    q.get_nowait()
                q.put_nowait((event, data))

    async def stream(self, keepalive: float = 15.0) -> AsyncIterator[str]:
        """Flux au format text/event-stream."""
        q: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(self._queue_size)
        self._subscribers.add(q)
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    event, data = await asyncio.wait_for(q.get(), keepalive)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        finally:
            self._subscribers.discard(q)
