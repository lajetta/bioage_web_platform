from __future__ import annotations

import os

import redis
from rq import Worker, Queue, Connection

from app.core.settings import settings


def main() -> None:
    listen = ["default"]
    redis_url = settings.redis_url
    conn = redis.from_url(redis_url)

    with Connection(conn):
        worker = Worker(map(Queue, listen))
        worker.work(with_scheduler=False)


if __name__ == "__main__":
    # Ensure module path
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()
