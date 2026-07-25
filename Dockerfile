# syntax=docker/dockerfile:1.7

FROM python:3.13.14-slim-bookworm AS builder

WORKDIR /code

RUN python -m venv /app/.venv

ENV PATH="/app/.venv/bin:${PATH}"

COPY requirements.txt ./

RUN pip install \
        --no-cache-dir \
        -r requirements.txt


FROM python:3.13.14-slim-bookworm AS runtime

WORKDIR /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd \
        --gid 10001 \
        vigilia \
    && useradd \
        --uid 10001 \
        --gid 10001 \
        --no-create-home \
        --shell /usr/sbin/nologin \
        vigilia

COPY --from=builder \
    --chown=vigilia:vigilia \
    /app/.venv \
    /app/.venv

COPY --chown=vigilia:vigilia app ./app
COPY --chown=vigilia:vigilia migrations ./migrations
COPY --chown=vigilia:vigilia alembic.ini ./

USER vigilia

EXPOSE 8000

CMD [
    "uvicorn",
    "app.main:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8000"
]