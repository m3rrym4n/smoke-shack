FROM python:3.12.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --system smoke && useradd --system --gid smoke --create-home smoke
WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY migrations ./migrations
COPY config ./config
RUN pip install --no-cache-dir .
RUN mkdir -p /data/photos && chown -R smoke:smoke /data /app

USER smoke
VOLUME ["/data"]
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
