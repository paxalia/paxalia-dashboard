# analytics/views/geography.py
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render
from django.db.models import Count

from analytics.models import PageView

from .utils import get_date_range, detect_active_preset, section_enabled

import pycountry


# Create your views here.


@staff_member_required
def analytics_geography(request):
    if not section_enabled('geography'):
        raise Http404
    start_dt, end_dt = get_date_range(request)
    base_qs = PageView.objects.filter(created_at__range=(start_dt, end_dt))

    # Country counts (unchanged)
    country_qs = (
        base_qs
        .exclude(country_code__isnull=True)
        .exclude(country_code='')
        .values('country_code', 'country_name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    countries = []
    for item in country_qs:
        code = item['country_code']
        name = item['country_name']
        count = item['count']
        try:
            country = pycountry.countries.get(alpha_2=code)
            if not country:
                continue
            alpha3 = country.alpha_3
        except (LookupError, AttributeError, KeyError):
            continue
        countries.append({
            'code': alpha3,  # for Datamaps
            'alpha2': code,  # for click filtering
            'name': name,
            'count': count,
        })

    # Selected country filter
    selected_country = request.GET.get('country', '').strip()

    # Top cities – optionally filtered by selected country
    city_qs = (
        base_qs
        .exclude(city__isnull=True)
        .exclude(city='')
    )
    if selected_country:
        city_qs = city_qs.filter(country_code=selected_country)

    city_qs = (
        city_qs
        .values('city', 'country_name')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )

    active_preset = detect_active_preset(start_dt.date(), end_dt.date())

    context = {
        'countries': countries,
        'top_cities': city_qs,
        'selected_country': selected_country,
        'start_date': start_dt.date(),
        'end_date': end_dt.date(),
        'active_preset': active_preset,
        'show_search': False,
        'active_page': 'geography',
    }
    return render(request, 'analytics/geography.html', context)
