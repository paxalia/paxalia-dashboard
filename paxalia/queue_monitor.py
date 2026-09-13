# paxalia/queue_monitor.py
"""
Optional Celery queue introspection for the Queues page — mirrors the
dotted-path config pattern already used for billing models
(BILLING_INVOICE_MODEL etc., see conf's get_billing_models()): this
package doesn't own the consuming project's Celery Application
instance, so it's configured by pointing CELERY_APP_PATH at one
(e.g. 'myproject.celery.app').

Nothing here adds `celery` to requirements.txt. If CELERY_APP_PATH
isn't configured, celery isn't installed, or the configured app can't
be imported, get_queue_stats() returns None rather than raising — the
Queues page then shows an empty/not-configured state, same "no
errors, no broken pages" precedent as the billing/releases sections.

RQ (the other queue library the roadmap mentions) isn't implemented
here — Celery is the more common choice in the Django ecosystem, and
adding RQ support later would follow this exact same shape (a
dotted-path setting, a guarded import, a graceful None on anything
unconfigured or unreachable) rather than needing a redesign.
"""
import importlib

from .settings import get_config


def get_celery_app():
    """Return the configured Celery Application instance, or None if
    unconfigured or unimportable. Never raises."""
    path = get_config().get('CELERY_APP_PATH')
    if not path:
        return None
    try:
        module_path, attr = path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        return getattr(module, attr)
    except Exception:
        return None


def get_queue_stats():
    """
    Returns None if Celery isn't configured. Otherwise a dict:
        {'reachable': bool, 'workers': [...], 'active_count',
         'reserved_count', 'scheduled_count'}
    'reachable': False (with empty workers/counts) means Celery is
    configured but no worker responded to the inspect ping within the
    timeout — a worker being briefly down/restarting shouldn't 500 the
    dashboard, it should show "no workers responding" instead.
    """
    app = get_celery_app()
    if app is None:
        return None

    try:
        inspect = app.control.inspect(timeout=2.0)
        active = inspect.active() or {}
        reserved = inspect.reserved() or {}
        scheduled = inspect.scheduled() or {}
        stats = inspect.stats() or {}
    except Exception:
        return {'reachable': False, 'workers': [], 'active_count': 0, 'reserved_count': 0, 'scheduled_count': 0}

    worker_names = sorted(set(active) | set(reserved) | set(scheduled) | set(stats))
    workers = []
    for name in worker_names:
        pool_info = (stats.get(name) or {}).get('pool') or {}
        workers.append({
            'name': name,
            'active': len(active.get(name, [])),
            'reserved': len(reserved.get(name, [])),
            'scheduled': len(scheduled.get(name, [])),
            'concurrency': pool_info.get('max-concurrency'),
        })

    return {
        'reachable': True,
        'workers': workers,
        'active_count': sum(len(v) for v in active.values()),
        'reserved_count': sum(len(v) for v in reserved.values()),
        'scheduled_count': sum(len(v) for v in scheduled.values()),
    }
