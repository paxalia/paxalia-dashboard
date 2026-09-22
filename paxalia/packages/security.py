"""Optional authenticated encryption for Paxalia packages.

The package format never silently downgrades a requested encrypted operation.
Cryptography is intentionally an optional dependency at runtime; callers get a
clear PackageSecurityError when it is unavailable.
"""

import base64
import json
import os


class PackageSecurityError(ValueError):
    """Raised when encrypted package operations cannot be completed safely."""


KDF_ITERATIONS = 390_000
ALGORITHM = "AES-256-GCM"
KDF = "PBKDF2-HMAC-SHA256"
ENVELOPE_VERSION = 1


def _crypto():
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except Exception as exc:  # pragma: no cover - depends on environment
        raise PackageSecurityError(
            "Encrypted Paxalia packages require the 'cryptography' package. "
            "Install paxalia-dashboard with its package encryption dependency."
        ) from exc
    return hashes, AESGCM, PBKDF2HMAC


def encrypt(data: bytes, password: str) -> bytes:
    if not password:
        raise PackageSecurityError("An encryption password is required.")
    hashes, AESGCM, PBKDF2HMAC = _crypto()
    salt = os.urandom(16)
    nonce = os.urandom(12)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    key = kdf.derive(password.encode("utf-8"))
    ciphertext = AESGCM(key).encrypt(nonce, data, None)
    envelope = {
        "version": ENVELOPE_VERSION,
        "algorithm": ALGORITHM,
        "kdf": KDF,
        "iterations": KDF_ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def decrypt(envelope_bytes: bytes, password: str) -> bytes:
    if not password:
        raise PackageSecurityError("An encryption password is required.")
    hashes, AESGCM, PBKDF2HMAC = _crypto()
    try:
        envelope = json.loads(envelope_bytes.decode("utf-8"))
        if envelope.get("version") != ENVELOPE_VERSION:
            raise PackageSecurityError("Unsupported encryption envelope version.")
        if envelope.get("algorithm") != ALGORITHM or envelope.get("kdf") != KDF:
            raise PackageSecurityError("Unsupported package encryption parameters.")
        iterations = int(envelope.get("iterations") or 0)
        if iterations != KDF_ITERATIONS:
            raise PackageSecurityError("Unsupported package KDF parameters.")
        salt = base64.b64decode(envelope["salt"], validate=True)
        nonce = base64.b64decode(envelope["nonce"], validate=True)
        ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
        if len(salt) != 16 or len(nonce) != 12 or len(ciphertext) < 16:
            raise PackageSecurityError("Malformed encrypted package payload.")
    except PackageSecurityError:
        raise
    except Exception as exc:
        raise PackageSecurityError("Malformed encrypted package envelope.") from exc

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    try:
        key = kdf.derive(password.encode("utf-8"))
        return AESGCM(key).decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise PackageSecurityError("Package decryption failed. Check the password and package integrity.") from exc
