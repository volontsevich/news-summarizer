FROM python:3.11-slim
RUN groupadd -r appuser && useradd -r -g appuser appuser -m
WORKDIR /app
COPY ./app /app/app
COPY ./pyproject.toml ./poetry.lock* /app/
RUN chown -R appuser:appuser /app
USER appuser
RUN pip install --user poetry
ENV PATH="/home/appuser/.local/bin:$PATH"
RUN poetry install --no-root --only main
CMD ["poetry", "run", "celery", "-A", "app.tasks.celery_app:celery", "worker", "--loglevel=INFO"]