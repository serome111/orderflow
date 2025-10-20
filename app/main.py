from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.api.v1.routes import router as api_router
from app.core.config import settings
from app.db.session import async_session, init_models
from app.services.order_processor import OrderProcessor
from app.services.redis_consumer import RedisOrderConsumer

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - Redis is optional in tests
    Redis = None  # type: ignore[assignment]

logger = logging.getLogger("orderflow.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    processor = OrderProcessor(async_session)
    await processor.start()
    app.state.order_processor = processor

    redis_consumer: RedisOrderConsumer | None = None
    if settings.ORDER_REDIS_URL and Redis is not None:
        redis_client = Redis.from_url(settings.ORDER_REDIS_URL)
        try:
            await redis_client.ping()
        except Exception as exc:  # noqa: BLE001
            await redis_client.aclose()
            logger.warning("Failed to connect to Redis (%s). Continuing without consumer.", exc)
        else:
            redis_consumer = RedisOrderConsumer(
                redis_client,
                queue_name=settings.ORDER_REDIS_QUEUE,
            )
            await redis_consumer.start(processor)
    elif settings.ORDER_REDIS_URL and Redis is None:
        logger.warning(
            "Redis is not installed; skipping consumer. Install 'redis' to enable it."
        )
    app.state.redis_consumer = redis_consumer

    try:
        yield
    finally:
        if redis_consumer:
            await redis_consumer.stop()
            await redis_consumer.close()
        await processor.stop()


app = FastAPI(title="MyApp API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(api_router, prefix="/api/v1")
