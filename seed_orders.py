#!/usr/bin/env python3
"""
Utility script to generate sample orders and validate the pipeline.

Quick usage:
    python seed_orders.py --mode api --count 50             # Send to the local API
    python seed_orders.py --mode redis --count 50 --redis-url redis://localhost:6379/0

The generated SKUs end with the numeric id expected by https://fakestoreapi.com,
so the OrderProcessor can enrich the products when processing them.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
from datetime import datetime, timezone
from typing import Iterable

import httpx

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - Redis mode is optional
    Redis = None  # type: ignore[assignment]

SKU_POOL = [f"P{i:03d}" for i in range(1, 21)]  # FakeStore API has ids 1 through 20


def build_order(order_id: int) -> dict:
    num_items = random.randint(1, 4)
    selected_skus = random.sample(SKU_POOL, k=num_items)
    items: list[dict[str, object]] = []
    for sku in selected_skus:
        items.append(
            {
                "sku": sku,
                "quantity": random.randint(1, 5),
                "unit_price": round(random.uniform(5, 150), 2),
            }
        )
    return {
        "id": order_id,
        "customer": f"Customer {order_id}",
        "items": items,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }


async def publish_api(
    base_url: str,
    orders: Iterable[dict],
    *,
    concurrency: int = 10,
) -> None:
    semaphore = asyncio.Semaphore(concurrency)

    async def _send(client: httpx.AsyncClient, order: dict) -> None:
        async with semaphore:
            resp = await client.post("/api/v1/orders", json=order)
            resp.raise_for_status()

    async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
        await asyncio.gather(*[_send(client, order) for order in orders])


async def publish_redis(
    redis_url: str,
    queue: str,
    orders: Iterable[dict],
) -> None:
    if Redis is None:
        raise RuntimeError(
            "Install the 'redis' package to enable Redis mode (pip install redis)."
        )
    redis = Redis.from_url(redis_url)
    try:
        await redis.ping()
        for order in orders:
            await redis.rpush(queue, json.dumps(order))
    finally:
        await redis.aclose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample order generator.")
    parser.add_argument(
        "--mode",
        choices=("api", "redis"),
        default="api",
        help="Destination for the orders.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of orders to generate.",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API base URL (api mode).",
    )
    parser.add_argument(
        "--redis-url",
        default="redis://localhost:6379/0",
        help="Redis URL (redis mode).",
    )
    parser.add_argument(
        "--redis-queue",
        default="orderflow:orders",
        help="Redis list name (redis mode).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional seed to generate reproducible data.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    orders = [build_order(order_id) for order_id in range(1, args.count + 1)]

    if args.mode == "api":
        print(f"Sending {args.count} orders to {args.base_url} ...")
        asyncio.run(publish_api(args.base_url, orders))
    else:
        print(f"Pushing {args.count} orders to Redis {args.redis_url}/{args.redis_queue} ...")
        asyncio.run(publish_redis(args.redis_url, args.redis_queue, orders))
    print("Done.")


if __name__ == "__main__":
    main()
