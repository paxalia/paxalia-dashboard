---

# Security Center

Security Center brings application-facing security visibility into the same operational environment as analytics.

### Login activity

The security layer can surface:

- successful logins
- failed login patterns
- staff/privileged activity
- login locations where available
- authentication context
- related security events

### Active sessions

Where the host authentication/session model provides the required data, administrators can inspect active sessions and
revoke them through the appropriate workflow.

### IP blocklist

Security Center can maintain blocked IPs.

When `SecurityBlockMiddleware` is enabled, requests from blocked addresses can be denied before analytics recording.

### Brute-force alerting

Configure:

```python
PAXALIA_DASHBOARD = {
    "SECURITY_FAILED_LOGIN_THRESHOLD": 5,
    "SECURITY_FAILED_LOGIN_WINDOW_MINUTES": 15,
}
```

Crossing the configured threshold can generate a security alert.

### CSP violation reporting

Browser CSP violations can be fed into the Security Center so policy failures can be investigated alongside application
observability.

### Security scorecard

The Security Scorecard presents configuration/posture findings from the package's supported security checks.

It is a visibility tool, not a replacement for an external security assessment.

The Security Overview is separate from this legacy scorecard surface: it uses explicit control states and actionable
configuration details rather than reducing the administrator's security posture to one number.

### Administrator authentication

Paxalia Dashboard administration is protected by a mandatory three-layer authentication contract:

```text
Layer 1 — Host Django authentication
    password / configured backend
    rate limiting / brute-force protection
            ↓
Layer 2 — Mandatory 2FA
    Paxalia TOTP authenticator / recovery path
            ↓
Layer 3 — Authorized device credential
    WebAuthn challenge + signature verification
            ↓
Paxalia Dashboard Admin
```

The layers are enforced server-side. There is no ordinary dashboard setting that turns the three-layer administrator
security model off. IP address, user-agent data, and browser fingerprints are context only; they are not treated as the
identity of an authorized administrator device.

### Defense-in-depth administrator controls

The mandatory administrator security contract is broader than the three credential layers:

```text
1. Password
   └─ Django authentication + password validation

2. 2FA
   └─ django-otp TOTP or one-time recovery code

3. Device
   └─ WebAuthn challenge + credential signature verification

4. Rate limiting
   └─ login + 2FA + device ceremony limits

5. CSRF
   └─ Django CSRF middleware + CSRF-aware bundled JSON helper

6. Separate authentication
   └─ dedicated Paxalia SessionStore + scoped cookie

7. Secret path
   └─ deployment-specific private dashboard mount
```

Additional hardening surrounds the chain:

```text
SecurityBlockMiddleware
        +
CSP / SecurityMiddleware
        +
honeypot integration
        +
sensitive-field redaction
        +
no-store protected responses
        +
package encryption/integrity
        +
bounded upload and log ingestion
        +
security/audit events
```

The dashboard's security tooling is therefore designed as a system rather than a single score.

### Security Overview

**Security Overview** is a read-only diagnostic surface that reports the effective state of supported controls instead
of
turning security into a single opaque score. Checks can be reported as `PASS`, `WARNING`, `DANGER`, `DISABLED`,
`NOT CONFIGURED`, or `NOT APPLICABLE`, with the current state, expected state, reason, configuration source, and a
relevant
action/page where one exists.

The checks cover the configured authentication and session stack, mandatory 2FA and enrollment, WebAuthn availability,
HTTPS and cookie posture, CSRF and SecurityMiddleware, authentication/device rate limits, brute-force monitoring,
`ALLOWED_HOSTS`, `DEBUG`, `SECRET_KEY`, CSP, persistent Paxalia logging and retention, protected package encryption,
sensitive-field protection, admin-gate health, active administrator devices, and challenge/session policy.

### Backup re-authentication

Sensitive backup downloads can require a recent password-authentication timestamp.

---


---

## Paxalia Error Pages

The package ships production-oriented Paxalia 404 and 500 templates that can be used by a generic Django project. Their
visual language is adapted from the broader Paxalia product reference while using Paxalia Dashboard's own theme tokens,
typography, spacing, surfaces, and responsive shell.

### 404

The 404 page is a branded, responsive error surface with a lightweight glitch/CRT treatment, a safe return-home action,
and a browser-history action. Dynamic request information is not reflected into the page without escaping.

### 500

The 500 page is intentionally production-safe. It does not expose exception details, tracebacks, SQL, filesystem paths,
request headers, environment variables, or secrets. The technical event belongs in Paxalia Logs, where authorized
administrators can investigate the correlated application/request event.

### Error-page overrides

Host projects can override `templates/404.html` and `templates/500.html` using Django's normal template-loader
precedence without editing the installed Paxalia package. Branding/home/support settings can be configured through the
existing `PAXALIA_DASHBOARD` namespace.

### Root URL configuration

Because Django resolves `handler404` and `handler500` from the project's root URLconf, wire the packaged handlers there:

```python
handler404 = "paxalia.error_handlers.paxalia_404"
handler500 = "paxalia.error_handlers.paxalia_500"
```

This keeps the error implementation inside Paxalia while leaving root routing and template overrides under the host
project's control.

### DEBUG behavior

With production `DEBUG=False`, the packaged 500 page remains safe and user-facing. With `DEBUG=True`, Django's
development
exception machinery can still provide its normal development diagnostics to the developer; Paxalia does not treat DEBUG
as
a mechanism for bypassing administrator authentication.

---


---

## Security & Privacy Model

Paxalia is designed to keep data on the host application.

That does not mean "privacy automatically solved."

The host project still controls:

- database access
- operating system security
- reverse proxy
- authentication
- administrator accounts
- backups
- network policy
- retention choices
- proxy trust
- email/webhook destinations
- access to exported files

### Application-level security principles

Paxalia uses:

- Django authentication
- staff checks
- Django permissions
- object-level ModelAdmin permission hooks where available
- CSRF protection
- sensitive-field redaction
- no-store handling for protected responses where configured
- package structural validation
- package integrity checks
- package encryption requirements
- ZIP archive safety controls
- bounded upload/package limits
- audit/security events

### Secret dashboard paths

The dashboard can be mounted at a private path.

This is useful as a defense-in-depth measure.

It must not be treated as an authentication mechanism by itself.

For the v4.1.0 deployment model, the private path is configured through `DASHBOARD_URL` and, in production, is
validated as a 32–128 character URL-safe random segment.

All privileged dashboard routes and the Paxalia administrator authentication lifecycle can live beneath that same
private
mount:

```text
<secret-path>/
├── auth/
├── security/
├── admin/
├── logs/
├── packages/
└── dashboard/
```

The browser-facing public application can keep normal authentication and public ingestion routes outside this mount.

### Public ingestion endpoints

Browser event ingestion is intentionally public because visitors send anonymous telemetry to it.

Public ingestion endpoints must therefore validate and bound input on the server.

### Proxy trust

Only enable forwarded-IP trust behind a controlled proxy infrastructure.

### Logging privacy

Persistent observability makes debugging easier, but it also creates another sensitive data store.

The logging system therefore:

- redacts credential-like fields
- bounds message and stack sizes
- bounds metadata
- bounds browser event rates
- supports retention policies
- distinguishes diagnostic context from secrets
- supports privacy-aware failed-login identifier handling

### Admin privacy

Paxalia Admin is designed to avoid displaying configured sensitive fields as normal values.

Protected values should not be exposed simply because an administrator can browse the model.

### Package privacy

Normal exports omit configured sensitive fields.

Protected-model export can require encryption.

Package failure reports must not expose secret material.

### Backups

Physical backups contain whatever the configured backup scope includes.

Treat them as highly sensitive infrastructure artifacts and protect their storage and transport accordingly.

### What Paxalia does not do

Paxalia does not:

- replace your OS firewall
- rotate all application credentials for you
- verify crawler identity through a live IP-range lookup
- replace a dedicated WAF
- replace a dedicated SIEM
- automatically upgrade dependencies
- provision your Redis/Celery/PostgreSQL infrastructure
- operate your mail server
- replace a physical disaster-recovery strategy
- certify legal compliance

### Production principle

Use Paxalia as an **application-level observability, analytics, administration, and security layer** alongside your
normal infrastructure controls.

---


---

## Final v4.1.0 Security Checklist

Before exposing Paxalia Dashboard to real users, verify the deployment as one complete boundary:

```text
[ ] Password authentication is active
[ ] Administrator accounts are recognized by the configured admin policy
[ ] TOTP enrollment is confirmed
[ ] Recovery codes are generated and stored safely
[ ] At least one authorized WebAuthn device is registered
[ ] Device revocation is tested
[ ] Login / 2FA / device rate limits are configured
[ ] Django CSRF middleware is enabled
[ ] Paxalia administrator session isolation is enabled
[ ] The isolated administrator cookie is scoped to the private dashboard path
[ ] Production DASHBOARD_URL is a long random segment
[ ] WebAuthn RP ID and origin match the deployed HTTPS origin
[ ] ALLOWED_HOSTS is configured correctly
[ ] DEBUG=False in production
[ ] SECRET_KEY is configured securely
[ ] CSP/SecurityMiddleware remain enabled
[ ] Sensitive fields are protected in Admin
[ ] Security Overview reports the expected posture
[ ] Backup downloads use the configured re-authentication policy
[ ] Authentication and security events are visible in Paxalia observability
```

A secret path, a password, 2FA, or WebAuthn by itself is not the complete security model. The package is designed so
these
controls reinforce one another.

---


---

## Future Security Setup & Bootstrap Tooling

> **Planned / not implemented in the current release.**
>
> This section documents a future contribution direction only. None of the commands below are available from the
> current package. Do not copy them into deployment automation expecting them to exist today.

The long-term goal is to provide an interactive Paxalia project-setup layer that can diagnose a Django project, preview
proposed security/configuration changes, create backups, and then apply only changes that the administrator explicitly
approves.

### Future `paxalia_check`

A future command may provide a single read-only project health entry point:

```bash
python manage.py paxalia_check
```

The intended scope includes Django deployment checks, Paxalia security checks, authentication checks, configuration
checks, logging checks, and Admin checks.

### Future `paxalia_setup`

A future interactive setup command may inspect the host project and show a preview before making changes:

```bash
python manage.py paxalia_setup
```

The future workflow could inspect the project, preview proposed changes, create backups, configure Paxalia, configure
security, configure logging, and configure authentication while preserving existing project behavior.

### Future security setup

A future security-focused mode could be exposed as:

```bash
python manage.py paxalia_setup security
python manage.py paxalia_setup security --apply
```

A future implementation should first inspect the project safely and present a deterministic preview. Depending on the
project, it could eventually:

- detect existing security/authentication packages
- propose only compatible dependencies
- back up files before mutation
- update `.env` safely where the project uses environment-based settings
- update `.env.example` and `.gitignore` when appropriate
- configure security middleware
- configure Paxalia logging
- configure administrator authentication and security
- run Django/Paxalia validation after applying changes

The future tooling must preserve existing settings instead of blindly rewriting arbitrary `settings.py` files.

### Future production security setup

A future production-oriented mode could be exposed as:

```bash
python manage.py paxalia_setup security --production --apply
```

This would still need to preview its intended changes, create backups, detect conflicts, and stop rather than silently
overwrite project-specific configuration. Production mode should maximize safe automation, not remove administrator
control.

### Explicitly outside the current release

The current package does **not** automatically:

- migrate `settings.py` secrets into `.env`
- rewrite `.env` files
- modify `requirements.txt`, `pyproject.toml`, Poetry configuration, or other dependency manifests
- rewrite arbitrary Django settings files
- bootstrap a deployment automatically
- provide the future `paxalia_check` command
- provide the future `paxalia_setup` command

For the current release, Security Overview is intentionally diagnostic and read-only: it tells administrators what is
active, what is missing, and what requires attention. Future setup tooling can build on those diagnostics later without
changing the completed security architecture.

---

> **Created with love by the Paxalia team for the world — because detail matters.**
>
> Detail is in the layers you may not notice first: thoughtful security boundaries, password + 2FA + authorized-device
> authentication, rate limits, CSRF protection, isolated administrator sessions, a private dashboard path, twelve
> token-driven themes, a clean Django-native structure, careful data portability, persistent observability, and the
> small
> decisions that make the whole system feel considered.
>
> **Paxalia Dashboard is built around the belief that the details are part of the product.**
