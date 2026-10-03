FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY apps/api/pyproject.toml apps/api/requirements.lock ./
COPY apps/api/app ./app
RUN python -m pip wheel --wheel-dir /wheels --constraint requirements.lock .

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/home/insighthr/.local/bin:${PATH}

RUN groupadd --gid 10001 insighthr \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin insighthr

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels insighthr-api \
    && rm -rf /wheels
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/alembic ./alembic

USER 10001:10001
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

