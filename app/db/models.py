from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class Item(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(String(500), default="")


class ProcessedOrder(Base):
    __tablename__ = "processed_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(unique=True, index=True)
    customer: Mapped[str] = mapped_column(String(120), index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    total: Mapped[float] = mapped_column(Float)
    discount: Mapped[float] = mapped_column(Float)
    final_total: Mapped[float] = mapped_column(Float)
    hash_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    items: Mapped[dict] = mapped_column(JSON)
    extra: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
