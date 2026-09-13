# paxalia/security_scorecard.py
"""
Security Scorecard — a pass/fail/warn checklist for the Security Center.

This is deliberately NOT a live scan of the filesystem or network: every
check here reads configuration that's already loaded in-process (Django
`settings`, this package's own config, or a handful of existing model
rows) and evaluates it against a known-good baseline. That keeps it fast
enough to run on every Security Center page load and means there's
nothing new to schedule or grant filesystem access to.

Each check returns a dict:
    {
        'key':    str   — stable identifier, safe to use in HTML/CSS
        'label':  str   — short human name
        'status': 'pass' | 'warn' | 'fail'
        'detail': str   — one sentence explaining the result
    }

Add a new check by writing a `_check_*()` function returning one of
these dicts and appending it to the relevant group in
`run_scorecard_checks()`.
"""
from django.conf import settings

from .conf_uploads import get_upload_blocked_extensions, is_releases_enabled

# A SECRET_KEY containing any of these substrings is almost certainly a
# copy-pasted tutorial/starter-project placeholder rather than a real
# generated key. Not exhaustive — just enough to catch the common case.
_INSECURE_SECRET_KEY_MARKERS = (
    'django-insecure-',
    'change-me',
    'changeme',
    'CHANGE_THIS',
    'your-secret-key',
    'secret-key-here',
)

# Server-executable / script extensions that are essentially never a
# legitimate release artifact and are dangerous if a misconfigured
# deployment ever serves the uploads directory directly. Enforced
# regardless of UPLOAD_ALLOWED_EXTENSIONS — see conf_uploads.py.
_KNOWN_DANGEROUS_EXTENSIONS = {
    '.php', '.phtml', '.phar', '.py', '.pyc', '.pyw', '.rb', '.pl',
    '.cgi', '.jsp', '.jspx', '.asp', '.aspx', '.sh', '.bash',
    '.htaccess', '.htpasswd',
}


def _check(key, label, status, detail):
    return {'key': key, 'label': label, 'status': status, 'detail': detail}


def _check_debug():
    if settings.DEBUG:
        return _check('debug', 'DEBUG disabled', 'fail',
                       'DEBUG is True — never run a public deployment this way (leaks settings, source, and SQL on error pages).')
    return _check('debug', 'DEBUG disabled', 'pass', 'DEBUG is False.')


def _check_https_redirect():
    if getattr(settings, 'SECURE_SSL_REDIRECT', False):
        return _check('https_redirect', 'HTTPS enforced', 'pass',
                       'SECURE_SSL_REDIRECT is True.')
    return _check('https_redirect', 'HTTPS enforced', 'warn',
                  'SECURE_SSL_REDIRECT is not enabled — set it (or enforce HTTPS at your proxy/load balancer) so plaintext requests are rejected.')


def _check_session_cookie():
    secure = getattr(settings, 'SESSION_COOKIE_SECURE', False)
    httponly = getattr(settings, 'SESSION_COOKIE_HTTPONLY', True)
    if secure and httponly:
        return _check('session_cookie', 'Session cookie flags', 'pass',
                       'SESSION_COOKIE_SECURE and SESSION_COOKIE_HTTPONLY are both set.')
    missing = []
    if not secure:
        missing.append('SESSION_COOKIE_SECURE')
    if not httponly:
        missing.append('SESSION_COOKIE_HTTPONLY')
    return _check('session_cookie', 'Session cookie flags', 'fail' if not secure else 'warn',
                  f'{", ".join(missing)} not enabled — the session cookie can be sent over plaintext HTTP or read by JavaScript.')


def _check_csrf_cookie():
    if getattr(settings, 'CSRF_COOKIE_SECURE', False):
        return _check('csrf_cookie', 'CSRF cookie secure', 'pass', 'CSRF_COOKIE_SECURE is True.')
    return _check('csrf_cookie', 'CSRF cookie secure', 'warn',
                  'CSRF_COOKIE_SECURE is not enabled — the CSRF cookie can be sent over plaintext HTTP.')


def _check_secret_key():
    key = getattr(settings, 'SECRET_KEY', '') or ''
    if not key:
        return _check('secret_key', 'SECRET_KEY strength', 'fail', 'SECRET_KEY is empty.')
    lowered = key.lower()
    if any(marker.lower() in lowered for marker in _INSECURE_SECRET_KEY_MARKERS):
        return _check('secret_key', 'SECRET_KEY strength', 'fail',
                       'SECRET_KEY looks like a placeholder from a tutorial or starter project — generate a real one and rotate it.')
    if len(key) < 40:
        return _check('secret_key', 'SECRET_KEY strength', 'warn',
                       f'SECRET_KEY is only {len(key)} characters — Django generates 50 by default; a short key is easier to brute-force.')
    return _check('secret_key', 'SECRET_KEY strength', 'pass', 'SECRET_KEY is set and long enough that it is not an obvious placeholder.')


def _check_allowed_hosts():
    hosts = getattr(settings, 'ALLOWED_HOSTS', []) or []
    if '*' in hosts:
        return _check('allowed_hosts', 'ALLOWED_HOSTS not wildcarded', 'fail',
                       "ALLOWED_HOSTS contains '*' — Host-header attacks (cache poisoning, password-reset link poisoning) become possible.")
    if not hosts and not settings.DEBUG:
        return _check('allowed_hosts', 'ALLOWED_HOSTS not wildcarded', 'fail',
                       'ALLOWED_HOSTS is empty with DEBUG off — every request will 400.')
    return _check('allowed_hosts', 'ALLOWED_HOSTS not wildcarded', 'pass',
                  f'{len(hosts)} host(s) explicitly allowed, no wildcard.')


def _check_csp_enforced():
    middleware = getattr(settings, 'MIDDLEWARE', []) or []
    enforced = any('csp' in m.lower() and 'middleware' in m.lower() for m in middleware)
    if enforced:
        return _check('csp_enforced', 'CSP header enforced', 'pass',
                       'A CSP-enforcing middleware is installed — violation reports land on the CSP Violations tab above.')
    return _check('csp_enforced', 'CSP header enforced', 'warn',
                  "This package's CSP violation reporting endpoint is live, but no CSP-enforcing middleware (e.g. django-csp) is in MIDDLEWARE — the browser isn't actually being told to block anything yet. See the README's CSP setup section.")


def _check_backup_encryption():
    from .models import BackupConfiguration
    config = BackupConfiguration.objects.first()
    if not config or not config.enabled:
        return _check('backup_encryption', 'Backups encrypted at rest', 'warn',
                       'Backups are not configured/enabled, so this cannot be evaluated yet.')
    return _check('backup_encryption', 'Backups encrypted at rest', 'warn',
                  'Backup archives are plain tar.gz — this package does not encrypt them. '
                  'Encrypt the storage_path volume, or wrap the archive with your own GPG/age step, if it may hold sensitive data.')


def _check_backup_path_isolation():
    from .models import BackupConfiguration
    config = BackupConfiguration.objects.first()
    if not config or not config.storage_path or not config.get_backup_paths_list():
        return _check('backup_path_isolation', 'Backup storage isolated from backup paths', 'warn',
                       'Backups are not fully configured yet, so this cannot be evaluated.')
    warning = config.get_path_overlap_warning()
    if warning:
        return _check('backup_path_isolation', 'Backup storage isolated from backup paths', 'fail', warning)
    return _check('backup_path_isolation', 'Backup storage isolated from backup paths', 'pass',
                  'storage_path does not overlap any configured backup path.')


def _check_backup_download_reauth():
    # This is a static statement of what the code does (see
    # views/backup.py::_require_recent_reauth), not a runtime check —
    # there's no per-request state to inspect from here.
    return _check('backup_reauth', 'Backup download requires re-authentication', 'pass',
                  'Downloading a backup archive requires re-entering your password within the last '
                  f"{getattr(settings, 'PAXALIA_DASHBOARD', {}).get('BACKUP_REAUTH_MINUTES', 15)} minutes.")


def _check_upload_extension_validation():
    if not is_releases_enabled():
        return _check('upload_validation', 'Upload file-type validation', 'pass',
                       'Releases/uploads section is not enabled.')
    blocked = get_upload_blocked_extensions()
    if not blocked:
        return _check('upload_validation', 'Upload file-type validation', 'warn',
                       'UPLOAD_BLOCKED_EXTENSIONS has been cleared to empty — any file extension can be uploaded.')
    return _check('upload_validation', 'Upload file-type validation', 'pass',
                  f'{len(blocked)} known-dangerous extension(s) are blocked on upload; configure UPLOAD_ALLOWED_EXTENSIONS for a stricter allowlist.')


def _middleware_has(suffix):
    return any(m.rsplit('.', 1)[-1] == suffix for m in (getattr(settings, 'MIDDLEWARE', []) or []))


def _check_hsts():
    max_age = int(getattr(settings, 'SECURE_HSTS_SECONDS', 0) or 0)
    if max_age >= 31536000:
        return _check('hsts', 'HSTS policy', 'pass', f'SECURE_HSTS_SECONDS is {max_age}.')
    if max_age > 0:
        return _check('hsts', 'HSTS policy', 'warn', f'HSTS is enabled for only {max_age} seconds; production sites normally use a long-lived policy.')
    return _check('hsts', 'HSTS policy', 'warn', 'No Django HSTS policy is configured; enforce HSTS at the trusted proxy/load balancer if that is where TLS terminates.')


def _check_frame_options():
    value = getattr(settings, 'X_FRAME_OPTIONS', 'DENY')
    if value == 'DENY':
        return _check('frame_options', 'Clickjacking protection', 'pass', 'X_FRAME_OPTIONS is DENY.')
    return _check('frame_options', 'Clickjacking protection', 'warn', f'X_FRAME_OPTIONS is {value!r}; review whether framing is required.')


def _check_cors():
    allow_all = bool(getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False))
    if allow_all:
        return _check('cors', 'CORS origins restricted', 'fail', 'CORS_ALLOW_ALL_ORIGINS is True.')
    return _check('cors', 'CORS origins restricted', 'pass', 'CORS is not globally open.')


def _check_security_block_middleware():
    if _middleware_has('SecurityBlockMiddleware'):
        return _check('blocked_ip_enforcement', 'IP block enforcement', 'pass', 'SecurityBlockMiddleware is active.')
    return _check('blocked_ip_enforcement', 'IP block enforcement', 'warn', 'BlockedIP entries are stored but SecurityBlockMiddleware is not active; the blocklist will not reject requests until enforcement is enabled.')


def _check_slow_query_middleware():
    if _middleware_has('SlowQueryMiddleware'):
        return _check('slow_query_capture', 'Slow-query capture', 'pass', 'SlowQueryMiddleware is active.')
    return _check('slow_query_capture', 'Slow-query capture', 'warn', 'Slow-query records are not being captured because SlowQueryMiddleware is not active.')


def run_scorecard_checks():
    """Return {'django': [...], 'package': [...], 'summary': {...}}."""
    django_checks = [
        _check_debug(),
        _check_https_redirect(),
        _check_session_cookie(),
        _check_csrf_cookie(),
        _check_secret_key(),
        _check_allowed_hosts(),
        _check_csp_enforced(),
        _check_hsts(),
        _check_frame_options(),
        _check_cors(),
        _check_security_block_middleware(),
        _check_slow_query_middleware(),
    ]
    package_checks = [
        _check_backup_encryption(),
        _check_backup_path_isolation(),
        _check_backup_download_reauth(),
        _check_upload_extension_validation(),
    ]

    all_checks = django_checks + package_checks
    summary = {
        'pass': sum(1 for c in all_checks if c['status'] == 'pass'),
        'warn': sum(1 for c in all_checks if c['status'] == 'warn'),
        'fail': sum(1 for c in all_checks if c['status'] == 'fail'),
        'total': len(all_checks),
    }
    return {'django': django_checks, 'package': package_checks, 'summary': summary}
