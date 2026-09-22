"""Canonical Paxalia .paxalia package container."""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import uuid
import zipfile
from datetime import datetime, timezone
from importlib import metadata

from django import VERSION as DJANGO_VERSION

FORMAT_NAME = "paxalia"
FORMAT_VERSION = 1
MANIFEST_MEMBER = "manifest.json"
DATA_MEMBER = "data.json"
ENCRYPTED_MEMBER = "data.enc"
INTEGRITY_MEMBER = "integrity.json"
ALLOWED_MEMBERS = {MANIFEST_MEMBER, DATA_MEMBER, ENCRYPTED_MEMBER, INTEGRITY_MEMBER}
MAX_MEMBER_COUNT = 8


def _json_bytes(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def paxalia_version() -> str:
    try:
        from .. import __version__
        return str(__version__)
    except Exception:
        try:
            return metadata.version("paxalia-dashboard")
        except Exception:
            return "development"


def build_package(payload: dict, *, encrypted_payload: bytes | None = None, package_id: str | None = None) -> bytes:
    package_id = package_id or str(uuid.uuid4())
    data_bytes = encrypted_payload if encrypted_payload is not None else _json_bytes(payload)
    encrypted = encrypted_payload is not None

    manifest = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "package_id": package_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "paxalia_version": paxalia_version(),
        "django_version": ".".join(str(x) for x in DJANGO_VERSION[:3]),
        "encrypted": encrypted,
        "encoding": "utf-8",
        "content_member": ENCRYPTED_MEMBER if encrypted else DATA_MEMBER,
        "models": payload.get("models", []),
        "record_count": int(payload.get("record_count", 0) or 0),
        "relationship_count": int(payload.get("relationship_count", 0) or 0),
        "translation_count": int(payload.get("translation_count", 0) or 0),
    }
    manifest_bytes = _json_bytes(manifest)
    integrity = {
        "version": 1,
        "algorithm": "sha256",
        "manifest": _sha256(manifest_bytes),
        "content": _sha256(data_bytes),
    }
    integrity_bytes = _json_bytes(integrity)

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr(MANIFEST_MEMBER, manifest_bytes)
        archive.writestr(INTEGRITY_MEMBER, integrity_bytes)
        archive.writestr(ENCRYPTED_MEMBER if encrypted else DATA_MEMBER, data_bytes)
    return output.getvalue()


def read_package(raw: bytes, *, max_size: int = 100 * 1024 * 1024) -> tuple[dict, bytes, bool]:
    if not raw:
        raise ValueError("The package is empty.")
    if len(raw) > max_size:
        raise ValueError("The package exceeds the configured maximum size.")
    if not raw.startswith(b"PK"):
        raise ValueError("The uploaded file is not a valid Paxalia package container.")

    try:
        archive = zipfile.ZipFile(io.BytesIO(raw), "r")
    except zipfile.BadZipFile as exc:
        raise ValueError("The Paxalia package archive is corrupted.") from exc

    try:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBER_COUNT:
            raise ValueError("The Paxalia package contains too many archive members.")
        member_names = [info.filename for info in infos]
        if len(member_names) != len(set(member_names)):
            raise ValueError("The Paxalia package contains duplicate archive members.")
        names = set(member_names)
        if not {MANIFEST_MEMBER, INTEGRITY_MEMBER}.issubset(names):
            raise ValueError("The Paxalia package is missing its manifest or integrity record.")
        if not names.issubset(ALLOWED_MEMBERS):
            raise ValueError("The Paxalia package contains unsupported archive members.")

        for info in infos:
            if info.filename != info.filename.strip() or ".." in info.filename.split("/"):
                raise ValueError("The Paxalia package contains an unsafe archive path.")
            if info.file_size > max_size:
                raise ValueError("A Paxalia package member exceeds the configured size limit.")
            if info.compress_size and info.file_size > max(info.compress_size * 200, 4 * 1024 * 1024):
                raise ValueError("The Paxalia package compression ratio is unsafe.")

        manifest_bytes = archive.read(MANIFEST_MEMBER)
        integrity_bytes = archive.read(INTEGRITY_MEMBER)
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        integrity = json.loads(integrity_bytes.decode("utf-8"))
        if manifest.get("format") != FORMAT_NAME:
            raise ValueError("This file is not a Paxalia package.")
        version = int(manifest.get("format_version") or 0)
        if version != FORMAT_VERSION:
            raise ValueError(f"Unsupported Paxalia package version: {version}.")
        if integrity.get("version") != 1 or integrity.get("algorithm") != "sha256":
            raise ValueError("Unsupported Paxalia package integrity metadata.")
        manifest_hash = integrity.get("manifest")
        if not isinstance(manifest_hash, str) or not hmac.compare_digest(_sha256(manifest_bytes), manifest_hash):
            raise ValueError("Paxalia package manifest integrity validation failed.")

        encrypted = bool(manifest.get("encrypted"))
        member = ENCRYPTED_MEMBER if encrypted else DATA_MEMBER
        content_members = names.intersection({DATA_MEMBER, ENCRYPTED_MEMBER})
        if content_members != {member}:
            raise ValueError("The Paxalia package must contain exactly one valid content member.")
        if manifest.get("content_member") != member:
            raise ValueError("Paxalia package content metadata does not match the archive.")
        if bool(manifest.get("encrypted")) != (member == ENCRYPTED_MEMBER):
            raise ValueError("Paxalia package encryption metadata is inconsistent.")
        content = archive.read(member)
        content_hash = integrity.get("content")
        if not isinstance(content_hash, str) or not hmac.compare_digest(_sha256(content), content_hash):
            raise ValueError("Paxalia package content integrity validation failed.")
        return manifest, content, encrypted
    finally:
        archive.close()
