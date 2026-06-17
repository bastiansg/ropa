.PHONY: core-build core-run app-build app-run app-up app-stop app-restart devcontainer-build test test-ay-not-dead


core-build:
	docker compose build ropa-core

core-run:
	docker compose run ropa-core


devcontainer-build: core-build
	docker compose -f .devcontainer/docker-compose.yml build ropa-devcontainer


test: app-build
	docker compose run --rm ropa-app pytest -s tests


app-build: core-build
	docker compose build ropa-app

app-run: app-build
	docker compose run --rm ropa-app

app-up: app-build
	docker compose up -d ropa-app

app-stop:
	docker stop ropa-app

app-restart: app-stop app-up
