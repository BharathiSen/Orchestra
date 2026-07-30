from redis import Redis

from app.core.config import settings


def normalize_redis_url(url: str) -> str:
    """Accept a bare redis URL or a pasted Upstash `redis-cli --tls -u ...` snippet."""
    value = (url or "").strip()
    if not value:
        return value

    for scheme in ("rediss://", "redis://", "unix://"):
        idx = value.find(scheme)
        if idx >= 0:
            value = value[idx:].split()[0]
            break

    # Upstash requires TLS; CLI uses --tls with redis:// — Python needs rediss://
    if value.startswith("redis://") and "upstash.io" in value:
        value = "rediss://" + value.removeprefix("redis://")

    return value


def get_redis() -> Redis:
    url = normalize_redis_url(settings.redis_url)
    if not url.startswith(("redis://", "rediss://", "unix://")):
        raise ValueError(
            "Redis URL must specify one of the following schemes "
            "(redis://, rediss://, unix://)"
        )
    return Redis.from_url(url, decode_responses=True)
