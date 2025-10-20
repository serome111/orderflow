from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Iterable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from app.schemas.order import OrderCreate
from app.services.order_processor import OrderProcessor
from app.services.product_provider import ProductLookupError, ProductProvider


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


class StubProvider(ProductProvider):
    def __init__(self, products: dict[str, dict], *, fail_times: int = 0) -> None:
        self._products = products
        self.fail_times = fail_times
        self.calls = 0

    async def get_many(self, skus: Iterable[str]) -> dict[str, dict]:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ProductLookupError("simulated failure")
        return {sku: self._products.get(sku, {}) for sku in skus}


async def create_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        echo=False,
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS processed_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER UNIQUE,
                    customer VARCHAR(120),
                    submitted_at TIMESTAMP,
                    total FLOAT,
                    discount FLOAT,
                    final_total FLOAT,
                    hash_id VARCHAR(64) UNIQUE,
                    items JSON,
                    extra JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def sample_order(order_id: int = 1) -> OrderCreate:
    return OrderCreate.model_validate(
        {
            "id": order_id,
            "customer": "ACME Corp",
            "submitted_at": "2025-01-01T10:30:00Z",
            "items": [
                {"sku": "P001", "quantity": 3, "unit_price": 10},
                {"sku": "P002", "quantity": 5, "unit_price": 20},
            ],
        }
    )


async def test_order_is_processed_and_persisted():
    session_factory = await create_session_factory()
    provider = StubProvider(
        {
            "P001": {"id": 1, "title": "Widget", "price": 120, "category": "tools"},
            "P002": {"id": 2, "title": "Gadget", "price": 55.5, "category": "tech"},
        }
    )
    processor = OrderProcessor(
        session_factory,
        product_provider=provider,
        concurrency=1,
        max_retries=1,
    )

    await processor.start()
    order = sample_order(42)
    await processor.enqueue(order)
    await asyncio.wait_for(processor.wait_for_all(), timeout=2)

    stored = await processor.get_processed(order.id)
    assert stored is not None
    assert stored.order_id == order.id
    assert stored.total > 0
    assert stored.final_total <= stored.total
    assert stored.hash_id
    assert len(stored.items) == 2
    assert provider.calls == 1

    await processor.stop()


async def test_order_retries_on_failure():
    session_factory = await create_session_factory()
    provider = StubProvider(
        {
            "P001": {"id": 1, "title": "Widget", "price": 120},
        },
        fail_times=1,
    )
    processor = OrderProcessor(
        session_factory,
        product_provider=provider,
        concurrency=1,
        max_retries=2,
    )

    await processor.start()
    order = OrderCreate.model_validate(
        {
            "id": 7,
            "customer": "Retry Co",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "items": [{"sku": "P001", "quantity": 1, "unit_price": 99}],
        }
    )
    await processor.enqueue(order)
    await asyncio.wait_for(processor.wait_for_all(), timeout=2)

    stored = await processor.get_processed(order.id)
    assert stored is not None
    assert provider.calls == 2  # first failure + successful retry

    await processor.stop()


async def test_duplicate_orders_are_ignored():
    session_factory = await create_session_factory()
    provider = StubProvider({"P001": {"id": 1, "price": 10}})
    processor = OrderProcessor(
        session_factory,
        product_provider=provider,
        concurrency=1,
        max_retries=1,
    )

    await processor.start()
    order = OrderCreate.model_validate(
        {
            "id": 99,
            "customer": "Dup Corp",
            "submitted_at": "2025-01-01T10:30:00Z",
            "items": [{"sku": "P001", "quantity": 1, "unit_price": 5}],
        }
    )
    await processor.enqueue(order)
    await asyncio.wait_for(processor.wait_for_all(), timeout=2)
    assert provider.calls == 1

    await processor.enqueue(order)
    await asyncio.sleep(0.1)
    assert provider.calls == 1  # no additional calls

    await processor.stop()
