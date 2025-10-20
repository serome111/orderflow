# Orderflow Demo

FastAPI project that addresses the three parts of the technical exercise:

- **Part 1** – Asynchronous workflow with an internal queue to validate, enrich via FakeStore API, calculate totals/hash IDs, and persist orders in SQLite.
- **Part 2** – Extensible catalog of transformation functions (`app/functions`) with a CLI (`main.py`).
- **Part 3** – Event-oriented design plus an optional Redis consumer to evolve toward a data bus.

---

## Requirements

- Python 3.11 (or activate the provided `.venv`).
- Dependencies: `pip install -r requirements.txt`.
- Docker (optional) to run Redis or containerize the app.

### Environment configuration

Copy the example file and customize values as needed:

```bash
cp .env.example .env
```

Leave `ORDER_QUEUE_REDIS_URL` blank to skip the optional Redis consumer, or set it to a value such as `redis://localhost:6379/0` when running Redis locally.

---

## Run the API

```bash
uvicorn app.main:app --reload
```

Key endpoints:

- `POST /api/v1/orders` → Enqueue orders for asynchronous processing.
- `GET /api/v1/orders` → List processed orders.
- `GET /api/v1/orders/{order_id}` → Retrieve a processed order.
- `GET /health` → Basic health check.

Sample payload:

```json
{
  "id": 123,
  "customer": "ACME Corp",
  "items": [
    {"sku": "P001", "quantity": 3, "unit_price": 10},
    {"sku": "P002", "quantity": 5, "unit_price": 20}
  ],
  "submitted_at": "2025-01-01T10:30:00Z"
}
```

Each SKU must end with the FakeStore numeric ID (`https://fakestoreapi.com/products/{id}`) so enrichment can succeed.

---

## Docker Compose

The provided `docker-compose.yml` runs the API with SQLite. Data files are stored in the `data/` directory on the host, so the database persists across container restarts.

```bash
docker compose up --build
```

Stop the stack with:

```bash
docker compose down
```

---

## Optional Redis Consumer

1. Start Redis (example):
   ```bash
   docker run -p 6379:6379 redis:7
   ```

2. Export the URL before starting the app:
   ```bash
   export ORDER_QUEUE_REDIS_URL=redis://localhost:6379/0
   uvicorn app.main:app --reload
   ```

3. Publish orders to the queue (defaults to `orderflow:orders`):
   ```bash
   python seed_orders.py --mode redis --count 50
   ```

The consumer (`app/services/redis_consumer.py`) reads the messages and forwards them to the existing `OrderProcessor`.

---

## Generate Sample Data

Use `seed_orders.py` to populate the queue or the API:

```bash
# 100 orders via API
python seed_orders.py --mode api --count 100 --base-url http://localhost:8000

# 100 orders via Redis
python seed_orders.py --mode redis --count 100 --redis-url redis://localhost:6379/0
```

---

## Transformation Functions (Part 2)

```bash
python main.py --list               # show registered functions
python main.py add 5 7              # prints 12
python main.py to_lowercase HOLA
```

To add a function, create a module under `app/functions/` and decorate it with `@register()`.

---

## Tests

```bash
pytest
```

Includes tests for the API, transformation functions, and order processor.

---

## Architecture (Part 3 summary)

- Asynchronous OrderProcessor with worker pool.
- Enrichment via FakeStore API.
- Persistence in SQLite (can be swapped for Postgres in multi-instance setups).
- Optional external data bus (Redis) to decouple producers/consumers.
- Extensible toward Kafka/NATS and multi-tenant pipelines.
