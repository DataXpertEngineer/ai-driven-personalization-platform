"""Redis cache for recent user sessions and recommendations."""
import json
import redis
from src.utils.config import settings


def get_redis_client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def cache_recommendations(user_id: str, payload: list[dict]) -> None:
    client = get_redis_client()
    key = f"recommendations:{user_id}"
    client.setex(key, settings.redis_ttl_seconds, json.dumps(payload))


def get_cached_recommendations(user_id: str) -> list[dict] | None:
    client = get_redis_client()
    key = f"recommendations:{user_id}"
    raw = client.get(key)
    if raw is None:
        return None
    return json.loads(raw)
