from __future__ import annotations

import asyncio
import re
from typing import Any, Iterable, Protocol

from app.utils.http_client import AsyncHTTP


class ProductProvider(Protocol):
    async def get_many(self, skus: Iterable[str]) -> dict[str, dict[str, Any]]:
        """Return product data keyed by SKU."""


class ProductLookupError(RuntimeError):
    """Raised when a product cannot be retrieved from the external service."""


class FakeStoreProductProvider:
    def __init__(
        self,
        *,
        base_url: str = "https://fakestoreapi.com",
        http_client_cls: type[AsyncHTTP] = AsyncHTTP,
        retries: int = 2,
        backoff: float = 0.5,
    ) -> None:
        self.base_url = base_url
        self._http_cls = http_client_cls
        self._retries = retries
        self._backoff = backoff
        self._sku_pattern = re.compile(r"(\d+)$")

    async def get_many(self, skus: Iterable[str]) -> dict[str, dict[str, Any]]:
        unique = {sku: self._extract_product_id(sku) for sku in set(skus)}
        async with self._http_cls(
            base_url=self.base_url, retries=self._retries, backoff=self._backoff
        ) as http:
            tasks = {
                sku: asyncio.create_task(http.get(f"/products/{product_id}"))
                for sku, product_id in unique.items()
            }

            results: dict[str, dict[str, Any]] = {}
            for sku, task in tasks.items():
                try:
                    results[sku] = await task
                except Exception as exc:  # noqa: BLE001
                    raise ProductLookupError(f"Failed to fetch product {sku}") from exc
            return results

    def _extract_product_id(self, sku: str) -> str:
        match = self._sku_pattern.search(sku)
        if not match:
            raise ProductLookupError(
                f"Could not infer product id from SKU '{sku}'. "
                "Use a SKU that ends with digits (e.g., 'P001')."
            )
        return str(int(match.group(1)))
