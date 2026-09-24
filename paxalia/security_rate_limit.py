"""Small cache-backed rate limiter for Paxalia authentication ceremonies."""
from __future__ import annotations

from hashlib import sha256

from django.core.cache import cache


def _key(scope: str, *parts: object) -> str:
    raw = "|".join([scope, *(str(part or "").strip().lower() for part in parts)])
    digest = sha256(raw.encode("utf-8", "ignore")).hexdigest()
    return f"paxalia:auth-rate:{scope}:{digest}"


def allowed(scope: str, limit: int, window_seconds: int, *parts: object) -> tuple[bool, int]:
    """Consume one attempt from a bounded counter.

    `cache.add` + `cache.incr` is used so common shared cache backends can
    perform the counter transition atomically enough for an authentication
    throttle. On backends without atomic increment support, the operation still
    fails closed only for the counter itself and the persistent security logger
    remains the secondary signal. Cache outages intentionally fail open so the
    limiter never becomes an authentication availability dependency.
    """
    limit = max(1, int(limit))
    window_seconds = max(1, int(window_seconds))
    key = _key(scope, *parts)
    try:
        current = cache.get(key)
        if current is None:
            if not cache.add(key, 1, timeout=window_seconds):
                current = int(cache.get(key, 0) or 0)
            else:
                return True, max(0, limit - 1)
        else:
            current = int(current or 0)

        if current >= limit:
            return False, 0
        try:
            new_value = int(cache.incr(key))
        except Exception:
            new_value = current + 1
            cache.set(key, new_value, timeout=window_seconds)
        return new_value <= limit, max(0, limit - new_value)
    except Exception:
        # Availability wins over the limiter itself; the existing persistent
        # failed-login logging/alerting remains a second signal.
        return True, limit


def clear(scope: str, *parts: object) -> None:
    try:
        cache.delete(_key(scope, *parts))
    except Exception:
        pass
