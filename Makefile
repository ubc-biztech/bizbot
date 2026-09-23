.PHONY: build up down restart logs status

build:
	docker build -t bizbot:local .

up:
	docker compose up -d --build --wait --wait-timeout 180

down:
	docker compose down

restart:
	docker compose restart bizbot

logs:
	docker compose logs --follow --tail=100 bizbot

status:
	docker compose ps
