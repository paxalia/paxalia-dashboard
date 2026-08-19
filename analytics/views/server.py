import psutil

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET


@staff_member_required
def server_overview(request):
    context = {
        'active_page': 'server_overview',
        'page_title': _('Server Overview'),
        'page_subtitle': _('Real‑time system health and resource usage'),
    }
    return render(request, 'analytics/server_overview.html', context)


@staff_member_required
def server_cpu(request):
    context = {
        'active_page': 'server_cpu',
        'page_title': _('CPU'),
        'page_subtitle': _('Processor usage and load'),
    }
    return render(request, 'analytics/server_cpu.html', context)


@staff_member_required
def server_memory(request):
    context = {
        'active_page': 'server_memory',
        'page_title': _('Memory'),
        'page_subtitle': _('RAM and swap usage'),
    }
    return render(request, 'analytics/server_memory.html', context)


@staff_member_required
def server_disk(request):
    context = {
        'active_page': 'server_disk',
        'page_title': _('Disk'),
        'page_subtitle': _('Partition usage and I/O'),
    }
    return render(request, 'analytics/server_disk.html', context)


@staff_member_required
def server_network(request):
    context = {
        'active_page': 'server_network',
        'page_title': _('Network'),
        'page_subtitle': _('Interface statistics'),
    }
    return render(request, 'analytics/server_network.html', context)


@staff_member_required
def server_services(request):
    context = {
        'active_page': 'server_services',
        'page_title': _('Services'),
        'page_subtitle': _('Running system services and daemons'),
    }
    return render(request, 'analytics/server_services.html', context)


@staff_member_required
def server_processes(request):
    context = {
        'active_page': 'server_processes',
        'page_title': _('Processes'),
        'page_subtitle': _('Active process list'),
    }
    return render(request, 'analytics/server_processes.html', context)


# -------------------- API endpoints (JSON) --------------------


@staff_member_required
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


@staff_member_required
@require_GET
def api_server_history(request):
    """
    Return historical data (e.g., last 60 minutes) for charts.

    Since there is no persistent time-series store yet, this retains the
    current demonstration behavior and generates a synthetic series.
    """
    import random
    import time

    now = time.time()
    history = []

    for i in range(60):
        t = now - (60 - i) * 60
        history.append({
            'time': t * 1000,
            'cpu': random.randint(10, 80),
            'memory': random.randint(30, 90),
            'disk_io_read': random.randint(0, 100) * 1024 * 1024,
            'disk_io_write': random.randint(0, 100) * 1024 * 1024,
            'network_in': random.randint(0, 50) * 1024 * 1024,
            'network_out': random.randint(0, 50) * 1024 * 1024,
        })

    return JsonResponse(history, safe=False)
