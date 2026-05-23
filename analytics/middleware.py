import hashlib
import logging
import uuid
import geoip2.database
import os
from .models import PageView, AnalyticsSettings
from .settings import get_config

logger = logging.getLogger('analytics')

# Load the GeoIP reader once (module-level, cached)
_geoip_reader = None


def _get_geoip_reader():
    global _geoip_reader
    if _geoip_reader is None:
        config = get_config()
        if config['GEOIP_PATH']:
            db_path = config['GEOIP_PATH']
        else:
            db_path = os.path.join(os.path.dirname(__file__), 'geoip', 'GeoLite2-City.mmdb')
        try:
            _geoip_reader = geoip2.database.Reader(db_path)
        except Exception:
            _geoip_reader = False
    return _geoip_reader if _geoip_reader else None


def _resolve_ip(ip):
    """Return (country_code, country_name, city) or (None, None, None)."""
    reader = _get_geoip_reader()
    if not reader:
        return None, None, None
    try:
        response = reader.city(ip)
        return (
            response.country.iso_code,
            response.country.name,
            response.city.name
        )
    except Exception:
        return None, None, None


def get_analytics_settings():
    instance = AnalyticsSettings.objects.first()
    if instance:
        return instance

    config = get_config()
    class DefaultSettings:
        anonymize_ip = config['DEFAULT_ANONYMIZE_IP']
        ignored_prefixes = '\n'.join(config['DEFAULT_IGNORED_PREFIXES'])
        ignored_extensions = '\n'.join(config['DEFAULT_IGNORED_EXTENSIONS'])
        realtime_refresh_seconds = config['DEFAULT_REALTIME_REFRESH']
    return DefaultSettings()


class AnalyticsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # ── Session cookie handling ──
        session_id = request.COOKIES.get('_analytics_sid')
        new_cookie = False
        if not session_id:
            session_id = uuid.uuid4().hex
            new_cookie = True
        # Store it on the request for potential reuse (e.g., future middleware)
        request.analytics_session_id = session_id

        response = self.get_response(request)

        path = request.path_info
        cfg = get_analytics_settings()

        ignore_prefixes = [p.strip() for p in cfg.ignored_prefixes.split('\n') if p.strip()]
        ignore_extensions = [e.strip() for e in cfg.ignored_extensions.split('\n') if e.strip()]

        # Check whether we should log this request
        if any(path.startswith(p) for p in ignore_prefixes):
            return response
        if any(ext in path for ext in ignore_extensions):
            return response
        if path.startswith('/static/') or path.startswith('/media/'):
            return response

        # Only set the session cookie for tracked requests
        if new_cookie:
            response.set_cookie(
                '_analytics_sid',
                session_id,
                max_age=60 * 60 * 24 * 30,  # 30 days
                httponly=True,
                secure=request.is_secure(),
                samesite='Lax',
            )

        try:
            ip = self._get_ip(request)
            ip_hash = ''
            if ip and cfg.anonymize_ip:
                ip_hash = hashlib.sha256(ip.encode()).hexdigest()

            # Resolve geolocation
            country_code, country_name, city = _resolve_ip(ip)

            PageView.objects.create(
                url=request.build_absolute_uri(),
                path=path,
                method=request.method,
                status_code=response.status_code,
                ip_hash=ip_hash,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],
                referrer=request.META.get('HTTP_REFERER', '')[:2048],
                user=request.user if request.user.is_authenticated else None,
                session_id=session_id,
                country_code=country_code or '',
                country_name=country_name or '',
                city=city or '',
            )
        except Exception:
            logger.exception("Failed to log page view")

        return response

    @staticmethod
    def _get_ip(request):
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
