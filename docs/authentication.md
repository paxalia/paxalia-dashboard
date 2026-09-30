---

# Paxalia Auth & Administrator Security

Paxalia Dashboard includes a standalone, override-friendly authentication experience for host Django projects. The
main Paxalia application is not required; its authentication pages were used only as the UX/design reference for the
Paxalia-branded presentation.

### Public authentication surfaces

The package can provide:

- Login
- Sign Up
- Password reset request
- Password reset confirmation
- Password change
- Session-expired state
- Access-denied state

These surfaces use Django's authentication, password validators, session framework, messages, CSRF protection, and
configured user model rather than creating a second user/password database. Host projects can override the templates or
route users to their existing authentication views.

### Mandatory administrator authentication

The privileged Paxalia Dashboard flow is separate from ordinary public-site authentication. A public user can use the
host application's normal login/signup flow; a dashboard administrator must complete all three security layers before a
privileged Paxalia session is created.

```text
Anonymous
  ↓
Paxalia Admin Login
  ↓
Layer 1: Django username/email + password
  ↓
Layer 2: confirmed TOTP / one-time recovery code
  ↓
Layer 3: authorized WebAuthn credential
  ↓
final Django/Paxalia administrator session
```

Intermediate authentication states are intentionally non-privileged. Reaching the password or 2FA step alone does not
make the user an administrator for dashboard views, package operations, security settings, or protected APIs.

### The seven security layers

Paxalia's final administrator protection model is intentionally described as seven layers because authentication
credentials
and deployment hardening solve different problems:

#### 1. Password

The first layer uses the host project's configured Django user model. In isolated mode, Paxalia's default credential
boundary deliberately uses Django's `ModelBackend` unless the host explicitly supplies another backend through
`AUTH_ISOLATED_AUTHENTICATION_BACKENDS`.

The package does not create a parallel user/password database. Password validation remains Django's responsibility.

#### 2. Mandatory 2FA

Every Paxalia administrator must have a confirmed TOTP device before normal privileged administration is permitted.
Recovery codes provide a controlled recovery path without creating a password-only bypass.

#### 3. Authorized device

Layer 3 uses WebAuthn. The server stores the public credential and safe authenticator metadata; the private credential
remains with the authenticator.

Each ceremony uses a server-generated, short-lived, single-use challenge. Replay, expiry, wrong-user, and revoked-device
cases are rejected.

A Paxalia Authorized Device Credential is not a guaranteed permanent hardware UUID. It represents an authorized
credential
that an administrator can register, name, review, and revoke.

#### 4. Rate limiting

Authentication ceremonies are independently bounded:

```text
Login
  8 attempts / 15 minutes

2FA
  5 attempts / 5 minutes

Device / WebAuthn
  5 attempts / 5 minutes
```

The package also surfaces broader failed-login thresholds through Security Center and keeps browser event ingestion
bounded
through the logging subsystem.

#### 5. CSRF

State-changing browser operations remain behind Django CSRF protection. The authentication JavaScript includes the CSRF
token in JSON POST requests used by the WebAuthn ceremony.

The secure deployment rule is simple:

```text
CsrfViewMiddleware stays enabled.
Authentication views stay CSRF protected.
Do not solve integration problems by disabling CSRF.
```

#### 6. Separate authentication boundaries

In the default isolated mode, the public website and Paxalia administrator authentication do not share the same session
state.

The host website keeps its normal Django session while the dashboard uses:

```text
paxalia_admin_session
        ↓
dedicated Django SessionStore
        ↓
dashboard-path cookie scope
```

This means:

```text
host login      ≠      Paxalia admin login
host logout     ≠      Paxalia admin logout
host session    ≠      Paxalia admin session
host rotation   ≠      Paxalia admin rotation
```

The package still uses the configured Django session engine/backend, so isolation does not require a second identity
database.

#### 7. Secret dashboard path

The full administrator surface is mounted below a deployment-specific private path. Production configuration requires a
32–128 character URL-safe random segment and rejects common predictable administrator paths.

The path is defense in depth. It is deliberately not treated as an authentication mechanism.

### Authentication lifecycle

The normal administrator lifecycle is:

```text
GET private dashboard
        ↓
/auth/login/
        ↓
password accepted
        ↓
/auth/2fa/
        ↓
TOTP or one-time recovery code accepted
        ↓
/auth/device/
        ↓
WebAuthn credential accepted
        ↓
final Paxalia administrator session
        ↓
dashboard / Admin / Security / Packages
```

Logout returns to the Paxalia login surface and removes the dedicated administrator session. The host website session is
left intact in isolated mode.

### Layer 1 — primary authentication

Paxalia uses the host project's configured Django authentication backend and existing user model wherever possible.
Login
attempts are rate-limited by source and identifier, and important authentication events are sent through the existing
Paxalia structured logging/security infrastructure. Unknown-account failures use safe generic messages and can be
tracked
through the existing failed-login observability.

### Layer 2 — mandatory TOTP

Every administrator must have a confirmed TOTP device before normal Paxalia Dashboard administration is permitted. The
package uses `django-otp` for the TOTP implementation and provides a Paxalia-branded enrollment and verification flow.

The enrollment flow is: complete primary authentication, enroll the authenticator, verify a current code, generate
recovery codes, and continue to the authorized-device step. There is no normal "skip for now" path.

Recovery codes are generated with cryptographically secure randomness, stored as password hashes, individually consumed
when used, revocable/regenerable, and never written to Paxalia logs.

### Layer 3 — authorized device credential

Browser-based Layer 3 uses the maintained Python `webauthn` library and the WebAuthn browser API. Paxalia stores the
public credential and safe authenticator metadata; the private credential remains with the authenticator. Each ceremony
uses a server-generated, short-lived, single-use challenge. Replay, expiry, wrong-user, and revoked-credential cases
fail.

The credential is a **Paxalia Authorized Device Credential**, not a guaranteed permanent hardware UUID. An administrator
can register multiple credentials up to the configured active-device limit, name them, review safe metadata, and revoke
them individually.

### Device management

**Security → Admin Devices** provides:

- device name
- active/revoked/disabled state
- registration time
- last authentication time
- authenticator/device type where available
- attachment information where available
- backup state where safely available
- rename operation
- individual revocation

Private keys, raw credential secrets, challenges, recovery codes, and other sensitive cryptographic material are never
displayed as normal device data. Revocation is audited and invalidates future credential authentication; associated
privileged sessions are also invalidated according to the configured session architecture.

### Administrator sessions

**Security → Admin Sessions** shows privileged sessions recorded by the existing login-event infrastructure. Sessions
can
be revoked individually, all other sessions can be revoked, or all administrator sessions can be revoked. The privileged
session remains valid only while the administrator is active, the confirmed second factor still exists, the authorized
device credential remains active, the session has not expired, and the session has not been revoked.

### WebAuthn deployment requirements

WebAuthn must use the actual deployed relying-party ID and browser origin. In production, the browser context must be
HTTPS. `WEBAUTHN_RP_ID` and `WEBAUTHN_ORIGIN` can be explicitly configured for proxy/hosted deployments; otherwise the
package derives them from the current request when safe. The dashboard does not silently fall back to password-only
access if a secure WebAuthn ceremony cannot run.

### Authentication events

The authentication and device flow uses the existing structured logging/audit architecture. Examples include:

```text
admin_login_started
admin_login_failed
admin_login_rate_limited
admin_2fa_required
admin_2fa_success
admin_2fa_failed
admin_recovery_used
admin_device_challenge_failed
admin_device_authenticated
admin_device_rejected
admin_device_registered
admin_device_revoked
admin_device_renamed
admin_session_created
admin_all_sessions_revoked
admin_logout
```

Exact presentation can vary by logging surface, but these events remain within the existing Paxalia observability and
Security Center architecture rather than creating a parallel security-event store. Authentication secrets, TOTP codes,
recovery codes, private keys, and raw WebAuthn assertions are not logged.

### Security configuration

The current settings expose policy details such as active-device limits, privileged-session lifetime, authentication and
2FA/device rate limits, challenge lifetime, WebAuthn relying-party configuration, recovery-code count, and
authentication
page branding. These settings configure implementation details; they do not disable the mandatory administrator security
layers.

---
