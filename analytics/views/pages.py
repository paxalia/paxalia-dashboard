# analytics/views/pages.py
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render
from django.db.models import Count
from django.core.paginator import Paginator

from analytics.models import PageView

from .utils import get_date_range, detect_active_preset, section_enabled


# Create your views here.

@staff_member_required
def analytics_pages(request):
    if not section_enabled('pages'):
        raise Http404
    start_dt, end_dt = get_date_range(request)
    base_qs = PageView.objects.filter(created_at__range=(start_dt, end_dt), is_bot=False, is_api=False)

    path_query = request.GET.get('path', '').strip()
    if path_query:
        base_qs = base_qs.filter(path__icontains=path_query)

    pages = (
        base_qs
        .values('path')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    active_preset = detect_active_preset(start_dt.date(), end_dt.date())

    paginator = Paginator(pages, 50)  # 50 rows per page
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {
        'pages': page_obj,
        'start_date': start_dt.date(),
        'end_date': end_dt.date(),
        'active_preset': active_preset,
        'show_search': True,
        'search_path': path_query,
        'active_page': 'pages',
    }
    return render(request, 'analytics/pages.html', context)
