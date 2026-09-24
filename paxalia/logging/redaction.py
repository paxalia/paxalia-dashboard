"""Centralized redaction and payload bounding for Paxalia logs."""
import json
import re
from collections.abc import Mapping


DEFAULT_SENSITIVE_KEYS = {
    "authorization", "proxyauthorization", "cookie", "setcookie",
    "password", "passwd", "secret", "token", "accesstoken", "refreshtoken",
    "csrf", "csrftoken", "apikey", "apikeys", "privatekey", "clientsecret",
    "signingsecret", "sessionkey", "secretkey", "credential", "credentials",
}

_BEARER_RE = re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]+")
_BASIC_RE = re.compile(r"(?i)(\bBasic\s+)[A-Za-z0-9+/=]+")
_QUERY_SECRET_RE = re.compile(
    r"(?i)([?&](?:password|passwd|token|secret|api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token|csrf[_-]?token)=)[^&#\s]+"
)
_SECRET_PAIR_RE = re.compile(
    r"(?i)(\b(?:password|passwd|token|secret|api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token|csrf[_-]?token)\s*[=:]\s*)[^\s,;]+"
)


_ANSI_ESCAPE_RE = re.compile(
    r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
)


def strip_ansi(value):
    """Remove terminal/console ANSI control sequences from log text."""
    if value is None:
        return ""
    return _ANSI_ESCAPE_RE.sub("", str(value))


def _normalise_key(key):
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def _sensitive_keys(extra=None):
    keys = set(DEFAULT_SENSITIVE_KEYS)
    for key in extra or ():
        keys.add(_normalise_key(key))
    return keys


def redact_text(value):
    """Redact common credential formats embedded in a string."""
    if value is None:
        return ""
    value = str(value)
    value = _BEARER_RE.sub(r"\1[REDACTED]", value)
    value = _QUERY_SECRET_RE.sub(r"\1[REDACTED]", value)
    value = _BASIC_RE.sub(r"\1[REDACTED]", value)
    value = _SECRET_PAIR_RE.sub(r"\1[REDACTED]", value)
    return value


def redact(value, *, extra_keys=None, max_depth=6, max_items=100):
    """Recursively sanitize arbitrary application data without raising.

    Dictionaries are redacted by key; sequences are bounded; unknown objects
    are converted to bounded strings. This is intentionally conservative.
    """
    sensitive = _sensitive_keys(extra_keys)

    def _walk(obj, depth):
        if depth > max_depth:
            return "[TRUNCATED_DEPTH]"
        if obj is None or isinstance(obj, (bool, int, float)):
            return obj
        if isinstance(obj, str):
            return redact_text(obj[:4000])
        if isinstance(obj, bytes):
            return "[BYTES REDACTED]"
        if isinstance(obj, Mapping):
            result = {}
            for idx, (key, item) in enumerate(obj.items()):
                if idx >= max_items:
                    result["_paxalia_truncated"] = True
                    break
                key_str = str(key)[:200]
                if _normalise_key(key_str) in sensitive:
                    result[key_str] = "[REDACTED]"
                else:
                    result[key_str] = _walk(item, depth + 1)
            return result
        if isinstance(obj, (list, tuple, set, frozenset)):
            items = list(obj)
            result = [_walk(item, depth + 1) for item in items[:max_items]]
            if len(items) > max_items:
                result.append("[TRUNCATED_ITEMS]")
            return result
        try:
            return redact_text(str(obj)[:4000])
        except Exception:
            return "[UNSERIALIZABLE]"

    return _walk(value, 0)


def bound_json(value, *, max_bytes=16384, extra_keys=None):
    """Redact and JSON-size-bound structured data."""
    cleaned = redact(value, extra_keys=extra_keys)
    try:
        raw = json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"), default=str)
    except Exception:
        return {"_paxalia_error": "unserializable_metadata"}
    if len(raw.encode("utf-8")) <= max_bytes:
        return cleaned
    # Preserve the fact that content was truncated without silently dropping it.
    preview = redact_text(raw[: max(256, max_bytes // 2)])
    return {
        "_paxalia_truncated": True,
        "_paxalia_preview": preview,
    }
