.PHONY: core-build core-run app-build app-run app-up app-stop app-restart devcontainer-build collect-data collect-ay-not-dead collect-bolivia-universo collect-ropa-revolver extract-size-guides catalog-stats size-guide-stats reconstruct-test-body


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


collect-data: devcontainer-build mongo-start
	docker compose -f .devcontainer/docker-compose.yml run --rm --entrypoint="env PYTHONPATH=/workspace/src python -m ropa.scripts.collect_data" ropa-devcontainer

collect-ay-not-dead: devcontainer-build mongo-start
	docker compose -f .devcontainer/docker-compose.yml run --rm --entrypoint="env PYTHONPATH=/workspace/src python -m ropa.scripts.collect_ay_not_dead" ropa-devcontainer

collect-bolivia-universo: devcontainer-build mongo-start
	docker compose -f .devcontainer/docker-compose.yml run --rm --entrypoint="env PYTHONPATH=/workspace/src python -m ropa.scripts.collect_bolivia_universo" ropa-devcontainer

collect-ropa-revolver: devcontainer-build mongo-start
	docker compose -f .devcontainer/docker-compose.yml run --rm --entrypoint="env PYTHONPATH=/workspace/src python -m ropa.scripts.collect_ropa_revolver" ropa-devcontainer

extract-size-guides: devcontainer-build mongo-start redis-start
	docker compose -f .devcontainer/docker-compose.yml run --rm --entrypoint="env PYTHONPATH=/workspace/src python -m ropa.scripts.extract_size_guides" ropa-devcontainer

catalog-stats: devcontainer-build mongo-start
	docker compose -f .devcontainer/docker-compose.yml run --rm --entrypoint="env PYTHONPATH=/workspace/src python -m ropa.scripts.catalog_stats" ropa-devcontainer

size-guide-stats: devcontainer-build mongo-start
	docker compose -f .devcontainer/docker-compose.yml run --rm --entrypoint="env PYTHONPATH=/workspace/src python -m ropa.scripts.size_guide_stats" ropa-devcontainer

reconstruct-test-body: devcontainer-build
	docker compose -f .devcontainer/docker-compose.yml run --rm --entrypoint="env PYTHONPATH=/workspace/src python -m ropa.scripts.reconstruct_test_body" ropa-devcontainer
