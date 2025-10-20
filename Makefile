run:
    uvicorn app.main:app --reload

test:
    pytest -q

build:
    docker build -t myapp:latest .

up:
    docker compose up -d --build

down:
    docker compose down
