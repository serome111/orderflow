from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import ProcessedOrder
from app.schemas.order import EnrichedProduct, OrderCreate, ProcessedOrderRead
from app.services.product_provider import (
    FakeStoreProductProvider,
    ProductLookupError,
    ProductProvider,
)

logger = logging.getLogger("orderflow.order_processor")


@dataclass(slots=True)
class QueueJob:
    payload: OrderCreate
    attempt: int = 0


class OrderProcessor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        product_provider: ProductProvider | None = None,
        concurrency: int = 4,
        max_retries: int = 3,
        hash_factory: Callable[[OrderCreate, float], str] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._product_provider = product_provider or FakeStoreProductProvider()
        self._concurrency = max(1, concurrency)
        self._max_retries = max(0, max_retries)
        self._hash_factory = hash_factory or self._default_hash_factory

        self._queue: asyncio.Queue[QueueJob] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        if self._workers:
            return
        self._shutdown_event.clear()
        for index in range(self._concurrency):
            task = asyncio.create_task(
                self._worker_loop(index), name=f"order-worker-{index}"
            )
            self._workers.append(task)
        logger.info("OrderProcessor started with %s workers.", self._concurrency)

    async def stop(self) -> None:
        self._shutdown_event.set()
        await self._queue.join()
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("OrderProcessor stopped.")

    async def enqueue(self, order: OrderCreate | dict[str, Any]) -> None:
        payload = order if isinstance(order, OrderCreate) else OrderCreate.model_validate(order)
        if await self._is_already_processed(payload.id):
            logger.info("Order %s already processed; ignoring new request.", payload.id)
            return
        await self._queue.put(QueueJob(payload=payload))
        logger.info("Order %s queued.", payload.id)

    async def wait_for_all(self) -> None:
        """Wait for the queue to finish processing all pending items."""
        await self._queue.join()

    async def _worker_loop(self, worker_id: int) -> None:
        logger.debug("Worker %s started.", worker_id)
        while True:
            if self._shutdown_event.is_set() and self._queue.empty():
                break
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            try:
                await self._process_job(job, worker_id)
            finally:
                self._queue.task_done()
        logger.debug("Worker %s finished.", worker_id)

    async def _process_job(self, job: QueueJob, worker_id: int) -> None:
        order = job.payload
        if await self._is_already_processed(order.id):
            logger.info("Order %s was already processed; skipping.", order.id)
            return

        try:
            processed = await self._process_order(order)
            await self._persist_processed(order, processed)
            logger.info("Order %s processed by worker %s.", order.id, worker_id)
        except ProductLookupError as exc:
            await self._handle_failure(job, exc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error processing order %s", order.id)
            await self._handle_failure(job, exc)

    async def _handle_failure(self, job: QueueJob, exc: Exception) -> None:
        if self._shutdown_event.is_set():
            logger.warning(
                "Failed processing order %s during shutdown: %s",
                job.payload.id,
                exc,
            )
            return
        if job.attempt < self._max_retries:
            job.attempt += 1
            await self._queue.put(job)
            logger.warning(
                "Failed processing order %s (attempt %s/%s): %s. Retrying.",
                job.payload.id,
                job.attempt,
                self._max_retries,
                exc,
            )
        else:
            logger.error(
                "Failed processing order %s after %s attempts: %s",
                job.payload.id,
                self._max_retries,
                exc,
            )

    async def _process_order(self, order: OrderCreate) -> ProcessedOrderRead:
        product_data = await self._product_provider.get_many(
            [product.sku for product in order.items]
        )

        enriched: list[EnrichedProduct] = []
        subtotal = 0.0

        for product in order.items:
            api_info = product_data.get(product.sku) or {}
            api_price_raw = api_info.get("price")
            api_price = round(float(api_price_raw), 2) if api_price_raw is not None else None
            unit_price = api_price if api_price is not None else product.unit_price
            line_total = round(unit_price * product.quantity, 2)
            subtotal += line_total

            enriched.append(
                EnrichedProduct(
                    sku=product.sku,
                    quantity=product.quantity,
                    unit_price=product.unit_price,
                    api_id=api_info.get("id"),
                    title=api_info.get("title"),
                    api_price=api_price,
                    category=api_info.get("category"),
                    description=api_info.get("description"),
                    line_total=line_total,
                )
            )

        subtotal = round(subtotal, 2)
        discount = round(subtotal * 0.10, 2) if subtotal > 500 else 0.0
        final_total = round(subtotal - discount, 2)
        hash_id = self._hash_factory(order, final_total)

        return ProcessedOrderRead(
            order_id=order.id,
            customer=order.customer,
            submitted_at=order.submitted_at,
            total=subtotal,
            discount=discount,
            final_total=final_total,
            hash_id=hash_id,
            items=enriched,
            extra={"discount_rule": "10% on orders > 500"},
            created_at=datetime.now(timezone.utc),
        )

    async def _persist_processed(
        self,
        order: OrderCreate,
        processed: ProcessedOrderRead,
    ) -> None:
        async with self._session_factory() as session:
            existing = await session.scalar(
                select(ProcessedOrder).where(ProcessedOrder.order_id == order.id)
            )
            payload_json = [
                product.model_dump(mode="json") for product in processed.items
            ]
            if existing:
                existing.customer = processed.customer
                existing.submitted_at = processed.submitted_at
                existing.total = processed.total
                existing.discount = processed.discount
                existing.final_total = processed.final_total
                existing.hash_id = processed.hash_id
                existing.items = payload_json
                existing.extra = processed.extra
            else:
                session.add(
                    ProcessedOrder(
                        order_id=processed.order_id,
                        customer=processed.customer,
                        submitted_at=processed.submitted_at,
                        total=processed.total,
                        discount=processed.discount,
                        final_total=processed.final_total,
                        hash_id=processed.hash_id,
                        items=payload_json,
                        extra=processed.extra,
                    )
                )

            await session.commit()

    async def _is_already_processed(self, order_id: int) -> bool:
        async with self._session_factory() as session:
            exists = await session.scalar(
                select(ProcessedOrder.order_id).where(ProcessedOrder.order_id == order_id)
            )
            return exists is not None

    @staticmethod
    def _default_hash_factory(order: OrderCreate, final_total: float) -> str:
        payload = json.dumps(
            {
                "order_id": order.id,
                "customer": order.customer,
                "submitted_at": order.submitted_at.isoformat(),
                "final_total": final_total,
            },
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    async def list_processed(self, limit: int = 50) -> list[ProcessedOrderRead]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ProcessedOrder)
                .order_by(ProcessedOrder.created_at.desc())
                .limit(limit)
            )
            rows = result.scalars().all()
            return [
                ProcessedOrderRead(
                    order_id=row.order_id,
                    customer=row.customer,
                    submitted_at=row.submitted_at,
                    total=row.total,
                    discount=row.discount,
                    final_total=row.final_total,
                    hash_id=row.hash_id,
                    items=[
                        EnrichedProduct.model_validate(product)
                        for product in (row.items or [])
                    ],
                    extra=row.extra,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    async def get_processed(self, order_id: int) -> ProcessedOrderRead | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(ProcessedOrder).where(ProcessedOrder.order_id == order_id)
            )
            if row is None:
                return None
            return ProcessedOrderRead(
                order_id=row.order_id,
                customer=row.customer,
                submitted_at=row.submitted_at,
                total=row.total,
                discount=row.discount,
                final_total=row.final_total,
                hash_id=row.hash_id,
                items=[
                    EnrichedProduct.model_validate(product)
                    for product in (row.items or [])
                ],
                extra=row.extra,
                created_at=row.created_at,
            )
