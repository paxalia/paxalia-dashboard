"""WebAuthn integration for Paxalia administrator device credentials."""
from __future__ import annotations

import ipaddress
import json
import secrets
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.utils import timezone

from .models import PaxaliaDevice, PaxaliaDeviceCredential, PaxaliaWebAuthnChallenge
from .settings import get_config



def webauthn_available() -> bool:
    try:
        import webauthn  # noqa: F401
        return True
    except Exception:
        return False


def webauthn_app_configured() -> bool:
    return webauthn_available()


def _host_without_port(host: str) -> str:
    # IPv6 literals are already bracketed in HTTP Host headers. Preserve them
    # without a port where possible; WebAuthn RP IDs are domain identifiers,
    # not URLs or IP literals.
    if host.startswith("[") and "]" in host:
        return host[1:host.index("]")]
    return host.split(":", 1)[0]


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(str(host or "").strip("[]"))
        return True
    except ValueError:
        return False


def is_local_web_authn_request(request) -> bool:
    """Return True when DEBUG mode is using a loopback IP instead of localhost."""
    if not settings.DEBUG:
        return False
    host = _host_without_port(request.get_host())
    if not _is_ip_literal(host):
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def localhost_url_for_request(request) -> str:
    """Build the same request path on the WebAuthn-compatible localhost origin."""
    parsed = urlsplit(request.build_absolute_uri("/"))
    scheme = parsed.scheme or ("https" if request.is_secure() else "http")
    port = parsed.port
    netloc = "localhost" if not port else f"localhost:{port}"
    return urlunsplit((scheme, netloc, request.path, request.META.get("QUERY_STRING", ""), ""))


def configuration_for_request(request) -> tuple[str, str]:
    config = get_config()
    rp_id = str(config.get("WEBAUTHN_RP_ID") or _host_without_port(request.get_host())).strip()
    origin = str(config.get("WEBAUTHN_ORIGIN") or request.build_absolute_uri("/")).rstrip("/")
    parsed_origin = urlsplit(origin)
    scheme = parsed_origin.scheme.lower()
    if not rp_id or scheme not in {"https", "http"} or not parsed_origin.netloc:
        raise ValueError("Invalid WebAuthn relying-party configuration.")
    if parsed_origin.path not in {"", "/"} or parsed_origin.query or parsed_origin.fragment:
        raise ValueError("WEBAUTHN_ORIGIN must be an origin without a path, query string, or fragment.")
    if not settings.DEBUG and scheme != "https":
        raise ValueError("WebAuthn requires an HTTPS origin when DEBUG=False.")
    if not settings.DEBUG and not request.is_secure():
        raise ValueError("Paxalia WebAuthn requires a secure request in production.")

    origin_host = (parsed_origin.hostname or "").rstrip(".").lower()
    normalized_rp_id = rp_id.rstrip(".").lower()
    if not origin_host or not normalized_rp_id:
        raise ValueError("WebAuthn relying-party configuration requires a valid host.")

    if _is_ip_literal(origin_host):
        if settings.DEBUG and ipaddress.ip_address(origin_host).is_loopback:
            raise ValueError(
                "WebAuthn local development requires the browser origin to use "
                "http://localhost instead of a loopback IP such as 127.0.0.1."
            )
        raise ValueError("WebAuthn requires a DNS-style relying-party domain; IP addresses cannot be used as RP IDs.")

    if _is_ip_literal(normalized_rp_id):
        raise ValueError("WEBAUTHN_RP_ID must be a DNS-style domain and cannot be an IP address.")

    if "." not in origin_host and origin_host != normalized_rp_id:
        # Local development hosts such as localhost are valid single-label
        # origins. They must still match the configured relying-party ID.
        raise ValueError("WEBAUTHN_RP_ID must match the WebAuthn origin host.")
    elif "." in origin_host and not (origin_host == normalized_rp_id or origin_host.endswith("." + normalized_rp_id)):
        raise ValueError("WEBAUTHN_RP_ID must match the WebAuthn origin host or a parent domain.")
    return normalized_rp_id, origin


def _challenge_bytes() -> bytes:
    # WebAuthn libraries already expose generate_challenge(), but keeping the
    # challenge bytes here under our persistence boundary makes the one-time
    # lifecycle explicit and library-independent.
    return secrets.token_bytes(64)


def create_challenge(*, user, request, kind: str, device=None):
    import base64

    raw = _challenge_bytes()
    encoded = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    ttl = max(30, int(get_config().get("WEBAUTHN_CHALLENGE_TTL_SECONDS", 120)))
    now = timezone.now()
    # Cleanup is deliberately scoped to the current administrator so creating
    # a new ceremony cannot grow an unrelated user's challenge history.
    # The model uses expires_at/used_at; prune only terminal challenges.
    PaxaliaWebAuthnChallenge.objects.filter(user=user, expires_at__lte=now).delete()
    PaxaliaWebAuthnChallenge.objects.filter(user=user, used_at__isnull=False).delete()
    return PaxaliaWebAuthnChallenge.objects.create(
        user=user,
        device=device,
        kind=kind,
        challenge=encoded,
        session_key=getattr(getattr(request, "session", None), "session_key", "") or "",
        created_at=now,
        expires_at=now + timezone.timedelta(seconds=ttl),
    )


def challenge_bytes(challenge: PaxaliaWebAuthnChallenge) -> bytes:
    import base64

    value = challenge.challenge.encode("ascii")
    value += b"=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value)


def consume_challenge(challenge: PaxaliaWebAuthnChallenge) -> None:
    challenge.used_at = timezone.now()
    challenge.save(update_fields=["used_at"])


def _device_type(value) -> str:
    return getattr(value, "value", str(value or ""))[:32]


def _transports(credential) -> list[str]:
    try:
        transports = credential.response.transports or []
    except Exception:
        transports = []
    return [str(value)[:32] for value in transports if value]


def registration_options(request, user, *, device_name: str):
    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        ResidentKeyRequirement,
        UserVerificationRequirement,
        PublicKeyCredentialDescriptor,
    )

    rp_id, _origin = configuration_for_request(request)
    existing_user_handle = PaxaliaDeviceCredential.objects.filter(
        device__user=user
    ).values_list("webauthn_user_handle", flat=True).first()
    user_handle = bytes(existing_user_handle) if existing_user_handle else secrets.token_bytes(64)
    if not 1 <= len(user_handle) <= 64:
        raise ValueError("The stored WebAuthn user handle is invalid.")
    challenge = create_challenge(user=user, request=request, kind="registration")
    challenge.user_handle = user_handle
    challenge.save(update_fields=["user_handle"])
    existing = PaxaliaDeviceCredential.objects.filter(
        device__user=user, device__status="active"
    )
    exclusions = [
        PublicKeyCredentialDescriptor(id=_credential_id_bytes(item.credential_id))
        for item in existing
    ]
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=str(get_config().get("WEBAUTHN_RP_NAME") or "Paxalia Dashboard"),
        user_id=user_handle,
        user_name=str(user.get_username()),
        user_display_name=str(user.get_full_name() or user.get_username()),
        challenge=challenge_bytes(challenge),
        exclude_credentials=exclusions,
        # Paxalia Layer 3 is a passkey authorization factor. Passkeys are
        # discoverable credentials, so require a resident credential and require
        # user verification during creation. No authenticator-attachment hint is
        # supplied so platform, hybrid, and security-key authenticators remain
        # eligible.
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    return challenge, json.loads(options_to_json(options))


def authentication_options(request, user):
    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers.structs import PublicKeyCredentialDescriptor, UserVerificationRequirement

    rp_id, _origin = configuration_for_request(request)
    credentials = PaxaliaDeviceCredential.objects.filter(
        device__user=user, device__status="active"
    )
    if not credentials.exists():
        raise ValueError("No active Paxalia device credentials are registered for this administrator.")
    challenge = create_challenge(user=user, request=request, kind="authentication")
    allow = [
        PublicKeyCredentialDescriptor(id=_credential_id_bytes(item.credential_id))
        for item in credentials
    ]
    options = generate_authentication_options(
        rp_id=rp_id,
        challenge=challenge_bytes(challenge),
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return challenge, json.loads(options_to_json(options))


def _credential_id_bytes(value: str) -> bytes:
    import base64

    raw = str(value).encode("ascii")
    raw += b"=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw)


def _credential_id_string(value: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _user_handle_for(user) -> bytes:
    existing = PaxaliaDeviceCredential.objects.filter(device__user=user).values_list(
        "webauthn_user_handle", flat=True
    ).first()
    return bytes(existing) if existing else secrets.token_bytes(64)


def verify_registration(request, user, *, challenge, payload: dict, device_name: str):
    from webauthn import verify_registration_response

    rp_id, origin = configuration_for_request(request)
    result = verify_registration_response(
        credential=payload,
        expected_challenge=challenge_bytes(challenge),
        expected_rp_id=rp_id,
        expected_origin=origin,
        require_user_verification=True,
    )
    credential_id = _credential_id_string(result.credential_id)
    if PaxaliaDeviceCredential.objects.filter(credential_id=credential_id).exists():
        raise ValueError("That authenticator is already registered.")

    max_devices = max(1, int(get_config().get("ADMIN_MAX_DEVICES", 5)))
    active_count = PaxaliaDevice.objects.filter(user=user, status="active").count()
    if active_count >= max_devices:
        raise ValueError("The configured maximum number of active admin devices has been reached.")

    device = PaxaliaDevice.objects.create(
        user=user,
        display_name=(device_name or "Paxalia Authenticator").strip()[:120],
        status="active",
        created_at=timezone.now(),
    )
    handle = bytes(challenge.user_handle) if challenge.user_handle else _user_handle_for(user)
    credential = PaxaliaDeviceCredential.objects.create(
        device=device,
        credential_id=credential_id,
        credential_public_key=bytes(result.credential_public_key),
        sign_count=int(result.sign_count),
        webauthn_user_handle=handle,
        device_type=_device_type(result.credential_device_type),
        backed_up=bool(result.credential_backed_up),
        aaguid=str(getattr(result, "aaguid", "") or "")[:64],
        authenticator_attachment=str(payload.get("authenticatorAttachment") or "")[:32],
        transports=_transports(payload),
        created_at=timezone.now(),
    )
    return credential


def _authentication_backup_eligibility(payload: dict) -> bool:
    """Return the WebAuthn backup-eligibility (BE) bit from an assertion.

    BE is carried in the authenticator-data flags byte. Reading this bit before
    server-side verification lets the RP choose an appropriate signature-counter
    policy for multi-device credentials while the WebAuthn library still performs
    the actual cryptographic, challenge, RP-ID, origin, and user-verification checks.
    Malformed authenticator data returns False so the normal verifier remains the
    authority for rejecting malformed assertions.
    """
    try:
        from webauthn import base64url_to_bytes

        encoded = str(((payload.get("response") or {}).get("authenticatorData")) or "")
        raw = base64url_to_bytes(encoded)
        if len(raw) < 37:
            return False
        return bool(raw[32] & 0x08)
    except Exception:
        return False


def verify_authentication(request, user, *, challenge, payload: dict) -> PaxaliaDeviceCredential:
    from webauthn import base64url_to_bytes, verify_authentication_response

    credential_id = str(payload.get("rawId") or payload.get("id") or "")
    credential_id = _credential_id_string(base64url_to_bytes(credential_id))
    try:
        credential = PaxaliaDeviceCredential.objects.select_for_update().select_related("device").get(
            credential_id=credential_id,
            device__user=user,
            device__status="active",
        )
    except PaxaliaDeviceCredential.DoesNotExist as exc:
        raise ValueError("This authenticator is not authorized for the administrator.") from exc

    rp_id, origin = configuration_for_request(request)
    backup_eligible = _authentication_backup_eligibility(payload)
    current_sign_count = int(credential.sign_count)

    # Device-bound credentials retain strict monotonic counter enforcement.
    # Backup-eligible/multi-device credentials are different: synced copies may
    # report a counter that is not monotonic across authenticators, so feeding a
    # previously observed non-zero counter into py_webauthn would reject an
    # otherwise valid cryptographic assertion before the library can verify it.
    verification_sign_count = 0 if backup_eligible else current_sign_count

    result = verify_authentication_response(
        credential=payload,
        expected_challenge=challenge_bytes(challenge),
        expected_rp_id=rp_id,
        expected_origin=origin,
        credential_public_key=bytes(credential.credential_public_key),
        credential_current_sign_count=verification_sign_count,
        require_user_verification=True,
    )

    # For single-device credentials, a backwards counter remains a hard failure.
    # For backup-eligible credentials the counter is advisory, not the source of
    # authentication truth; the assertion has already passed signature/challenge
    # /origin/user-verification checks above. Keep the highest observed value for
    # diagnostics without making a synced-copy rollback unusable.
    if not backup_eligible and int(result.new_sign_count) < current_sign_count:
        raise ValueError("The authenticator counter moved backwards.")

    now = timezone.now()
    credential.sign_count = max(int(result.new_sign_count), current_sign_count)
    credential.backed_up = bool(result.credential_backed_up)
    credential.device_type = _device_type(result.credential_device_type)
    credential.last_authenticated_at = now
    credential.save(update_fields=["sign_count", "backed_up", "device_type", "last_authenticated_at"])
    credential.device.last_authenticated_at = now
    credential.device.save(update_fields=["last_authenticated_at"])
    return credential
