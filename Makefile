# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# ...existing code...

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build

revision:
	docker compose exec api poetry run alembic revision --autogenerate -m "auto"

migrate:
	docker compose exec api poetry run alembic upgrade head

format:
	docker compose exec api poetry run black app tests
	docker compose exec api poetry run isort app tests

test:
	docker compose exec api poetry run pytest
