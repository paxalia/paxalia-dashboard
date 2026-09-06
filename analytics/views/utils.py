# analytics/views/utils.py
from django.utils import timezone
from datetime import datetime, timedelta
from django.utils.timezone import make_aware

from analytics.settings import get_config

from user_agents import parse

# Create your views here.

def get_date_range(request):
    """Return (start_dt, end_dt) as aware datetimes from GET params.
       Defaults to the last 30 days (ending today)."""
    today = timezone.now().date()
    end_str = request.GET.get('end_date')
    start_str = request.GET.get('start_date')
    if end_str:
        try:
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = today
    else:
        end_date = today
    if start_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = end_date - timedelta(days=29)
    else:
        start_date = end_date - timedelta(days=29)
    if start_date > end_date:
        start_date = end_date
    start_dt = make_aware(datetime.combine(start_date, datetime.min.time()))
    end_dt = make_aware(datetime.combine(end_date, datetime.max.time()))
    return start_dt, end_dt


def detect_active_preset(start_date, end_date):
    """Return preset key if the date range matches a known preset, else 'custom'."""
    today = timezone.now().date()
    if start_date == today and end_date == today:
        return 'today'
    yesterday = today - timedelta(days=1)
    if start_date == yesterday and end_date == yesterday:
        return 'yesterday'
    if start_date == today - timedelta(days=6) and end_date == today:
        return 'last7'
    if start_date == today - timedelta(days=29) and end_date == today:
        return 'last30'
    first_of_month = today.replace(day=1)
    if start_date == first_of_month and end_date == today:
        return 'this_month'
    return 'custom'


def section_enabled(section_name):
    """Return True if the sidebar section is enabled in config."""
    config = get_config()
    return section_name in config['SIDEBAR_SECTIONS']


def get_current_site(request):
    """
    Return the currently-selected Site for dashboard filtering, or None
    for "All Sites" (no filter).

    Selection comes from ?site=<uuid> and is persisted in the session so
    it carries across navigation without needing it on every link. An
    invalid/stale id (e.g. a deleted Site) is treated the same as no
    selection — falls back to "All Sites" rather than erroring.
    """
    from analytics.models import Site

    site_param = request.GET.get('site')
    if site_param is not None:
        if site_param == '':
            request.session.pop('analytics_current_site_id', None)
            return None
        request.session['analytics_current_site_id'] = site_param
    else:
        site_param = request.session.get('analytics_current_site_id')

    if not site_param:
        return None

    return Site.objects.filter(id=site_param).first()


def get_current_segment(request):
    """Same pattern as get_current_site(): ?segment=<uuid>, persisted in
    session, None means no segment filter applied."""
    from analytics.models import Segment

    segment_param = request.GET.get('segment')
    if segment_param is not None:
        if segment_param == '':
            request.session.pop('analytics_current_segment_id', None)
            return None
        request.session['analytics_current_segment_id'] = segment_param
    else:
        segment_param = request.session.get('analytics_current_segment_id')

    if not segment_param:
        return None

    return Segment.objects.filter(id=segment_param).first()


def site_scoped(queryset, site):
    """Apply the current site filter to a queryset, or return it
    unchanged for "All Sites" (site=None). Centralizing this one-liner
    means every view filters the same way — `.filter(site=site)` when
    site is a Site instance, untouched when it's None (which must NOT
    become `.filter(site=None)` — that would mean "unassigned traffic
    only," not "no filter")."""
    return queryset.filter(site=site) if site is not None else queryset


def get_billing_models():
    """Return (InvoiceModel, UserBillingModel, DonationModel) or (None, None, None)."""
    config = get_config()
    if 'billing' not in config['SIDEBAR_SECTIONS']:
        return None, None, None
    try:
        from django.apps import apps
        invoice_model = apps.get_model(config['BILLING_INVOICE_MODEL'])
        user_plan_model = apps.get_model(config['BILLING_USER_PLAN_MODEL'])
        donation_model = apps.get_model(config['BILLING_DONATION_MODEL'])
        return invoice_model, user_plan_model, donation_model
    except (LookupError, ImportError):
        return None, None, None


def parse_user_agent(ua_string):
    """
    Return a dict with browser, os, device from a user-agent string.
    Falls back to 'Other' / 'Unknown' if parsing fails or library missing.
    """
    result = {
        'browser': 'Other',
        'os': 'Unknown',
        'device': 'Other',
    }
    if not ua_string:
        return result

    try:
        ua = parse(ua_string)

        # Browser
        if ua.browser.family:
            result['browser'] = ua.browser.family
        # OS
        if ua.os.family:
            result['os'] = ua.os.family
        # Device type
        if ua.is_mobile:
            result['device'] = 'Mobile'
        elif ua.is_tablet:
            result['device'] = 'Tablet'
        elif ua.is_pc:
            result['device'] = 'Desktop'
        else:
            result['device'] = 'Other'
    except ImportError:
        # Fallback to simple detection (existing logic)
        ua = ua_string.lower()
        if 'firefox' in ua:
            result['browser'] = 'Firefox'
        elif 'edg' in ua:
            result['browser'] = 'Edge'
        elif 'chrome' in ua and 'safari' in ua:
            result['browser'] = 'Chrome'
        elif 'safari' in ua:
            result['browser'] = 'Safari'
        elif 'opera' in ua or 'opr' in ua:
            result['browser'] = 'Opera'
        # Rough OS / device detection can be added here as well
        if 'windows' in ua:
            result['os'] = 'Windows'
        elif 'mac os' in ua or 'macintosh' in ua:
            result['os'] = 'macOS'
        elif 'linux' in ua and 'android' not in ua:
            result['os'] = 'Linux'
        elif 'android' in ua:
            result['os'] = 'Android'
            result['device'] = 'Mobile'
        elif 'ios' in ua or 'iphone' in ua or 'ipad' in ua:
            result['os'] = 'iOS'
            result['device'] = 'Tablet' if 'ipad' in ua else 'Mobile'
    except Exception:
        pass  # keep defaults
    return result
