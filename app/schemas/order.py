from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class OrderProduct(BaseModel):
    sku: str = Field(min_length=1, max_length=50)
    quantity: int = Field(gt=0)
    unit_price: float = Field(gt=0)

    @field_validator("unit_price")
    @classmethod
    def _price_precision(cls, value: float) -> float:
        return round(float(value), 2)


class OrderCreate(BaseModel):
    id: int = Field(gt=0)
    customer: str = Field(min_length=1, max_length=120)
    items: list[OrderProduct]
    submitted_at: datetime

    @model_validator(mode="after")
    def _check_items(self) -> "OrderCreate":
        if not self.items:
            raise ValueError("The order must include at least one product.")
        return self


class EnrichedProduct(BaseModel):
    sku: str
    quantity: int
    unit_price: float
    api_id: int | None = None
    title: str | None = None
    api_price: float | None = None
    category: str | None = None
    description: str | None = None
    line_total: float


class ProcessedOrderRead(BaseModel):
    order_id: int
    customer: str
    submitted_at: datetime
    total: float
    discount: float
    final_total: float
    hash_id: str
    items: list[EnrichedProduct]
    extra: dict[str, Any] | None = None
    created_at: datetime
