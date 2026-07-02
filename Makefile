.PHONY: core-build core-run app-build app-run app-up app-stop app-restart devcontainer-build test test-ay-not-dead collect-data


core-build:
	docker compose build ropa-core

core-run:
	docker compose run ropa-core


devcontainer-build: core-build
	docker compose -f .devcontainer/docker-compose.yml build ropa-devcontainer


redis-start:
	docker compose up -d ropa-redis

redis-stop:
	docker compose stop ropa-redis

redis-flush:
	docker compose exec ropa-redis redis-cli FLUSHALL

redis-restart: redis-stop
	docker compose up -d ropa-redis


mongo-start:
	docker compose up -d ropa-mongo

mongo-stop:
	docker compose stop ropa-mongo

mongo-restart: mongo-stop mongo-start


app-build: core-build
	docker compose build ropa-app

app-run: app-build
	docker compose run --rm ropa-app

app-up: app-build
	docker compose up -d ropa-app

app-stop:
	docker stop ropa-app

app-restart: app-stop app-up


test: app-build
	docker compose run --rm ropa-app pytest -s tests

collect-data: app-build mongo-start
	docker compose run --rm ropa-app collect_data
