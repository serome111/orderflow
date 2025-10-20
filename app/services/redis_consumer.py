from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from redis.asyncio import Redis

from app.schemas.order import OrderCreate
from app.services.order_processor import OrderProcessor

logger = logging.getLogger("orderflow.redis_consumer")


class RedisOrderConsumer:
    """Consume orders from a Redis list and feed them into the OrderProcessor."""

    def __init__(
        self,
        redis: Redis,
        queue_name: str,
        *,
        poll_timeout: int = 1,
    ) -> None:
        self._redis = redis
        self._queue_name = queue_name
        self._poll_timeout = max(1, poll_timeout)
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._processor: OrderProcessor | None = None

    async def start(self, processor: OrderProcessor) -> None:
        if self._task:
            return
        self._processor = processor
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="redis-order-consumer")
        logger.info("RedisOrderConsumer started for queue '%s'.", self._queue_name)

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        await self._task
        self._task = None
        logger.info("RedisOrderConsumer stopped.")

    async def _run(self) -> None:
        assert self._processor is not None
        processor = self._processor
        while not self._stop_event.is_set():
            try:
                data = await self._redis.blpop(self._queue_name, timeout=self._poll_timeout)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                logger.exception("Error reading from Redis: %s", exc)
                await asyncio.sleep(1)
                continue

            if not data:
                continue

            _, payload = data
            try:
                raw: Any = json.loads(payload)
                order = OrderCreate.model_validate(raw)
            except Exception as exc:  # noqa: BLE001
                logger.error("Invalid payload received from Redis: %s (%s)", payload, exc)
                continue

            logger.info("Order %s read from Redis.", order.id)
            await processor.enqueue(order)

    async def close(self) -> None:
        await self._redis.aclose()
