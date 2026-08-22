.PHONY: core-build core-run app-build app-run app-up app-stop app-restart devcontainer-build collect-data collect-ay-not-dead collect-bolivia-universo collect-ropa-revolver extract-size-guides catalog-stats size-guide-stats segment-test-body


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


collect-data: app-build mongo-start
	docker compose run --rm ropa-app collect_data

collect-ay-not-dead: app-build mongo-start
	docker compose run --rm ropa-app collect_ay_not_dead

collect-bolivia-universo: app-build mongo-start
	docker compose run --rm ropa-app collect_bolivia_universo

collect-ropa-revolver: app-build mongo-start
	docker compose run --rm ropa-app collect_ropa_revolver

extract-size-guides: app-build mongo-start redis-start
	docker compose run --rm ropa-app python -m ropa.scripts.extract_size_guides

catalog-stats: app-build mongo-start
	docker compose run --rm ropa-app catalog_stats

size-guide-stats: app-build mongo-start
	docker compose run --rm ropa-app size_guide_stats

segment-test-body: app-build
	docker compose run --rm -v "$(CURDIR)/resources:/src/resources" ropa-app segment_test_body
