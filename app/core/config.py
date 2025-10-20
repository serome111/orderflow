from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    API_PREFIX: str = "/api/v1"
    DB_URL: str = Field(default="sqlite+aiosqlite:///./app.db")
    CORS_ORIGINS: list[str] = ["*"]
    ORDER_REDIS_URL: str | None = Field(default=None, alias="ORDER_QUEUE_REDIS_URL")
    ORDER_REDIS_QUEUE: str = Field(default="orderflow:orders")

    class Config:
        env_file = ".env"

settings = Settings()
