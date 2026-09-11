import psutil

from analytics.permissions import require_section_permission
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET


@require_section_permission('server')
def server_overview(request):
    context = {
        'active_page': 'server_overview',
        'page_title': _('Server Overview'),
        'page_subtitle': _('Real‑time system health and resource usage'),
    }
    return render(request, 'analytics/server_overview.html', context)


@require_section_permission('server')
def server_cpu(request):
    context = {
        'active_page': 'server_cpu',
        'page_title': _('CPU'),
        'page_subtitle': _('Processor usage and load'),
    }
    return render(request, 'analytics/server_cpu.html', context)


@require_section_permission('server')
def server_memory(request):
    context = {
        'active_page': 'server_memory',
        'page_title': _('Memory'),
        'page_subtitle': _('RAM and swap usage'),
    }
    return render(request, 'analytics/server_memory.html', context)


@require_section_permission('server')
def server_disk(request):
    context = {
        'active_page': 'server_disk',
        'page_title': _('Disk'),
        'page_subtitle': _('Partition usage and I/O'),
    }
    return render(request, 'analytics/server_disk.html', context)


@require_section_permission('server')
def server_network(request):
    context = {
        'active_page': 'server_network',
        'page_title': _('Network'),
        'page_subtitle': _('Interface statistics'),
    }
    return render(request, 'analytics/server_network.html', context)


@require_section_permission('server')
def server_services(request):
    context = {
        'active_page': 'server_services',
        'page_title': _('Services'),
        'page_subtitle': _('Running system services and daemons'),
    }
    return render(request, 'analytics/server_services.html', context)


@require_section_permission('server')
def server_processes(request):
    context = {
        'active_page': 'server_processes',
        'page_title': _('Processes'),
        'page_subtitle': _('Active process list'),
    }
    return render(request, 'analytics/server_processes.html', context)


@require_section_permission('server')
def server_slow_queries(request):
    from analytics.models import SlowQuery

    slow_queries = SlowQuery.objects.all()[:200]
    context = {
        'active_page': 'server_slow_queries',
        'page_title': _('Slow Queries'),
        'page_subtitle': _('Database queries recorded by SlowQueryMiddleware'),
        'slow_queries': slow_queries,
    }
    return render(request, 'analytics/server_slow_queries.html', context)


@require_section_permission('server')
def server_queues(request):
    from analytics.queue_monitor import get_queue_stats

    context = {
        'active_page': 'server_queues',
        'page_title': _('Queues'),
        'page_subtitle': _('Celery worker and task status'),
        'queue_stats': get_queue_stats(),
    }
    return render(request, 'analytics/server_queues.html', context)


@require_section_permission('server')
def server_deployments(request):
    from analytics.models import Deployment

    deployments = Deployment.objects.select_related('site', 'annotation')[:100]
    context = {
        'active_page': 'server_deployments',
        'page_title': _('Deployments'),
        'page_subtitle': _('Recorded via manage.py record_deployment'),
        'deployments': deployments,
    }
    return render(request, 'analytics/server_deployments.html', context)


# -------------------- API endpoints (JSON) --------------------


@require_section_permission('server')
@require_GET
def api_server_metrics(request):
    """
    Return all major system metrics as JSON.
    Used by the overview page and individual charts.
    """
    cpu_percent = psutil.cpu_percent(interval=0.5)
    cpu_per_core = psutil.cpu_percent(interval=0.5, percpu=True)
    cpu_count = psutil.cpu_count()
    load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None

    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    disk_usage = {}
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disk_usage[part.device] = {
                'mount': part.mountpoint,
                'total': usage.total,
                'used': usage.used,
                'free': usage.free,
                'percent': usage.percent,
            }
        except PermissionError:
            continue

    disk_io = psutil.disk_io_counters()
    disk_io_data = {
        'read_count': disk_io.read_count if disk_io else 0,
        'write_count': disk_io.write_count if disk_io else 0,
        'read_bytes': disk_io.read_bytes if disk_io else 0,
        'write_bytes': disk_io.write_bytes if disk_io else 0,
    }

    net_io = psutil.net_io_counters(pernic=True)
    net_data = {}
    for iface, stats in net_io.items():
        net_data[iface] = {
            'bytes_sent': stats.bytes_sent,
            'bytes_recv': stats.bytes_recv,
            'packets_sent': stats.packets_sent,
            'packets_recv': stats.packets_recv,
            'errin': stats.errin,
            'errout': stats.errout,
            'dropin': stats.dropin,
            'dropout': stats.dropout,
        }

    processes = []
    for proc in psutil.process_iter(
        ['pid', 'name', 'cpu_percent', 'memory_percent', 'status']
    ):
        try:
            pinfo = proc.info
            processes.append({
                'pid': pinfo['pid'],
                'name': pinfo['name'],
                'cpu': round(pinfo['cpu_percent'], 1),
                'memory': round(pinfo['memory_percent'], 1),
                'status': pinfo['status'],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes.sort(key=lambda p: p['cpu'], reverse=True)
    processes = processes[:20]

    services = []
    try:
        import subprocess

        output = subprocess.check_output(
            [
                'systemctl',
                'list-units',
                '--type=service',
                '--state=running',
                '--no-legend',
            ],
            text=True,
        )

        for line in output.strip().split('\n'):
            parts = line.split()
            if parts:
                services.append({
                    'name': parts[0],
                    'load': parts[1] if len(parts) > 1 else '',
                    'active': parts[2] if len(parts) > 2 else '',
                    'sub': parts[3] if len(parts) > 3 else '',
                    'description': ' '.join(parts[4:]) if len(parts) > 4 else '',
                })
    except (subprocess.SubprocessError, FileNotFoundError):
        services = None

    data = {
        'timestamp': psutil.boot_time(),
        'cpu': {
            'percent': cpu_percent,
            'per_core': cpu_per_core,
            'count': cpu_count,
            'load_avg': load_avg,
        },
        'memory': {
            'total': mem.total,
            'available': mem.available,
            'used': mem.used,
            'percent': mem.percent,
            'swap_total': swap.total,
            'swap_used': swap.used,
            'swap_percent': swap.percent,
        },
        'disk': {
            'partitions': disk_usage,
            'io': disk_io_data,
        },
        'network': net_data,
        'processes': processes,
        'services': services,
    }

    return JsonResponse(data)


@require_section_permission('server')
@require_GET
def api_server_history(request):
    """
    Real historical data from ServerMetricSnapshot, written by
    `manage.py record_server_metrics` (see that command's docstring
    for the required cron/Celery beat scheduling). Before Phase 13
    this endpoint returned synthetic random.randint() data — a
    placeholder that looked real but wasn't (flagged explicitly in
    Phase 8's audit pass and deliberately deferred here). If the
    command has never been scheduled, this now returns an empty list
    rather than fabricating a chart — the frontend shows an empty
    state, not fake numbers.

    disk/network deltas are computed here, between consecutive
    snapshots, from the cumulative counters ServerMetricSnapshot
    stores — max(0, ...) guards against a negative delta if the
    process restarted and psutil's own counters reset to zero
    in between two snapshots.
    """
    from datetime import timedelta

    from django.utils import timezone

    from analytics.models import ServerMetricSnapshot

    minutes = int(request.GET.get('minutes', 60))
    cutoff = timezone.now() - timedelta(minutes=minutes)
    snapshots = list(
        ServerMetricSnapshot.objects.filter(recorded_at__gte=cutoff).order_by('recorded_at')
    )

    history = []
    previous = None
    for snap in snapshots:
        entry = {
            'time': snap.recorded_at.timestamp() * 1000,
            'cpu': round(snap.cpu_percent, 1),
            'memory': round(snap.memory_percent, 1),
        }
        if previous is not None:
            entry['disk_io_read'] = max(0, snap.disk_io_read_bytes - previous.disk_io_read_bytes)
            entry['disk_io_write'] = max(0, snap.disk_io_write_bytes - previous.disk_io_write_bytes)
            entry['network_in'] = max(0, snap.network_in_bytes - previous.network_in_bytes)
            entry['network_out'] = max(0, snap.network_out_bytes - previous.network_out_bytes)
        else:
            entry['disk_io_read'] = 0
            entry['disk_io_write'] = 0
            entry['network_in'] = 0
            entry['network_out'] = 0
        history.append(entry)
        previous = snap

    return JsonResponse(history, safe=False)
