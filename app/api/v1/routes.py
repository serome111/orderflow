from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.db.models import Item
from app.schemas.item import ItemCreate, ItemRead
from app.schemas.order import OrderCreate, ProcessedOrderRead
from app.services.order_processor import OrderProcessor

router = APIRouter()


@router.post("/items", response_model=ItemRead, tags=["items"])
async def create_item(payload: ItemCreate, db: AsyncSession = Depends(get_db)):
    item = Item(name=payload.name, description=payload.description or "")
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return ItemRead.model_validate(item.__dict__)


@router.get("/items", response_model=list[ItemRead], tags=["items"])
async def list_items(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Item))
    rows = res.scalars().all()
    return [ItemRead.model_validate(i.__dict__) for i in rows]


def _get_processor(request: Request) -> OrderProcessor:
    processor = getattr(request.app.state, "order_processor", None)
    if processor is None:
        raise HTTPException(status_code=500, detail="Order processor unavailable.")
    return processor


@router.post("/orders", status_code=status.HTTP_202_ACCEPTED, tags=["orders"])
async def enqueue_order(payload: OrderCreate, request: Request):
    processor = _get_processor(request)
    await processor.enqueue(payload)
    return {"status": "accepted", "order_id": payload.id}


@router.get("/orders", response_model=list[ProcessedOrderRead], tags=["orders"])
async def list_orders(request: Request, limit: int = 50):
    processor = _get_processor(request)
    return await processor.list_processed(limit=limit)


@router.get(
    "/orders/{order_id}",
    response_model=ProcessedOrderRead,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Order not found"}},
    tags=["orders"],
)
async def get_order(order_id: int, request: Request):
    processor = _get_processor(request)
    processed = await processor.get_processed(order_id)
    if processed is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return processed
