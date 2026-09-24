from ..admin_security import admin_security_required
from django.http import Http404
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.translation import gettext as _

from paxalia.models import AnalyticsSettings
from paxalia.views.utils import section_enabled


@admin_security_required
def analytics_settings(request):
    if not section_enabled("settings"):
        raise Http404
    instance = AnalyticsSettings.objects.first()
    if request.method == "POST":
        try:
            refresh_seconds = int(request.POST.get("realtime_refresh_seconds", 30))
        except (TypeError, ValueError):
            refresh_seconds = 30
        refresh_seconds = max(5, min(refresh_seconds, 300))
        data = {
            "anonymize_ip": request.POST.get("anonymize_ip") == "on",
            "ignored_prefixes": request.POST.get("ignored_prefixes", ""),
            "ignored_extensions": request.POST.get("ignored_extensions", ""),
            "realtime_refresh_seconds": refresh_seconds,
            "tracked_paths": request.POST.get("tracked_paths", ""),
            "bot_paths": request.POST.get("bot_paths", ""),
        }
        if instance:
            for key, val in data.items():
                setattr(instance, key, val)
            instance.save()
            messages.success(request, _("Settings saved successfully."))
        else:
            AnalyticsSettings.objects.create(**data)
            messages.success(request, _("Settings saved successfully."))
        return redirect("paxalia:settings")

    context = {
        "settings": instance,
        "active_page": "settings",
        "themes": [
            {"slug": "dark", "label": _("Dark Gold")},
            {"slug": "default", "label": _("Skybound Silk")},
            {"slug": "golden", "label": _("Golden Dusk")},
            {"slug": "azure", "label": _("Azure Drift")},
            {"slug": "sunlit", "label": _("Sunlit Meadow")},
            {"slug": "indigo", "label": _("Indigo Spectrum")},
            {"slug": "arctic", "label": _("Arctic Horizon")},
            {"slug": "ocean", "label": _("Ocean Breeze")},
            {"slug": "twilight", "label": _("Twilight Reverie")},
            {"slug": "velvet", "label": _("Velvet Noir")},
            {"slug": "citrine", "label": _("Citrine Prestige")},
            {"slug": "amethyst", "label": _("Amethyst Luxe")},
            {"slug": "onyx", "label": _("Onyx Pearl")},
        ],
        "languages": [
            {"code": "en", "name": _("English")},
            {"code": "es", "name": _("Español")},
            {"code": "ar", "name": _("العربية")},
            {"code": "zh-hans", "name": _("简体中文")},
            {"code": "pt-br", "name": _("Português (Brasil)")},
        ],
    }
    return render(request, "paxalia/settings.html", context)
