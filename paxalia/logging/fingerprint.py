"""Stable event fingerprinting/grouping for Paxalia logs."""
import hashlib
import json
import re

_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.I,
)
_LONG_HEX_RE = re.compile(r"\b[0-9a-f]{12,}\b", re.I)
_NUMBER_RE = re.compile(r"\b\d{2,}\b")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_message(message):
    value = str(message or "")
    value = _UUID_RE.sub("<uuid>", value)
    value = _LONG_HEX_RE.sub("<hex>", value)
    value = _NUMBER_RE.sub("<n>", value)
    value = _WHITESPACE_RE.sub(" ", value).strip()
    return value[:2000]


def build_fingerprint(*, source, severity, category, exception_type, message,
                      module, function_name, file_name, traffic_type):
    normalized = {
        "source": source or "Other",
        "severity": severity or "INFO",
        "category": category or "",
        "exception_type": exception_type or "",
        "message": normalize_message(message),
        "module": module or "",
        "function_name": function_name or "",
        "file_name": file_name or "",
        "traffic_type": traffic_type or "",
    }
    raw = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()
