from pydantic import BaseModel, Field

class ItemBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)

class ItemCreate(ItemBase):
    pass

class ItemRead(ItemBase):
    id: int
