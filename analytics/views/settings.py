from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.translation import gettext as _

from analytics.models import AnalyticsSettings
from analytics.views.utils import section_enabled


@staff_member_required
def analytics_settings(request):
    if not section_enabled('settings'):
        raise Http404
    instance = AnalyticsSettings.objects.first()
    if request.method == 'POST':
        data = {
            'anonymize_ip': request.POST.get('anonymize_ip') == 'on',
            'ignored_prefixes': request.POST.get('ignored_prefixes', ''),
            'ignored_extensions': request.POST.get('ignored_extensions', ''),
            'realtime_refresh_seconds': int(request.POST.get('realtime_refresh_seconds', 30)),
            # New fields
            'tracked_paths': request.POST.get('tracked_paths', ''),
            'bot_paths': request.POST.get('bot_paths', ''),
        }
        if instance:
            for key, val in data.items():
                setattr(instance, key, val)
            instance.save()
            messages.success(request, _("Settings saved successfully."))
        else:
            AnalyticsSettings.objects.create(**data)
        return redirect('analytics:settings')

    context = {
        'settings': instance,
        'active_page': 'settings',
        'themes': [
            {'slug': 'dark', 'label': 'Dark Gold'},
            {'slug': 'default', 'label': 'Skybound Silk'},
            {'slug': 'golden', 'label': 'Golden Dusk'},
            {'slug': 'azure', 'label': 'Azure Drift'},
            {'slug': 'sunlit', 'label': 'Sunlit Meadow'},
            {'slug': 'indigo', 'label': 'Indigo Spectrum'},
            {'slug': 'arctic', 'label': 'Arctic Horizon'},
            {'slug': 'ocean', 'label': 'Ocean Breeze'},
            {'slug': 'twilight', 'label': 'Twilight Reverie'},
            {'slug': 'velvet', 'label': 'Velvet Noir'},
            {'slug': 'citrine', 'label': 'Citrine Prestige'},
            {'slug': 'onyx', 'label': 'Onyx Pearl'},
        ],
        'languages': [
            {'code': 'en', 'name': 'English'},
            {'code': 'es', 'name': 'Español'},
            {'code': 'ar', 'name': 'العربية'},
            {'code': 'zh-hans', 'name': '简体中文'},
            {'code': 'pt-br', 'name': 'Português (Brasil)'},
        ],
    }
    return render(request, 'analytics/settings.html', context)