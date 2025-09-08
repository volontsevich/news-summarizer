# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# ...existing code...

FROM python:3.11-slim
WORKDIR /app
COPY ./app /app/app
COPY ./alembic /app/alembic
COPY ./alembic.ini ./pyproject.toml ./poetry.lock* /app/
COPY ./tests /app/tests
RUN pip install --upgrade pip && pip install poetry && poetry install --with dev
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
