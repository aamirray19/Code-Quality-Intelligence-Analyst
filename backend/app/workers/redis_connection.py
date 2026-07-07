import redis

from app.core.config import settings

_connection: redis.Redis | None = None


def get_redis_connection() -> redis.Redis:
    global _connection
    if _connection is None:
        _connection = redis.from_url(settings.redis_url)
    return _connection
