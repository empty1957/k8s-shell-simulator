.PHONY: build up down logs clean

build:
	docker compose build

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f simulator

clean:
	docker compose down -v
